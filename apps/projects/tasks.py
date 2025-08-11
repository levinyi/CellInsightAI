import time
import uuid
import json
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import StepRun, Step, Artifact
from apps.steps.runners.qc_runner import run_qc
from django.conf import settings
from apps.advice.analyzer import AdviceEngine
# 新增导入其他 Runner
from apps.steps.runners.hvg_runner import run_hvg
from apps.steps.runners.pca_runner import run_pca
from apps.steps.runners.umap_runner import run_umap
from apps.steps.runners.cluster_runner import run_cluster


def ws_send(task_id, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"task_{task_id}",
        {"type": "task.message", "payload": payload}
    )

@shared_task(bind=True, name='projects.run_step')
def run_step(self, step_run_id: str):
    run = StepRun.objects.get(id=step_run_id)
    run.status = 'RUNNING'
    run.started_at = timezone.now()
    run.save(update_fields=['status', 'started_at'])

    task_id = str(run.id)

    # 根据 Step 类型选择 Runner（扩展支持 qc/hvg/pca/umap/clustering）
    step = run.step
    params = run.params_json or {}

    # 兼容参数键名差异：PCA 的 n_pcs -> n_components
    if step.step_type == 'pca' and 'n_pcs' in params and 'n_components' not in params:
        params = {**params, 'n_components': params.get('n_pcs')}

    ws_send(task_id, {'phase': 'START', 'message': '开始执行', 'progress': 5, 'ts': timezone.now().isoformat()})

    outputs = {}
    try:
        if step.step_type == 'qc':
            outputs = run_qc(inputs={}, params=params)
        elif step.step_type == 'hvg':
            outputs = run_hvg(inputs={}, params=params)
        elif step.step_type == 'pca':
            outputs = run_pca(inputs={}, params=params)
        elif step.step_type == 'umap':
            outputs = run_umap(inputs={}, params=params)
        elif step.step_type in ('clustering', 'cluster'):
            outputs = run_cluster(inputs={}, params=params)
        else:
            # 其他步骤暂时模拟
            outputs = {'artifacts': [], 'metrics': {'note': 'not_implemented'}, 'evidence': {}}
        ws_send(task_id, {'phase': step.step_type.upper(), 'message': '阶段完成', 'progress': 70, 'ts': timezone.now().isoformat()})

        # 保存metrics和evidence
        run.metrics_json = outputs.get('metrics', {})
        run.evidence_json = outputs.get('evidence', {})
        run.status = 'SUCCEEDED'
        run.finished_at = timezone.now()
        run.save(update_fields=['metrics_json', 'evidence_json', 'status', 'finished_at'])

        # 记录artifacts
        for art in outputs.get('artifacts', []):
            Artifact.objects.create(
                step_run=run,
                name=art.get('name'),
                artifact_type=art.get('type', 'json'),
                file_path=art.get('path'),
                file_size=art.get('size', 0),
                file_hash=art.get('hash', ''),
                metadata=art.get('metadata', {})
            )

        # 生成AI建议（当前仅对 QC 生效）
        try:
            count = AdviceEngine.generate_advice(run)
            ws_send(task_id, {'phase': 'ADVICE', 'message': f'生成{count or 0}条建议', 'progress': 90, 'ts': timezone.now().isoformat()})
        except Exception as _:
            pass

        ws_send(task_id, {
            'phase': 'DONE',
            'message': '分析完成',
            'metrics': run.metrics_json,
            'progress': 100,
            'ts': timezone.now().isoformat(),
        })
        return {'status': run.status, 'metrics': run.metrics_json}
    except Exception as e:
        run.status = 'FAILED'
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'finished_at'])
        ws_send(task_id, {'phase': 'ERROR', 'message': str(e), 'progress': 100, 'ts': timezone.now().isoformat()})
        raise