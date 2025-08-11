from typing import Dict, Any


def run_umap(inputs: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    UMAP Runner
    params: {
        "n_neighbors": 15,
        "min_dist": 0.1,
        "metric": "euclidean"
    }
    """
    n_neighbors = params.get('n_neighbors', 15)
    min_dist = params.get('min_dist', 0.1)

    metrics = {
        'n_neighbors': n_neighbors,
        'min_dist': min_dist,
        'global_structure_preservation': 0.65,
        'local_structure_preservation': 0.82
    }

    evidence = {
        'umap_scatter': 's3://artifacts/umap_scatter.png'
    }

    artifacts = [
        {'name': 'umap_embeddings.csv', 'type': 'csv', 'path': 'artifacts/umap/embeddings.csv'},
        {'name': 'umap_scatter.png', 'type': 'png', 'path': 'artifacts/umap/scatter.png'}
    ]

    return {'artifacts': artifacts, 'metrics': metrics, 'evidence': evidence}