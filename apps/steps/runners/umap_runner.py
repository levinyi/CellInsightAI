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


def run_umap(inputs: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """UMAP Runner: 读取输入H5AD，基于PCA执行UMAP，输出嵌入与散点图

    Args:
        inputs: {'data_uri': <S3 key or s3://...>, 'step_run_id': str}
        params: {'n_neighbors': int, 'min_dist': float, 'metric': str}
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
        return {'artifacts': [], 'metrics': {'error': 'UMAP requires input H5AD: inputs["data_uri"] missing'}, 'evidence': {}}

    n_neighbors = int((params or {}).get('n_neighbors', 15))
    min_dist = float((params or {}).get('min_dist', 0.1))
    metric = (params or {}).get('metric', 'euclidean')

    with tempfile.TemporaryDirectory() as tmpdir:
        in_local = os.path.join(tmpdir, 'input.h5ad')
        try:
            download_from_s3(data_uri, in_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to download input: {str(e)}'}, 'evidence': {}}

        try:
            sc.settings.verbosity = 0
            adata = sc.read_h5ad(in_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to read H5AD: {str(e)}'}, 'evidence': {}}

        # 如果没有 PCA，自动运行 PCA
        try:
            if 'X_pca' not in adata.obsm:
                sc.pp.scale(adata, max_value=10)
                sc.pp.pca(adata, n_comps=50)
        except Exception:
            pass

        # 邻接图与 UMAP
        try:
            sc.pp.neighbors(adata, n_neighbors=n_neighbors, use_rep='X_pca', metric=metric)
            sc.tl.umap(adata, min_dist=min_dist)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to compute UMAP: {str(e)}'}, 'evidence': {}}

        # 保存嵌入
        emb_local = os.path.join(tmpdir, 'umap_embeddings.csv')
        try:
            X_umap = adata.obsm.get('X_umap')
            if X_umap is None:
                raise ValueError('X_umap not found')
            df = pd.DataFrame(X_umap, index=adata.obs_names, columns=['UMAP1', 'UMAP2'])
            df.to_csv(emb_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to write UMAP embeddings: {str(e)}'}, 'evidence': {}}

        # 绘制散点
        scatter_local = os.path.join(tmpdir, 'umap_scatter.png')
        try:
            plt.figure(figsize=(6, 5))
            plt.scatter(adata.obsm['X_umap'][:, 0], adata.obsm['X_umap'][:, 1], s=4, c='steelblue', alpha=0.7)
            plt.xlabel('UMAP1')
            plt.ylabel('UMAP2')
            plt.title('UMAP Embedding')
            plt.tight_layout()
            plt.savefig(scatter_local, dpi=300, bbox_inches='tight')
            plt.close()
        except Exception:
            scatter_local = None

        # 保存H5AD
        out_local = os.path.join(tmpdir, 'umap_processed.h5ad')
        try:
            adata.write_h5ad(out_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to write output H5AD: {str(e)}'}, 'evidence': {}}

        # 上传
        emb_s3 = f'artifacts/{step_run_id}/umap_embeddings.csv'
        out_s3 = f'artifacts/{step_run_id}/umap_processed.h5ad'
        scatter_s3 = f'artifacts/{step_run_id}/umap_scatter.png' if scatter_local else None
        try:
            upload_to_s3(emb_local, emb_s3, 'text/csv')
            upload_to_s3(out_local, out_s3, 'application/octet-stream')
            if scatter_local:
                upload_to_s3(scatter_local, scatter_s3, 'image/png')
        except Exception:
            return {'artifacts': [], 'metrics': {'error': 'Failed to upload UMAP artifacts'}, 'evidence': {}}

        metrics = {
            'n_neighbors': n_neighbors,
            'min_dist': min_dist
        }
        evidence = {
            'umap_scatter': scatter_s3,
            'summary': f'UMAP computed with n_neighbors={n_neighbors}, min_dist={min_dist}'
        }
        artifacts: List[Dict[str, Any]] = [
            {'name': 'umap_embeddings.csv', 'type': 'csv', 'path': emb_s3},
            {'name': 'umap_processed.h5ad', 'type': 'h5ad', 'path': out_s3},
        ]
        if scatter_s3:
            artifacts.append({'name': 'umap_scatter.png', 'type': 'png', 'path': scatter_s3})

        return {'artifacts': artifacts, 'metrics': metrics, 'evidence': evidence}