import json
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import StepRun, Step, Sample
from .tasks import run_step

@require_http_methods(["POST"])
@login_required
def trigger_run(request):
    """Create a StepRun and dispatch Celery task (authenticated)"""
    data = json.loads(request.body or '{}')
    sample_id = data.get('sample')
    step_id = data.get('step')
    params = data.get('params', {})

    sample = get_object_or_404(Sample, id=sample_id)
    step = get_object_or_404(Step, id=step_id)

    # Basic tenant isolation: ensure sample belongs to user's org if set
    profile = getattr(request.user, 'profile', None)
    if profile and profile.organization and getattr(sample.project, 'organization_id', None):
        if str(profile.organization.id) != str(sample.project.organization_id):
            return JsonResponse({'detail': 'Forbidden'}, status=403)

    run = StepRun.objects.create(sample=sample, step=step, params_json=params, status='PENDING')
    # Dispatch Celery
    run_step.delay(str(run.id))

    return JsonResponse({
        'id': str(run.id),
        'status': run.status,
        'ws_url': f'ws://{request.get_host()}/ws/tasks/{run.id}',
        'created_at': run.created_at.isoformat(),
    }, status=202)