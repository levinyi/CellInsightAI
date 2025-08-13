from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Project, Dataset, Session, Step, StepRun, Artifact, Advice, AuditLog


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email']


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'owner', 'created_at', 'updated_at', 'organization_id', 'tags', 'notes']
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at', 'organization_id']


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = [
            'id', 'project', 'name', 'dataset_type', 'metadata',
            'input_h5ad_path', 'input_mtx_path', 'input_features_path', 'input_barcodes_path',
            'tags', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StepSerializer(serializers.ModelSerializer):
    class Meta:
        model = Step
        fields = ['id', 'name', 'step_type', 'description', 'runner_image', 'runner_command', 'default_params', 'created_at']
        read_only_fields = ['id', 'created_at']


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = [
            'id', 'dataset', 'name', 'description', 'tags', 'status', 'current_step',
            'parent_session', 'created_at', 'started_at', 'finished_at', 'last_active_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'started_at', 'finished_at', 'last_active_at']


class StepRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepRun
        fields = [
            'id', 'session', 'step', 'status', 'params_json', 'order_index',
            'runner_image_tag', 'git_commit_hash', 'input_files_hash',
            'metrics_json', 'evidence_json', 'created_at', 'started_at', 'finished_at', 'is_pinned'
        ]
        read_only_fields = ['id', 'status', 'metrics_json', 'evidence_json', 'created_at', 'started_at', 'finished_at']


class ArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artifact
        fields = ['id', 'step_run', 'name', 'artifact_type', 'file_path', 'file_size', 'file_hash', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']


class AdviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advice
        fields = [
            'id', 'step_run', 'advice_type', 'risk_level', 'title', 'description', 'evidence_text',
            'patch_json', 'patch_type', 'is_applied', 'applied_at', 'applied_by', 'rollback_data', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'timestamp', 'action_type', 'object_type', 'object_id', 'changes', 'metadata', 'ip_address', 'user_agent']
        read_only_fields = ['id', 'timestamp']