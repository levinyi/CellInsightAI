from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    ProjectViewSet, SampleViewSet, StepViewSet, StepRunViewSet,
    ArtifactViewSet, AdviceViewSet, AuditLogViewSet
)
from .api import trigger_run

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'samples', SampleViewSet)
router.register(r'steps', StepViewSet)
router.register(r'step-runs', StepRunViewSet)
router.register(r'artifacts', ArtifactViewSet)
router.register(r'advice', AdviceViewSet)
router.register(r'audit-logs', AuditLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('run/', trigger_run, name='trigger_run'),
]