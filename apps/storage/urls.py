from django.urls import path
from .views import generate_presigned_url

urlpatterns = [
    path('presign', generate_presigned_url, name='generate_presigned_url'),
]