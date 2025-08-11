from django.urls import path
from .views import generate_report, generate_report_for_run

urlpatterns = [
    path('generate', generate_report, name='generate_report'),
    path('runs/<uuid:id>/export', generate_report_for_run, name='generate_report_for_run'),
]