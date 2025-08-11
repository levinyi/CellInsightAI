import json
import uuid
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from apps.projects.models import StepRun, Step, Sample
from apps.projects.tasks import run_step

@csrf_exempt
@require_http_methods(["POST"])
def create_task(request):
    """创建任务：对应创建一个 StepRun 并派发 Celery 任务"""
    data = json.loads(request.body or '{}')
    sample_id = data.get('sample')
    step_id = data.get('step')
    params = data.get('params') or {}

    if not sample_id or not step_id:
        return JsonResponse({'detail': 'sample 和 step 为必填'}, status=400)

    sample = get_object_or_404(Sample, id=sample_id)
    step = get_object_or_404(Step, id=step_id)

    run = StepRun.objects.create(sample=sample, step=step, params_json=params, status='PENDING')
    # 派发 Celery
    run_step.delay(str(run.id))

    return JsonResponse({
        'task_id': str(run.id),
        'status_url': f"/api/v1/tasks/{run.id}",
        'ws_url': f'ws://{request.get_host()}/ws/tasks/{run.id}',
        'created_at': run.created_at.isoformat(),
    }, status=202)

@require_http_methods(["GET"]) 
def get_task_status(request, id):
    """查询任务状态：返回 StepRun 状态机信息"""
    try:
        run = StepRun.objects.get(id=id)
    except StepRun.DoesNotExist:
        return JsonResponse({'detail': 'not found'}, status=404)

    payload = {
        'id': str(run.id),
        'status': run.status,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        'metrics': run.metrics_json or {},
        'updated_at': (run.finished_at or run.started_at or run.created_at).isoformat(),
    }
    return JsonResponse(payload)