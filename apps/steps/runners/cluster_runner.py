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


def run_cluster(inputs: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Clustering Runner: 基于邻接图/UMAP进行Leiden/Louvain聚类，输出cluster标签与可视化

    Args:
        inputs: {'data_uri': <S3 key or s3://...>, 'step_run_id': str}
        params: {'resolution': float, 'method': 'leiden'|'louvain'}

    Returns:
        dict with artifacts, metrics, evidence
    """
    try:
        import scanpy as sc
        import anndata as ad  # noqa: F401
        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError as e:
        return {'artifacts': [], 'metrics': {'error': f'Missing required packages: {str(e)}'}, 'evidence': {}}

    data_uri = inputs.get('data_uri')
    step_run_id = inputs.get('step_run_id', 'unknown')
    if not data_uri:
        return {'artifacts': [], 'metrics': {'error': 'Clustering requires input H5AD: inputs["data_uri"] missing'}, 'evidence': {}}

    resolution = float((params or {}).get('resolution', 1.0))
    method = (params or {}).get('method', 'leiden')

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

        # 准备邻接图
        try:
            if 'X_pca' not in adata.obsm:
                sc.pp.scale(adata, max_value=10)
                sc.pp.pca(adata, n_comps=50)
            if 'neighbors' not in adata.uns:
                sc.pp.neighbors(adata, n_neighbors=15, use_rep='X_pca')
        except Exception:
            pass

        # 聚类
        try:
            if method == 'louvain':
                sc.tl.louvain(adata, resolution=resolution)
                cluster_key = 'louvain'
            else:
                sc.tl.leiden(adata, resolution=resolution)
                cluster_key = 'leiden'
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to cluster: {str(e)}'}, 'evidence': {}}

        # 保存labels
        labels_local = os.path.join(tmpdir, 'cluster_labels.csv')
        try:
            labels = adata.obs[cluster_key].astype(str)
            labels.to_csv(labels_local, header=True)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to write labels: {str(e)}'}, 'evidence': {}}

        # 基于UMAP绘制带颜色的散点
        scatter_local = os.path.join(tmpdir, 'cluster_umap.png')
        try:
            if 'X_umap' not in adata.obsm:
                sc.tl.umap(adata)
            plt.figure(figsize=(6,5))
            cats = sorted(labels.unique())
            palette = sns.color_palette('tab20', n_colors=len(cats))
            color_map = {c: palette[i] for i, c in enumerate(cats)}
            colors = [color_map[v] for v in labels]
            plt.scatter(adata.obsm['X_umap'][:,0], adata.obsm['X_umap'][:,1], s=4, c=colors, alpha=0.8)
            plt.xlabel('UMAP1')
            plt.ylabel('UMAP2')
            plt.title(f'Clusters ({cluster_key})')
            plt.tight_layout()
            plt.savefig(scatter_local, dpi=300, bbox_inches='tight')
            plt.close()
        except Exception:
            scatter_local = None

        # 保存H5AD
        out_local = os.path.join(tmpdir, 'clustered.h5ad')
        try:
            adata.write_h5ad(out_local)
        except Exception as e:
            return {'artifacts': [], 'metrics': {'error': f'Failed to write output H5AD: {str(e)}'}, 'evidence': {}}

        # 上传
        labels_s3 = f'artifacts/{step_run_id}/cluster_labels.csv'
        out_s3 = f'artifacts/{step_run_id}/clustered.h5ad'
        scatter_s3 = f'artifacts/{step_run_id}/cluster_umap.png' if scatter_local else None
        try:
            upload_to_s3(labels_local, labels_s3, 'text/csv')
            upload_to_s3(out_local, out_s3, 'application/octet-stream')
            if scatter_local:
                upload_to_s3(scatter_local, scatter_s3, 'image/png')
        except Exception:
            return {'artifacts': [], 'metrics': {'error': 'Failed to upload cluster artifacts'}, 'evidence': {}}

        n_clusters = int(len(set(labels)))
        metrics = {
            'resolution': resolution,
            'method': method,
            'n_clusters': n_clusters
        }
        evidence = {
            'cluster_umap': scatter_s3,
            'summary': f'Clustering with {method} (resolution={resolution}) produced {n_clusters} clusters.'
        }
        artifacts: List[Dict[str, Any]] = [
            {'name': 'cluster_labels.csv', 'type': 'csv', 'path': labels_s3},
            {'name': 'clustered.h5ad', 'type': 'h5ad', 'path': out_s3},
        ]
        if scatter_s3:
            artifacts.append({'name': 'cluster_umap.png', 'type': 'png', 'path': scatter_s3})

        return {'artifacts': artifacts, 'metrics': metrics, 'evidence': evidence}