import os
import uuid
import zipfile
import tempfile
import json
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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


@csrf_exempt
@require_http_methods(["POST"]) 
def upload_direct(request):
    """
    直传代理：客户端将文件直接上传到后端，由后端 put_object 到对象存储。
    form-data: file=<uploaded file>, path=<target key>
    返回: {"path": "..."}
    """
    try:
        f = request.FILES.get('file')
        path = request.POST.get('path') or f"uploads/{uuid.uuid4()}"
        if not f:
            return JsonResponse({'detail': 'file required'}, status=400)
        s3 = get_s3_client()
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        content_type = getattr(f, 'content_type', 'application/octet-stream') or 'application/octet-stream'
        s3.put_object(Bucket=bucket, Key=path, Body=f, ContentType=content_type)
        return JsonResponse({'path': path})
    except Exception as e:
        return JsonResponse({'detail': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"]) 
def extract_zip_10x(request):
    """
    输入: {"zip_path": "samples/<sample_id>/files.zip"}
    从对象存储下载该 ZIP，解压到 samples/<sample_id>/extracted/，
    尝试识别 10X 三件套：matrix.mtx(.gz)、features.tsv(.gz)/genes.tsv(.gz)、barcodes.tsv(.gz)
    输出: { "mtx": "samples/<sample_id>/extracted/...", "features": "...", "barcodes": "..." }
    注：此端点只做路径搬运，不做内容解析。
    """
    try:
        data = json.loads(request.body or '{}')
        zip_path = data.get('zip_path')
        if not zip_path:
            return JsonResponse({'detail': 'zip_path required'}, status=400)
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        s3 = get_s3_client()
        # 生成临时下载 URL
        dl_url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': zip_path},
            ExpiresIn=3600
        )
        # 下载到本地临时文件
        with tempfile.TemporaryDirectory() as tmpdir:
            local_zip = os.path.join(tmpdir, 'archive.zip')
            r = requests.get(dl_url, timeout=60)
            r.raise_for_status()
            with open(local_zip, 'wb') as f:
                f.write(r.content)
            # 解压
            extract_dir = os.path.join(tmpdir, 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(local_zip, 'r') as zf:
                zf.extractall(extract_dir)
            # 遍历找到候选文件
            tenx = {'mtx': None, 'features': None, 'barcodes': None}
            for root, _, files in os.walk(extract_dir):
                for name in files:
                    lower = name.lower()
                    full_path = os.path.join(root, name)
                    rel = os.path.relpath(full_path, extract_dir)
                    if lower.endswith('matrix.mtx') or lower.endswith('matrix.mtx.gz'):
                        tenx['mtx'] = rel
                    elif lower.endswith('features.tsv') or lower.endswith('features.tsv.gz') or lower.endswith('genes.tsv') or lower.endswith('genes.tsv.gz'):
                        tenx['features'] = rel
                    elif lower.endswith('barcodes.tsv') or lower.endswith('barcodes.tsv.gz'):
                        tenx['barcodes'] = rel
            if not all(tenx.values()):
                return JsonResponse({'detail': '10X files not found in zip', 'found': tenx}, status=400)
            # 将解压后的文件逐个上传回 S3 到一个固定前缀
            sample_prefix = os.path.dirname(zip_path) + '/extracted/'
            uploaded = {}
            for k, rel in tenx.items():
                local_file = os.path.join(extract_dir, rel)
                key = sample_prefix + rel.replace('\\', '/')
                # 确保中间目录
                # 直接 put_object 上传
                with open(local_file, 'rb') as f2:
                    s3.put_object(Bucket=bucket, Key=key, Body=f2)
                uploaded[k] = key
            return JsonResponse(uploaded)
    except Exception as e:
        return JsonResponse({'detail': str(e)}, status=500)