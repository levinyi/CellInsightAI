from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.projects'
    verbose_name = 'Projects & Analysis'

    def ready(self):
        # Lazy import to avoid AppRegistryNotReady
        try:
            from django.db.utils import OperationalError, ProgrammingError
            from .models import Step
            default_steps = [
                {
                    'step_type': 'qc',
                    'name': 'Quality Control',
                    'description': 'Filter cells/genes, compute mito/ribo metrics',
                    'runner_image': 'bioai/runner:latest',
                    'runner_command': 'python run_qc.py --params ${params_json}',
                    'default_params': {'min_genes': 200, 'max_genes': 5000, 'max_mito': 10},
                },
                {
                    'step_type': 'hvg',
                    'name': 'Highly Variable Genes',
                    'description': 'Detect highly variable genes',
                    'runner_image': 'bioai/runner:latest',
                    'runner_command': 'python run_hvg.py --params ${params_json}',
                    'default_params': {'method': 'seurat_v3', 'n_top_genes': 2000},
                },
                {
                    'step_type': 'pca',
                    'name': 'PCA',
                    'description': 'Reduce dimensionality',
                    'runner_image': 'bioai/runner:latest',
                    'runner_command': 'python run_pca.py --params ${params_json}',
                    'default_params': {'n_pcs': 30},
                },
                {
                    'step_type': 'umap',
                    'name': 'UMAP',
                    'description': '2D embedding',
                    'runner_image': 'bioai/runner:latest',
                    'runner_command': 'python run_umap.py --params ${params_json}',
                    'default_params': {'min_dist': 0.3},
                },
                {
                    'step_type': 'clustering',
                    'name': 'Clustering',
                    'description': 'Leiden clustering',
                    'runner_image': 'bioai/runner:latest',
                    'runner_command': 'python run_cluster.py --params ${params_json}',
                    'default_params': {'resolution': 0.8},
                },
            ]
            # Seed only when table exists and empty
            if Step.objects.count() == 0:
                Step.objects.bulk_create([Step(**s) for s in default_steps])
        except (OperationalError, ProgrammingError):
            # Database not ready or table missing during migration/collectstatic
            pass
        except Exception:
            # Avoid crashing app on seeding issues
            pass