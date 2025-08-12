import time
import uuid
import json
import os
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import StepRun, Step, Artifact, Advice
from apps.steps.runners.qc_runner import run_qc
from django.conf import settings
from apps.advice.analyzer import AdviceEngine
# 新增导入其他 Runner
from apps.steps.runners.hvg_runner import run_hvg
from apps.steps.runners.pca_runner import run_pca
from apps.steps.runners.umap_runner import run_umap
from apps.steps.runners.cluster_runner import run_cluster


def ws_send(task_id, payload, org_id: str | None = None):
    channel_layer = get_channel_layer()
    group = f"task_{task_id}" if not org_id else f"org_{org_id}_task_{task_id}"
    async_to_sync(channel_layer.group_send)(
        group,
        {
            'type': 'task.message',
            'payload': payload,
        }
    )


@shared_task(bind=True, name='projects.run_step')
def run_step(self, step_run_id: str):
    run = StepRun.objects.select_related('sample', 'step').get(id=step_run_id)
    run.status = 'RUNNING'
    run.started_at = timezone.now()
    run.save(update_fields=['status', 'started_at'])
    
    # In debug mode, allow time for WebSocket connection
    if settings.DEBUG:
        time.sleep(2)

    # Simulated metrics and advice generation
    metrics = {
        'cells': 9876,
        'doublet_rate': 0.037,
        'high_mito': 0.08,
    }
    run.metrics_json = metrics
    run.status = 'SUCCEEDED'
    run.finished_at = timezone.now()
    run.save(update_fields=['metrics_json', 'status', 'finished_at'])

    # A demo advice
    Advice.objects.create(
        step_run=run,
        advice_type='parameter_optimization',
        risk_level='low',
        title='可适当提高 n_top_genes',
        description='增加 HVG 的 n_top_genes 有利于更丰富的特征表达。',
        evidence_text='基于 QC 指标与 PCA 解释度',
        patch_json={'n_top_genes': 3000},
        patch_type='params',
    )

    # Notify via websocket
    ws_send(task_id=str(run.id), payload={'phase': 'DONE', 'progress': 100, 'message': 'SUCCEEDED'})
    return {'status': run.status, 'metrics': metrics}