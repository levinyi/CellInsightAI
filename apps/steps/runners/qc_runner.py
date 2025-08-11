import json
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RunnerIO:
    inputs: Dict[str, Any]
    params: Dict[str, Any]


def run_qc(inputs: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runner契约：
      - inputs.json: {"data_uri": "s3://.../sample.h5ad"}
      - params.json: {"min_genes": 200, "max_genes": 5000, "max_mito": 0.1}
      - outputs: {"artifacts":[], "metrics":{}, "evidence":{}}
    这里示例化实现：仅加载AnnData并计算基础QC指标（模拟）。
    注意：为避免依赖未安装导致导入失败，不在模块顶层导入scanpy/anndata。
    """
    # 如需真实计算，可在此处尝试导入，失败则继续使用模拟
    try:
        import scanpy as sc  # noqa: F401
        import anndata as ad  # noqa: F401
    except Exception:
        pass

    # 简化：仅返回模拟指标
    min_genes = params.get('min_genes', 200)
    max_genes = params.get('max_genes', 5000)
    max_mito = params.get('max_mito', 0.1)

    metrics = {
        'cells': 10000,
        'doublet_rate': 0.03,
        'high_mito': 0.08,
        'filters': {
            'min_genes': min_genes,
            'max_genes': max_genes,
            'max_mito': max_mito
        }
    }
    evidence = {
        'hist_mito': 's3://placeholder/mito_hist.png'
    }
    artifacts = [
        {'name': 'qc_metrics.json', 'type': 'json', 'path': 'artifacts/qc/metrics.json'}
    ]
    return {'artifacts': artifacts, 'metrics': metrics, 'evidence': evidence}