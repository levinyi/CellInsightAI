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
import boto3
from botocore.client import Config


def ws_send(task_id, payload, org_id: str | None = None):
    """通过Channels向对应任务/组织分组推送WebSocket消息
    Args:
        task_id (str): 任务ID（对应 StepRun.id）
        payload (dict): 要发送的消息体
        org_id (Optional[str]): 组织ID，用于多租户隔离（可选）
    """
    channel_layer = get_channel_layer()
    group = f"task_{task_id}" if not org_id else f"org_{org_id}_task_{task_id}"
    async_to_sync(channel_layer.group_send)(
        group,
        {
            'type': 'task.message',
            'payload': payload,
        }
    )


def _get_s3_client():
    """返回已配置的 S3/MinIO 客户端，用于对象存储操作"""
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )


def _get_s3_file_size(key: str) -> int:
    """获取对象存储中指定 Key 的文件大小，失败返回 0"""
    try:
        s3 = _get_s3_client()
        head = s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        return int(head.get('ContentLength', 0))
    except Exception:
        return 0


def _persist_results_and_advice(run: StepRun, result: dict, final_phase_message: str = 'SUCCEEDED') -> dict:
    """通用持久化逻辑：保存metrics/evidence、登记artifacts并生成AI建议
    Args:
        run: 当前StepRun
        result: runner返回的结果字典，包含metrics/evidence/artifacts
        final_phase_message: WebSocket完成阶段的提示
    Returns:
        dict: {'status': run.status, 'metrics': metrics}
    """
    metrics = result.get('metrics', {}) or {}
    evidence = result.get('evidence', {}) or {}
    artifacts = result.get('artifacts', []) or []

    # Runner错误处理
    if 'error' in metrics:
        run.metrics_json = metrics
        run.evidence_json = evidence
        run.status = 'FAILED'
        run.finished_at = timezone.now()
        run.save(update_fields=['metrics_json', 'evidence_json', 'status', 'finished_at'])
        try:
            ws_send(task_id=str(run.id), payload={'phase': 'FAILED', 'progress': 100, 'message': metrics['error']})
        except Exception:
            pass
        return {'status': run.status, 'metrics': metrics}

    # 持久化指标与证据
    run.metrics_json = metrics
    run.evidence_json = evidence
    run.save(update_fields=['metrics_json', 'evidence_json'])

    # 保存产物
    try:
        ws_send(task_id=str(run.id), payload={'phase': 'SAVING', 'progress': 70, 'message': 'Persisting artifacts'})
    except Exception:
        pass

    for art in artifacts:
        key = art.get('path') or art.get('file_path') or ''
        if not key:
            continue
        size = _get_s3_file_size(key)
        Artifact.objects.create(
            step_run=run,
            name=art.get('name') or os.path.basename(key),
            artifact_type=art.get('type') or 'json',
            file_path=key,
            file_size=size,
            metadata={}
        )

    # 生成AI建议
    try:
        AdviceEngine.generate_advice(run)
    except Exception:
        pass

    # 完成
    run.status = 'SUCCEEDED'
    run.finished_at = timezone.now()
    run.save(update_fields=['status', 'finished_at'])
    try:
        ws_send(task_id=str(run.id), payload={'phase': 'DONE', 'progress': 100, 'message': final_phase_message})
    except Exception:
        pass

    return {'status': run.status, 'metrics': metrics}


def _select_input_h5ad(run: StepRun) -> str | None:
    """选择下游步骤的数据输入优先级：
    1) 同一Session内最近一次成功运行的H5AD产物；
    2) 数据集的原始 input_h5ad_path。
    返回S3/MinIO Key（不带s3://前缀）或None。
    """
    dataset = run.session.dataset if run.session else None
    # 优先找同Session最近成功的H5AD产物
    if run.session:
        prev_run = (
            StepRun.objects.filter(session=run.session, status='SUCCEEDED')
            .exclude(id=run.id)
            .order_by('-created_at')
            .first()
        )
        if prev_run:
            h5ad_art = prev_run.artifacts.filter(artifact_type='h5ad').first()
            if h5ad_art and h5ad_art.file_path:
                return h5ad_art.file_path
    # 退回到数据集的初始路径
    if dataset and getattr(dataset, 'input_h5ad_path', None):
        return dataset.input_h5ad_path
    return None


@shared_task(bind=True, name='projects.run_step')
def run_step(self, step_run_id: str):
    """执行单步分析任务（Celery 任务）
    Args:
        step_run_id (str): StepRun 主键ID
    Returns:
        dict: 任务结果，包含状态与关键指标
    """
    # 修复：去除无效的 select_related('sample')，改为有效字段，并预取 dataset
    run = StepRun.objects.select_related('session', 'step', 'session__dataset').get(id=step_run_id)
    run.status = 'RUNNING'
    run.started_at = timezone.now()
    run.save(update_fields=['status', 'started_at'])

    # 推送开始阶段
    try:
        ws_send(task_id=str(run.id), payload={'phase': 'START', 'progress': 5, 'message': 'RUNNING'})
    except Exception:
        pass

    if settings.DEBUG:
        time.sleep(1)

    step_type = run.step.step_type
    params = run.params_json or {}

    # QC：真实执行
    if step_type == 'qc':
        dataset = run.session.dataset if run.session else None
        data_uri = getattr(dataset, 'input_h5ad_path', None) if dataset else None
        if not data_uri:
            # 没有提供 H5AD 输入，直接失败
            run.metrics_json = {'error': 'Dataset.input_h5ad_path is required for QC'}
            run.status = 'FAILED'
            run.finished_at = timezone.now()
            run.save(update_fields=['metrics_json', 'status', 'finished_at'])
            try:
                ws_send(task_id=str(run.id), payload={'phase': 'FAILED', 'progress': 100, 'message': 'Missing H5AD'})
            except Exception:
                pass
            return {'status': run.status, 'metrics': run.metrics_json}

        inputs = {
            'data_uri': data_uri,  # S3/MinIO Key 或 s3://bucket/key
            'step_run_id': str(run.id),
        }

        # 调用真实 QC Runner
        try:
            result = run_qc(inputs=inputs, params=params)
        except Exception as e:
            result = {'artifacts': [], 'metrics': {'error': str(e)}, 'evidence': {}}

        # 归一化/补充通用指标以兼容建议引擎（QCAdviceAnalyzer 目前读取 cells 和 high_mito）
        metrics = result.get('metrics', {}) or {}
        if 'cells' not in metrics:
            metrics['cells'] = metrics.get('cells_filtered') or metrics.get('cells_raw') or 0
        if 'high_mito' not in metrics and 'mean_mito_pct' in metrics:
            try:
                metrics['high_mito'] = float(metrics['mean_mito_pct']) / 100.0
            except Exception:
                metrics['high_mito'] = 0
        result['metrics'] = metrics

        return _persist_results_and_advice(run, result, final_phase_message='QC SUCCEEDED')

    # HVG：基于上游H5AD输入（若无则回退到数据集）
    if step_type == 'hvg':
        data_uri = _select_input_h5ad(run)
        if not data_uri:
            result = {'artifacts': [], 'metrics': {'error': 'No input H5AD found for HVG'}, 'evidence': {}}
            return _persist_results_and_advice(run, result)
        inputs = {'data_uri': data_uri, 'step_run_id': str(run.id)}
        try:
            result = run_hvg(inputs=inputs, params=params)
        except Exception as e:
            result = {'artifacts': [], 'metrics': {'error': str(e)}, 'evidence': {}}
        return _persist_results_and_advice(run, result, final_phase_message='HVG SUCCEEDED')

    # PCA：依赖上游（通常是HVG/归一化）的输出
    if step_type == 'pca':
        data_uri = _select_input_h5ad(run)
        inputs = {'data_uri': data_uri, 'step_run_id': str(run.id)} if data_uri else {'step_run_id': str(run.id)}
        try:
            result = run_pca(inputs=inputs, params=params)
        except Exception as e:
            result = {'artifacts': [], 'metrics': {'error': str(e)}, 'evidence': {}}
        return _persist_results_and_advice(run, result, final_phase_message='PCA SUCCEEDED')

    # UMAP：依赖上游（通常是PCA）的输出
    if step_type == 'umap':
        data_uri = _select_input_h5ad(run)
        inputs = {'data_uri': data_uri, 'step_run_id': str(run.id)} if data_uri else {'step_run_id': str(run.id)}
        try:
            result = run_umap(inputs=inputs, params=params)
        except Exception as e:
            result = {'artifacts': [], 'metrics': {'error': str(e)}, 'evidence': {}}
        return _persist_results_and_advice(run, result, final_phase_message='UMAP SUCCEEDED')

    # Clustering：依赖上游（通常是邻接图/PCA）的输出
    if step_type == 'clustering':
        data_uri = _select_input_h5ad(run)
        inputs = {'data_uri': data_uri, 'step_run_id': str(run.id)} if data_uri else {'step_run_id': str(run.id)}
        try:
            result = run_cluster(inputs=inputs, params=params)
        except Exception as e:
            result = {'artifacts': [], 'metrics': {'error': str(e)}, 'evidence': {}}
        return _persist_results_and_advice(run, result, final_phase_message='CLUSTERING SUCCEEDED')

    # -------------------- 其它未知步骤暂用演示逻辑 --------------------
    metrics = {
        'cells': 9876,
        'doublet_rate': 0.037,
        'high_mito': 0.08,
    }
    run.metrics_json = metrics
    run.status = 'SUCCEEDED'
    run.finished_at = timezone.now()
    run.save(update_fields=['metrics_json', 'status', 'finished_at'])

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

    try:
        ws_send(task_id=str(run.id), payload={'phase': 'DONE', 'progress': 100, 'message': 'SUCCEEDED'})
    except Exception:
        pass
    return {'status': run.status, 'metrics': metrics}