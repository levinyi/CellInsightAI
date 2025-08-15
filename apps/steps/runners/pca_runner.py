import os
import tempfile
from typing import Dict, Any, List

import boto3
from botocore.client import Config
from django.conf import settings


def get_s3_client():
    """获取已配置的 S3/MinIO 客户端实例"""
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )


def download_from_s3(s3_path: str, local_path: str) -> None:
    """从 S3/MinIO 下载对象到本地文件"""
    s3 = get_s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    if s3_path.startswith('s3://'):
        key = s3_path.split('/', 3)[-1]
    else:
        key = s3_path
    s3.download_file(bucket, key, local_path)


def upload_to_s3(local_path: str, key: str, content_type: str = 'application/octet-stream') -> None:
    """上传本地文件到 S3/MinIO 指定 key"""
    s3 = get_s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    with open(local_path, 'rb') as f:
        s3.put_object(Bucket=bucket, Key=key, Body=f, ContentType=content_type)


def run_pca(inputs: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """PCA Runner: 读取输入H5AD，执行PCA，输出嵌入、scree图与更新后的H5AD

    Args:
        inputs: {'data_uri': <S3 key or s3://...>, 'step_run_id': str}
        params: {'n_components': int, 'svd_solver': str}

    Returns:
        dict with artifacts, metrics, evidence
    """
    try:
        import scanpy as sc
        import anndata as ad  # noqa: F401
        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
    except ImportError as e:
        return {'artifacts': [], 'metrics': {'error': f'Missing required packages: {str(e)}'}, 'evidence': {}}

    data_uri = inputs.get('data_uri')
    step_run_id = inputs.get('step_run_id', 'unknown')
    if not data_uri:
        return {'artifacts': [], 'metrics': {'error': 'PCA requires input H5AD: inputs["data_uri"] missing'}, 'evidence': {}}

    n_components = int((params or {}).get('n_components', 50))
    svd_solver = (params or {}).get('svd_solver', 'arpack')

    with tempfile.TemporaryDirectory() as tmpdir:
        in_local = os.path.join(tmpdir, 'input.h5ad')
        try:
            download_from_s3(data_uri, in_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to download input: {str(e)}'}, 'evidence': {}}

        try:
            adata = sc.read_h5ad(in_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to read H5AD: {str(e)}'}, 'evidence': {}}

        # 执行 PCA
        try:
            sc.pp.scale(adata, max_value=10)
        except Exception:
            pass
        try:
            sc.pp.pca(adata, n_comps=n_components, svd_solver=svd_solver)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to run PCA: {str(e)}'}, 'evidence': {}}

        # 解释方差比例
        var_ratio = None
        try:
            var_ratio = adata.uns['pca']['variance_ratio']  # type: ignore
        except Exception:
            var_ratio = None
        explained_sum = float(sum(var_ratio[:min(n_components, len(var_ratio))])) if var_ratio is not None else 0.0

        # Scree plot
        scree_local = os.path.join(tmpdir, 'pca_scree_plot.png')
        try:
            if var_ratio is not None:
                plt.figure(figsize=(6, 4))
                x = list(range(1, len(var_ratio) + 1))
                plt.plot(x, var_ratio, marker='o')
                plt.xlabel('PC')
                plt.ylabel('Explained Variance Ratio')
                plt.title('PCA Scree Plot')
                plt.tight_layout()
                plt.savefig(scree_local, dpi=300, bbox_inches='tight')
                plt.close()
        except Exception:
            scree_local = None

        # Embeddings CSV
        emb_local = os.path.join(tmpdir, 'pca_embeddings.csv')
        try:
            X_pca = adata.obsm.get('X_pca')
            if X_pca is None:
                raise ValueError('X_pca not found')
            df = pd.DataFrame(X_pca, index=adata.obs_names)
            df.columns = [f'PC{i+1}' for i in range(df.shape[1])]
            df.to_csv(emb_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to write PCA embeddings: {str(e)}'}, 'evidence': {}}

        # 写出更新后的H5AD
        out_local = os.path.join(tmpdir, 'pca_processed.h5ad')
        try:
            adata.write_h5ad(out_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to write output H5AD: {str(e)}'}, 'evidence': {}}

        # 上传
        scree_s3 = f'artifacts/{step_run_id}/pca_scree_plot.png' if scree_local else None
        emb_s3 = f'artifacts/{step_run_id}/pca_embeddings.csv'
        out_s3 = f'artifacts/{step_run_id}/pca_processed.h5ad'
        if scree_local:
            try:
                upload_to_s3(scree_local, scree_s3, 'image/png')
            except Exception:
                scree_s3 = None
        try:
            upload_to_s3(emb_local, emb_s3, 'text/csv')
            upload_to_s3(out_local, out_s3, 'application/octet-stream')
        except Exception:
            return {'artifacts': [], 'metrics': {'error': 'Failed to upload PCA artifacts'}, 'evidence': {}}

        # 顶级载荷（前两个PC）
        top_loadings: Dict[str, Dict[str, float]] = {}
        try:
            import numpy as np
            loadings = adata.varm.get('PCs')  # genes x comps
            if loadings is not None:
                genes = adata.var_names.tolist()
                for i in range(min(2, loadings.shape[1])):
                    comp = loadings[:, i]
                    idx = np.argsort(-np.abs(comp))[:10]
                    top_loadings[f'PC{i+1}'] = {genes[j]: float(comp[j]) for j in idx}
        except Exception:
            pass

        metrics = {
            'n_components': n_components,
            'explained_variance_ratio_sum': explained_sum,
            'top_pc_loadings': top_loadings
        }
        evidence = {
            'scree_plot': scree_s3,
            'summary': f'PCA computed with n_components={n_components}, explained variance sum={explained_sum:.3f}'
        }
        artifacts: List[Dict[str, Any]] = [
            {'name': 'pca_embeddings.csv', 'type': 'csv', 'path': emb_s3},
            {'name': 'pca_processed.h5ad', 'type': 'h5ad', 'path': out_s3},
        ]
        if scree_s3:
            artifacts.append({'name': 'pca_scree_plot.png', 'type': 'png', 'path': scree_s3})

        return {'artifacts': artifacts, 'metrics': metrics, 'evidence': evidence}