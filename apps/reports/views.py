import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.utils import timezone

from apps.projects.models import StepRun, Advice, AuditLog

@csrf_exempt
@require_http_methods(["POST"]) 
def generate_report(request):
    """
    输入: {"run_id": "uuid", "format": "html|pdf"}
    输出: HTML内容或下载链接（此处先返回HTML）
    """
    data = json.loads(request.body or '{}')
    run_id = data.get('run_id')
    fmt = (data.get('format') or 'html').lower()

    try:
        run = StepRun.objects.select_related('sample','step').get(id=run_id)
    except StepRun.DoesNotExist:
        return JsonResponse({'detail': 'StepRun not found'}, status=404)

    advice = list(Advice.objects.filter(step_run=run).values())
    context = {
        'run': run,
        'advice': advice,
        'generated_at': timezone.now(),
    }
    html = render_to_string('report_basic.html', context)

    # 审计：记录报告导出行为
    try:
        user = getattr(request, 'user', None)
        AuditLog.objects.create(
            user=user if (user and getattr(user, 'is_authenticated', False)) else None,
            action_type='report_export',
            object_type='StepRun',
            object_id=run.id,
            changes={'format': fmt},
            metadata={'source': 'reports.generate_report'}
        )
    except Exception:
        # 审计失败不影响业务返回
        pass

    if fmt == 'html':
        return HttpResponse(html)
    else:
        # TODO: 后续接入PDF导出（weasyprint/typst/puppeteer）
        return HttpResponse(html)

@require_http_methods(["GET"]) 
def generate_report_for_run(request, id):
    request._body = json.dumps({'run_id': str(id), 'format': 'html'}).encode('utf-8')
    return generate_report(request)