import uuid
from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Multi-tenant support
    organization_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return self.name

class Sample(models.Model):
    SAMPLE_TYPES = [
        ('single_cell', 'Single Cell'),
        ('bulk_rna', 'Bulk RNA'),
        ('spatial', 'Spatial'),
        ('multiome', 'Multiome'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='samples')
    name = models.CharField(max_length=255)
    sample_type = models.CharField(max_length=20, choices=SAMPLE_TYPES, default='single_cell')
    metadata = models.JSONField(default=dict, blank=True)
    
    # Input data references
    input_h5ad_path = models.CharField(max_length=500, blank=True, null=True)
    input_mtx_path = models.CharField(max_length=500, blank=True, null=True)
    input_features_path = models.CharField(max_length=500, blank=True, null=True)
    input_barcodes_path = models.CharField(max_length=500, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.project.name}/{self.name}"

class Step(models.Model):
    STEP_TYPES = [
        ('qc', 'Quality Control'),
        ('normalization', 'Normalization'),
        ('hvg', 'Highly Variable Genes'),
        ('pca', 'Principal Component Analysis'),
        ('umap', 'UMAP Embedding'),
        ('clustering', 'Clustering'),
        ('batch_correction', 'Batch Correction'),
        ('annotation', 'Cell Type Annotation'),
        ('differential', 'Differential Expression'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    step_type = models.CharField(max_length=20, choices=STEP_TYPES)
    description = models.TextField(blank=True)
    
    # Runner contract metadata
    runner_image = models.CharField(max_length=200, default='bioai/runner:latest')
    runner_command = models.TextField()
    default_params = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['step_type']
        
    def __str__(self):
        return f"{self.get_step_type_display()}"

class StepRun(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('SUCCEEDED', 'Succeeded'),
        ('FAILED', 'Failed'),
        ('CANCELED', 'Canceled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name='step_runs')
    step = models.ForeignKey(Step, on_delete=models.CASCADE)
    
    # Execution metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    params_json = models.JSONField(default=dict)
    
    # Versioning & reproducibility
    runner_image_tag = models.CharField(max_length=100, blank=True)
    git_commit_hash = models.CharField(max_length=40, blank=True)
    input_files_hash = models.CharField(max_length=64, blank=True)
    
    # Execution results
    metrics_json = models.JSONField(default=dict, blank=True)
    evidence_json = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    
    # Parent-child relationships for pipeline
    parent_run = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='child_runs')
    
    # Pinning & comparison
    is_pinned = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.sample.name}/{self.step.name} [{self.status}]"

class Artifact(models.Model):
    ARTIFACT_TYPES = [
        ('h5ad', 'AnnData H5AD'),
        ('csv', 'CSV Table'),
        ('png', 'PNG Image'),
        ('pdf', 'PDF Report'),
        ('json', 'JSON Data'),
        ('html', 'HTML Report'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step_run = models.ForeignKey(StepRun, on_delete=models.CASCADE, related_name='artifacts')
    
    name = models.CharField(max_length=255)
    artifact_type = models.CharField(max_length=20, choices=ARTIFACT_TYPES)
    file_path = models.CharField(max_length=500)  # S3/MinIO path
    file_size = models.BigIntegerField(default=0)
    file_hash = models.CharField(max_length=64, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.step_run}/{self.name}"

class Advice(models.Model):
    ADVICE_TYPES = [
        ('parameter_optimization', 'Parameter Optimization'),
        ('quality_improvement', 'Quality Improvement'),
        ('method_suggestion', 'Method Suggestion'),
        ('troubleshooting', 'Troubleshooting'),
    ]
    
    RISK_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step_run = models.ForeignKey(StepRun, on_delete=models.CASCADE, related_name='advice')
    
    advice_type = models.CharField(max_length=30, choices=ADVICE_TYPES)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='medium')
    
    # Content
    title = models.CharField(max_length=255)
    description = models.TextField()
    evidence_text = models.TextField()
    
    # Actionable patch
    patch_json = models.JSONField(default=dict, blank=True)  # Parameter/code changes
    patch_type = models.CharField(max_length=20, default='params')  # params|code|both
    
    # Application tracking
    is_applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(blank=True, null=True)
    applied_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    
    # Rollback support
    rollback_data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.step_run} - {self.title}"

class AuditLog(models.Model):
    ACTION_TYPES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('execute', 'Execute'),
        ('export', 'Export'),
        ('rollback', 'Rollback'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Who & When
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # What
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    object_type = models.CharField(max_length=50)  # Project, Sample, StepRun, etc.
    object_id = models.UUIDField()
    
    # Details
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Context
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.user} {self.action_type} {self.object_type} at {self.timestamp}"