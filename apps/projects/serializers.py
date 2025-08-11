from rest_framework import serializers
from .models import Project, Sample, Step, StepRun, Artifact, Advice, AuditLog
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    owner_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='owner', write_only=True, required=False
    )

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'owner', 'owner_id', 'organization_id', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = ['id', 'project', 'name', 'sample_type', 'metadata',
                  'input_h5ad_path', 'input_mtx_path', 'input_features_path', 'input_barcodes_path',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class StepSerializer(serializers.ModelSerializer):
    class Meta:
        model = Step
        fields = ['id', 'name', 'step_type', 'description', 'runner_image', 'runner_command', 'default_params', 'created_at']
        read_only_fields = ['id', 'created_at']

class StepRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = StepRun
        fields = [
            'id', 'sample', 'step', 'status', 'params_json',
            'runner_image_tag', 'git_commit_hash', 'input_files_hash',
            'metrics_json', 'evidence_json',
            'created_at', 'started_at', 'finished_at',
            'parent_run', 'is_pinned'
        ]
        read_only_fields = ['id', 'created_at', 'started_at', 'finished_at', 'status']

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