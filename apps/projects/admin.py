from django.contrib import admin
from .models import Project, Dataset, Session, Step, StepRun, Artifact, Advice, AuditLog

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'organization_id', 'created_at')
    search_fields = ('name', 'description', 'organization_id')

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'dataset_type', 'created_at')
    search_fields = ('name', 'project__name')
    list_filter = ('dataset_type',)

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'dataset', 'status', 'created_at', 'started_at', 'finished_at')
    list_filter = ('status',)
    search_fields = ('name', 'dataset__name')

@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display = ('step_type', 'name', 'runner_image')
    search_fields = ('name', 'step_type')
    list_filter = ('step_type',)

@admin.register(StepRun)
class StepRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'step', 'status', 'order_index', 'created_at', 'started_at', 'finished_at', 'is_pinned')
    list_filter = ('status', 'is_pinned')
    search_fields = ('id', 'session__name', 'step__name')

@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ('name', 'artifact_type', 'step_run', 'file_size', 'created_at')
    list_filter = ('artifact_type',)
    search_fields = ('name', 'step_run__id')

@admin.register(Advice)
class AdviceAdmin(admin.ModelAdmin):
    list_display = ('title', 'advice_type', 'risk_level', 'step_run', 'is_applied', 'created_at')
    list_filter = ('advice_type', 'risk_level', 'is_applied')
    search_fields = ('title', 'step_run__id')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action_type', 'object_type', 'object_id')
    list_filter = ('action_type', 'object_type')
    search_fields = ('user__username', 'object_type', 'object_id')