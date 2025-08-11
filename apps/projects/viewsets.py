from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Project, Sample, Step, StepRun, Artifact, Advice, AuditLog
from .serializers import (
    ProjectSerializer, SampleSerializer, StepSerializer, StepRunSerializer,
    ArtifactSerializer, AdviceSerializer, AuditLogSerializer
)
from apps.common.permissions import IsOrgMember, RBACByRole

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            return qs.filter(organization_id=str(profile.organization.id))
        return qs

    def perform_create(self, serializer):
        owner = self.request.user
        profile = getattr(owner, 'profile', None)
        org_id = str(profile.organization.id) if profile and profile.organization else None
        serializer.save(owner=owner, organization_id=org_id)

class SampleViewSet(viewsets.ModelViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            return qs.filter(project__organization_id=str(profile.organization.id))
        return qs

class StepViewSet(viewsets.ModelViewSet):
    queryset = Step.objects.all()
    serializer_class = StepSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def ensure_defaults(self, request):
        created = []
        defaults = [
            {'name': 'Quality Control', 'step_type': 'qc', 'description': 'Basic QC filters', 'runner_image': 'bioai/runner:latest', 'runner_command': 'python qc.py', 'default_params': {'min_genes': 200, 'max_genes': 5000, 'max_mito': 0.1}},
            {'name': 'Highly Variable Genes', 'step_type': 'hvg', 'description': 'Select HVGs', 'runner_image': 'bioai/runner:latest', 'runner_command': 'python hvg.py', 'default_params': {'method': 'seurat_v3', 'n_top_genes': 2000}},
            {'name': 'PCA', 'step_type': 'pca', 'description': 'Dimensionality reduction', 'runner_image': 'bioai/runner:latest', 'runner_command': 'python pca.py', 'default_params': {'n_pcs': 30}},
            {'name': 'UMAP', 'step_type': 'umap', 'description': 'Embedding', 'runner_image': 'bioai/runner:latest', 'runner_command': 'python umap.py', 'default_params': {'min_dist': 0.5}},
            {'name': 'Clustering', 'step_type': 'clustering', 'description': 'Leiden clustering', 'runner_image': 'bioai/runner:latest', 'runner_command': 'python cluster.py', 'default_params': {'resolution': 0.8}},
        ]
        for d in defaults:
            obj, was_created = Step.objects.get_or_create(step_type=d['step_type'], defaults=d)
            if was_created:
                created.append(str(obj.id))
        return Response({'created': created, 'total': Step.objects.count()})

class StepRunViewSet(viewsets.ModelViewSet):
    queryset = StepRun.objects.all().select_related('sample', 'step')
    serializer_class = StepRunSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            return qs.filter(sample__project__organization_id=str(profile.organization.id))
        return qs

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        run = self.get_object()
        run.is_pinned = True
        run.save(update_fields=['is_pinned'])
        return Response({'status': 'pinned'})

    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        run = self.get_object()
        run.is_pinned = False
        run.save(update_fields=['is_pinned'])
        return Response({'status': 'unpinned'})

    @action(detail=True, methods=['get'])
    def advice(self, request, pk=None):
        run = self.get_object()
        qs = Advice.objects.filter(step_run=run).order_by('-created_at')
        return Response(AdviceSerializer(qs, many=True).data)

class ArtifactViewSet(viewsets.ModelViewSet):
    queryset = Artifact.objects.all()
    serializer_class = ArtifactSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            return qs.filter(step_run__sample__project__organization_id=str(profile.organization.id))
        return qs

class AdviceViewSet(viewsets.ModelViewSet):
    queryset = Advice.objects.all()
    serializer_class = AdviceSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            return qs.filter(step_run__sample__project__organization_id=str(profile.organization.id))
        return qs

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        advice = self.get_object()
        run = advice.step_run
        # 仅处理参数补丁
        if advice.patch_type in ('params', 'both'):
            original_params = dict(run.params_json or {})
            new_params = dict(original_params)
            patch = advice.patch_json or {}
            new_params.update(patch)
            run.params_json = new_params
            run.save(update_fields=['params_json'])
            # 更新建议状态
            advice.is_applied = True
            advice.applied_at = timezone.now()
            advice.applied_by = request.user if request.user.is_authenticated else None
            advice.rollback_data = {'prev_params': original_params}
            advice.save(update_fields=['is_applied','applied_at','applied_by','rollback_data'])
            # 审计
            AuditLog.objects.create(
                user=advice.applied_by,
                action_type='update',
                object_type='StepRun',
                object_id=run.id,
                changes={'apply_advice': str(advice.id), 'patch': patch},
                metadata={'source': 'Advice.apply'}
            )
            return Response({'status': 'applied', 'run_params': run.params_json})
        return Response({'detail': 'Unsupported patch_type'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def rollback(self, request, pk=None):
        advice = self.get_object()
        run = advice.step_run
        data = advice.rollback_data or {}
        prev_params = data.get('prev_params')
        if not prev_params:
            return Response({'detail': 'No rollback data'}, status=status.HTTP_400_BAD_REQUEST)
        run.params_json = prev_params
        run.save(update_fields=['params_json'])
        advice.is_applied = False
        advice.save(update_fields=['is_applied'])
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action_type='rollback',
            object_type='StepRun',
            object_id=run.id,
            changes={'rollback_advice': str(advice.id)},
            metadata={'source': 'Advice.rollback'}
        )
        return Response({'status': 'rolled_back', 'run_params': run.params_json})

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]