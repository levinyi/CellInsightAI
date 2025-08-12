from django.urls import path
from .views import generate_presigned_url, extract_zip_10x, upload_direct

urlpatterns = [
    path('presign', generate_presigned_url, name='generate_presigned_url'),
    path('extract-zip-10x', extract_zip_10x, name='extract_zip_10x'),
    path('upload', upload_direct, name='upload_direct'),
]