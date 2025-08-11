import os
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import boto3
from botocore.client import Config
from django.conf import settings


def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )


@csrf_exempt
@require_http_methods(["POST"]) 
def generate_presigned_url(request):
    """
    输入: {"path": "artifacts/run_id/filename", "method": "put|get", "content_type": "application/octet-stream"}
    输出: {"url": "...", "fields": {..}, "method": "PUT|GET"}
    """
    import json
    data = json.loads(request.body or '{}')
    path = data.get('path') or f"uploads/{uuid.uuid4()}"
    method = (data.get('method') or 'put').lower()
    content_type = data.get('content_type') or 'application/octet-stream'

    s3 = get_s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME

    if method == 'put':
        url = s3.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': bucket, 'Key': path, 'ContentType': content_type},
            ExpiresIn=3600
        )
        return JsonResponse({'url': url, 'method': 'PUT', 'path': path})
    else:
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': path},
            ExpiresIn=3600
        )
        return JsonResponse({'url': url, 'method': 'GET', 'path': path})