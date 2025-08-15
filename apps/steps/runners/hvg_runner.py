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
    """从 S3/MinIO 下载对象到本地文件

    Args:
        s3_path: 可以是完整的 s3://bucket/key 或仅 key
        local_path: 本地保存路径
    """
    s3 = get_s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    # 兼容 s3://bucket/key 与 纯 key
    if s3_path.startswith('s3://'):
        key = s3_path.split('/', 3)[-1]
    else:
        key = s3_path
    s3.download_file(bucket, key, local_path)


def upload_to_s3(local_path: str, key: str, content_type: str = 'application/octet-stream') -> None:
    """上传本地文件到 S3/MinIO 指定 key

    Args:
        local_path: 本地文件路径
        key: 目标对象 key（不要带 s3:// 前缀）
        content_type: MIME 类型
    """
    s3 = get_s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    with open(local_path, 'rb') as f:
        s3.put_object(Bucket=bucket, Key=key, Body=f, ContentType=content_type)


def run_hvg(inputs: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """高变基因（HVG）选择 Runner

    输入:
        inputs: 包含数据输入与上下文信息，如 { 'data_uri': <S3 key 或 s3://>, 'step_run_id': <ID> }
        params: HVG 参数，例如 {
            'method': 'seurat_v3|pearson|cell_ranger',
            'n_top_genes': 2000,
            'batch_key': Optional[str]
        }

    返回:
        {'artifacts': List[dict], 'metrics': dict, 'evidence': dict}
        - artifacts: 每个包含 {name, type, path}，其中 path 为 S3/MinIO key
        - metrics: 至少包含 n_hvgs 与 method
        - evidence: 包含可视化/说明性信息
    """
    try:
        import scanpy as sc
        import anndata as ad  # noqa: F401  # 仅确保依赖存在
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
    except ImportError as e:
        return {
            'artifacts': [],
            'metrics': {'error': f'Missing required packages: {str(e)}'},
            'evidence': {}
        }

    data_uri = inputs.get('data_uri')
    step_run_id = inputs.get('step_run_id', 'unknown')
    if not data_uri:
        return {
            'artifacts': [],
            'metrics': {'error': 'HVG requires input H5AD: inputs["data_uri"] missing'},
            'evidence': {}
        }

    method = (params or {}).get('method', 'seurat_v3')
    n_top_genes = int((params or {}).get('n_top_genes', 2000))
    batch_key = (params or {}).get('batch_key')

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1) 下载输入数据
        local_in = os.path.join(tmpdir, 'input.h5ad')
        try:
            download_from_s3(data_uri, local_in)
        except Exception as e:
            return {
                'artifacts': [],
                'metrics': {'error': f'Failed to download input: {str(e)}'},
                'evidence': {}
            }

        # 2) 读取数据
        try:
            adata = sc.read_h5ad(local_in)
        except Exception as e:
            return {
                'artifacts': [],
                'metrics': {'error': f'Failed to read H5AD: {str(e)}'},
                'evidence': {}
            }

        # 3) 计算 HVG
        method_used = method
        try:
            if method == 'pearson':
                # 优先尝试 experimental pearson residuals；失败则回退 seurat_v3
                try:
                    from scanpy.experimental.pp import highly_variable_genes as hvg_pearson  # type: ignore
                    hvg_pearson(adata, flavor='pearson_residuals', n_top_genes=n_top_genes, batch_key=batch_key)
                    method_used = 'pearson'
                except Exception:
                    sc.pp.highly_variable_genes(adata, flavor='seurat_v3', n_top_genes=n_top_genes, batch_key=batch_key)
                    method_used = 'seurat_v3'
            elif method in {'seurat_v3', 'seurat', 'cell_ranger'}:
                sc.pp.highly_variable_genes(adata, flavor=method, n_top_genes=n_top_genes, batch_key=batch_key)
            else:
                sc.pp.highly_variable_genes(adata, flavor='seurat_v3', n_top_genes=n_top_genes, batch_key=batch_key)
                method_used = 'seurat_v3'
        except Exception as e:
            return {
                'artifacts': [],
                'metrics': {'error': f'Failed to compute HVGs: {str(e)}'},
                'evidence': {}
            }

        # 4) 收集结果
        hv_mask = adata.var['highly_variable'] if 'highly_variable' in adata.var.columns else None
        hv_genes: List[str] = adata.var_names[hv_mask].tolist() if hv_mask is not None else []
        n_hvgs = len(hv_genes)

        # 排名信息
        rank_col = 'highly_variable_rank' if 'highly_variable_rank' in adata.var.columns else None
        means_col = 'means' if 'means' in adata.var.columns else None
        disp_col = None
        for c in ['dispersions_norm', 'variances_norm', 'dispersions', 'variances']:
            if c in adata.var.columns:
                disp_col = c
                break

        # 5) 可视化：均值-离散度散点，突出HVG
        hvg_plot_local = os.path.join(tmpdir, 'hvg_plot.png')
        try:
            if means_col and disp_col:
                plt.figure(figsize=(6, 5))
                x = adata.var[means_col]
                y = adata.var[disp_col]
                plt.scatter(x, y, s=6, c='lightgray', alpha=0.6, label='Genes')
                if hv_mask is not None and hv_mask.any():
                    plt.scatter(x[hv_mask], y[hv_mask], s=8, c='red', alpha=0.8, label='HVGs')
                plt.xlabel('Mean Expression')
                plt.ylabel(disp_col)
                plt.title(f'HVG selection ({method_used})')
                plt.legend()
                plt.tight_layout()
                plt.savefig(hvg_plot_local, dpi=300, bbox_inches='tight')
                plt.close()
            else:
                # 兜底：仅画 HVG 数量条形图
                plt.figure(figsize=(4, 3))
                plt.bar(['HVGs', 'Others'], [n_hvgs, max(0, adata.n_vars - n_hvgs)], color=['red', 'lightgray'])
                plt.ylabel('Gene Count')
                plt.title(f'HVG selection ({method_used})')
                plt.tight_layout()
                plt.savefig(hvg_plot_local, dpi=300, bbox_inches='tight')
                plt.close()
        except Exception:
            # 忽略绘图错误，不阻断流程
            hvg_plot_local = None

        # 6) 保存基因列表与排名
        genes_csv_local = os.path.join(tmpdir, 'hvg_genes.csv')
        ranking_csv_local = os.path.join(tmpdir, 'hvg_ranking.csv')
        try:
            pd.Series(hv_genes, name='gene').to_csv(genes_csv_local, index=False)
            # 排名表：若无 rank 列，按是否HVG排序
            df_rank = adata.var.copy()
            df_rank = df_rank.reset_index().rename(columns={'index': 'gene'})
            if rank_col is None:
                df_rank['highly_variable_rank'] = (~df_rank['highly_variable']).astype(int)  # HVG优先
            df_rank[['gene', 'highly_variable', 'highly_variable_rank']].sort_values(
                by=['highly_variable', 'highly_variable_rank'], ascending=[False, True]
            ).to_csv(ranking_csv_local, index=False)
        except Exception:
            # 允许排名文件失败，不影响主流程
            ranking_csv_local = None

        # 7) 写出更新后的 H5AD（保留 HVG 标记供下游步骤使用）
        out_h5ad_local = os.path.join(tmpdir, 'hvg_processed.h5ad')
        try:
            adata.write_h5ad(out_h5ad_local)
        except Exception as e:
            return {
                'artifacts': [],
                'metrics': {'error': f'Failed to write output H5AD: {str(e)}'},
                'evidence': {}
            }

        # 8) 上传产物到 S3
        hvg_plot_s3 = f'artifacts/{step_run_id}/hvg_plot.png' if hvg_plot_local else None
        genes_csv_s3 = f'artifacts/{step_run_id}/hvg_genes.csv'
        ranking_csv_s3 = f'artifacts/{step_run_id}/hvg_ranking.csv' if ranking_csv_local else None
        out_h5ad_s3 = f'artifacts/{step_run_id}/hvg_processed.h5ad'

        if hvg_plot_local:
            try:
                upload_to_s3(hvg_plot_local, hvg_plot_s3, 'image/png')
            except Exception:
                hvg_plot_s3 = None
        try:
            upload_to_s3(genes_csv_local, genes_csv_s3, 'text/csv')
        except Exception:
            return {
                'artifacts': [],
                'metrics': {'error': 'Failed to upload HVG genes csv'},
                'evidence': {}
            }
        if ranking_csv_local:
            try:
                upload_to_s3(ranking_csv_local, ranking_csv_s3, 'text/csv')
            except Exception:
                ranking_csv_s3 = None
        try:
            upload_to_s3(out_h5ad_local, out_h5ad_s3, 'application/octet-stream')
        except Exception:
            return {
                'artifacts': [],
                'metrics': {'error': 'Failed to upload output H5AD'},
                'evidence': {}
            }

        # 9) 汇总返回
        metrics = {
            'n_hvgs': int(n_hvgs),
            'method': method_used,
            'top_hvg_genes': hv_genes[:min(50, len(hv_genes))]
        }
        evidence = {
            'hvg_plot': hvg_plot_s3,
            'gene_ranking': ranking_csv_s3,
            'summary': f'Selected {n_hvgs} HVGs using {method_used} (n_top_genes={n_top_genes})'
        }
        artifacts: List[Dict[str, Any]] = [
            {'name': 'hvg_genes.csv', 'type': 'csv', 'path': genes_csv_s3},
            {'name': 'hvg_processed.h5ad', 'type': 'h5ad', 'path': out_h5ad_s3},
        ]
        if hvg_plot_s3:
            artifacts.append({'name': 'hvg_plot.png', 'type': 'png', 'path': hvg_plot_s3})
        if ranking_csv_s3:
            artifacts.append({'name': 'hvg_ranking.csv', 'type': 'csv', 'path': ranking_csv_s3})

        return {
            'artifacts': artifacts,
            'metrics': metrics,
            'evidence': evidence
        }