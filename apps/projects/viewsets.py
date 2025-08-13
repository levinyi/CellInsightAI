from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Project, Dataset, Session, Step, StepRun, Artifact, Advice, AuditLog
from .serializers import (
    ProjectSerializer, DatasetSerializer, SessionSerializer, StepSerializer, StepRunSerializer,
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

class DatasetViewSet(viewsets.ModelViewSet):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        """Return datasets within current org, with optional filters.
        Supported query params:
        - q: search in name or notes (icontains)
        - tags: comma-separated tags, requires all
        - created_after / created_before: ISO datetime range
        - project: filter by project id (exact)
        """
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            qs = qs.filter(project__organization_id=str(profile.organization.id))
        # Filters: q (name or notes), tags (comma-separated), created_before/after
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(notes__icontains=q))
        tags = self.request.query_params.get('tags')
        if tags:
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            for t in tag_list:
                qs = qs.filter(tags__contains=[t])
        created_after = self.request.query_params.get('created_after')
        created_before = self.request.query_params.get('created_before')
        if created_after:
            qs = qs.filter(created_at__gte=created_after)
        if created_before:
            qs = qs.filter(created_at__lte=created_before)
        # New: filter by project id if provided
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.select_related('dataset', 'current_step').all()
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        """Return sessions within current org, with optional filters.
        Supported query params:
        - q: search in name or description
        - status: session status exact
        - tags: comma-separated tags, requires all
        - created_after / created_before: ISO datetime range
        - dataset: filter by dataset id (exact)
        - project: filter by project id (exact, filtering through dataset)
        """
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            qs = qs.filter(dataset__project__organization_id=str(profile.organization.id))
        # Filters: q (name/description), tags, status, created_before/after
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        status_q = self.request.query_params.get('status')
        if status_q:
            qs = qs.filter(status=status_q)
        tags = self.request.query_params.get('tags')
        if tags:
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            for t in tag_list:
                qs = qs.filter(tags__contains=[t])
        created_after = self.request.query_params.get('created_after')
        created_before = self.request.query_params.get('created_before')
        if created_after:
            qs = qs.filter(created_at__gte=created_after)
        if created_before:
            qs = qs.filter(created_at__lte=created_before)
        # Filter by dataset id if provided
        dataset_id = self.request.query_params.get('dataset')
        if dataset_id:
            qs = qs.filter(dataset_id=dataset_id)
        # New: filter by project id if provided (through dataset)
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(dataset__project_id=project_id)
        return qs

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        session = self.get_object()
        session.status = 'PAUSED'
        session.save(update_fields=['status'])
        return Response({'status': 'paused'})

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        session = self.get_object()
        session.status = 'RUNNING'
        session.last_active_at = timezone.now()
        session.save(update_fields=['status', 'last_active_at'])
        return Response({'status': 'running'})

    @action(detail=True, methods=['get'])
    def latest_state(self, request, pk=None):
        """获取会话最新一步的状态与参数，用于“继续分析”恢复现场"""
        session = self.get_object()
        last_run = session.step_runs.order_by('-created_at').first()
        if not last_run:
            return Response({'detail': 'no runs yet', 'session': SessionSerializer(session).data})
        data = {
            'session': SessionSerializer(session).data,
            'last_run': StepRunSerializer(last_run).data,
        }
        return Response(data)

    @action(detail=True, methods=['post'])
    def fork(self, request, pk=None):
        """从当前会话分支复制为新会话（参数拷贝 + 下游清空）"""
        session = self.get_object()
        new_name = request.data.get('name') or f"{session.name}_fork"
        new_session = Session.objects.create(
            dataset=session.dataset,
            name=new_name,
            description=session.description,
            tags=session.tags,
            status='PAUSED',
            parent_session=session,
        )
        return Response(SessionSerializer(new_session).data, status=status.HTTP_201_CREATED)

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
    queryset = StepRun.objects.all().select_related('session', 'step')
    serializer_class = StepRunSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            qs = qs.filter(session__dataset__project__organization_id=str(profile.organization.id))
        # Filters: step_type, status, pinned, since
        step_type = self.request.query_params.get('step_type')
        if step_type:
            qs = qs.filter(step__step_type=step_type)
        status_q = self.request.query_params.get('status')
        if status_q:
            qs = qs.filter(status=status_q)
        pinned = self.request.query_params.get('pinned')
        if pinned in ('true', '1', 'yes'):
            qs = qs.filter(is_pinned=True)
        since = self.request.query_params.get('since')
        if since:
            qs = qs.filter(created_at__gte=since)
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

    @action(detail=True, methods=['post'])
    def fork_session(self, request, pk=None):
        """从某一步复制为新会话：拷贝该步的参数到新会话首步，保留溯源，不污染原会话"""
        run = self.get_object()
        base_session = run.session
        new_name = request.data.get('name') or f"{base_session.name}_from_{run.step.step_type}"
        # 创建新会话
        new_session = Session.objects.create(
            dataset=base_session.dataset,
            name=new_name,
            description=base_session.description,
            tags=base_session.tags,
            status='PAUSED',
            parent_session=base_session,
        )
        # 复制一步（参数拷贝，下游清空，这里仅创建第一步）
        StepRun.objects.create(
            session=new_session,
            step=run.step,
            params_json=run.params_json,
            status='PENDING',
            order_index=0,
            parent_run=None,
        )
        return Response(SessionSerializer(new_session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """快速回看与导出：聚合该步参数/指标/产物，返回 JSON 供前端渲染或导出报告"""
        run = self.get_object()
        artifacts = Artifact.objects.filter(step_run=run).order_by('-created_at')
        payload = {
            'run': StepRunSerializer(run).data,
            'artifacts': ArtifactSerializer(artifacts, many=True).data,
        }
        # 审计
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action_type='export',
            object_type='StepRun',
            object_id=run.id,
            changes={},
            metadata={'source': 'StepRun.export'}
        )
        return Response(payload)

class ArtifactViewSet(viewsets.ModelViewSet):
    queryset = Artifact.objects.all()
    serializer_class = ArtifactSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            return qs.filter(step_run__session__dataset__project__organization_id=str(profile.organization.id))
        return qs

class AdviceViewSet(viewsets.ModelViewSet):
    queryset = Advice.objects.all()
    serializer_class = AdviceSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, RBACByRole]

    def get_queryset(self):
        qs = super().get_queryset()
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.organization:
            return qs.filter(step_run__session__dataset__project__organization_id=str(profile.organization.id))
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