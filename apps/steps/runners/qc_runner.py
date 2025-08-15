import json
import os
import tempfile
import boto3
from botocore.client import Config
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
import zipfile
import tarfile
import shutil
import gzip
try:
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
except Exception:
    np = None
    plt = None
    sns = None
from django.conf import settings


@dataclass
class RunnerIO:
    inputs: Dict[str, Any]
    params: Dict[str, Any]


def get_s3_client():
    """获取S3客户端实例"""
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )


def download_from_s3(s3_path: str, local_path: str):
    """从S3下载文件到本地"""
    s3 = get_s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    # 移除s3://bucket_name前缀，获取纯key
    if s3_path.startswith('s3://'):
        key = s3_path.split('/', 3)[-1]  # s3://bucket/path -> path
    else:
        key = s3_path
    s3.download_file(bucket, key, local_path)


def upload_to_s3(local_path: str, s3_path: str, content_type: str = 'application/octet-stream'):
    """上传本地文件到S3"""
    s3 = get_s3_client()
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    with open(local_path, 'rb') as f:
        s3.put_object(Bucket=bucket, Key=s3_path, Body=f, ContentType=content_type)


# ========= 新增：输入文件有效性校验工具 =========
def _sniff_file_type(local_path: str) -> str:
    """根据文件头、扩展名做简单类型嗅探，返回类型标签
    可能返回：'hdf5', 'gzip', 'zip', 'json', 'html', 'text', 'unknown'
    """
    try:
        size = os.path.getsize(local_path)
        if size == 0:
            return 'empty'
        with open(local_path, 'rb') as f:
            head = f.read(16)
        # HDF5 标志
        if head.startswith(b'\x89HDF\r\n\x1a\n'):
            return 'hdf5'
        # gzip
        if head.startswith(b'\x1f\x8b'):
            return 'gzip'
        # zip
        if head.startswith(b'PK'):  # PK\x03\x04
            return 'zip'
        # 文本/JSON/HTML 粗略判断
        try:
            text = head.decode('utf-8', errors='ignore').strip().lower()
            if text.startswith('{') or text.startswith('['):
                return 'json'
            if '<html' in text or '<!doctype html' in text:
                return 'html'
            # 某些小文本
            return 'text'
        except Exception:
            return 'unknown'
    except Exception:
        return 'unknown'


def _validate_h5ad_file(local_path: str) -> Tuple[bool, str]:
    """验证本地文件是否为有效的 H5AD(HDF5) 文件
    返回 (ok, reason)，当 ok=False 时，reason 为可读错误原因。
    """
    try:
        if not os.path.exists(local_path):
            return False, 'file not found'
        size = os.path.getsize(local_path)
        if size < 16:
            return False, f'file too small (size={size} bytes)'
        ftype = _sniff_file_type(local_path)
        if ftype == 'hdf5':
            # 进一步用 h5py 打开以确保结构完整
            try:
                import h5py  # anndata 依赖里一般会带上 h5py
                with h5py.File(local_path, 'r'):
                    pass
                return True, ''
            except Exception as e:
                return False, f'HDF5 open failed: {e}'
        # 非 HDF5 的常见情况给出指引
        if ftype in {'gzip', 'zip'}:
            return False, f'not an HDF5 file, detected {ftype}. If this is a 10x archive, please convert to .h5ad first.'
        if ftype in {'json', 'html', 'text', 'empty'}:
            return False, f'not an HDF5 file, detected {ftype}'
        return False, f'unknown file type'
    except Exception as e:
        return False, f'validation exception: {e}'


def _extract_archive(archive_path: str, extract_dir: str) -> Tuple[bool, str, str]:
    """解压压缩包到指定目录并返回根目录
    
    支持格式：zip、tar、tar.gz、tgz、单文件 .gz（将解压为同名文件）
    
    Args:
        archive_path: 本地压缩文件路径
        extract_dir: 解压目标目录
    
    Returns:
        (ok, reason, root_dir)，ok 为 False 时 reason 包含错误原因；
        root_dir 为解压后的根目录（通常即 extract_dir）。
    """
    try:
        os.makedirs(extract_dir, exist_ok=True)
        # ZIP
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(extract_dir)
            return True, '', extract_dir
        # TAR (包含 .tar.gz/.tgz)
        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(extract_dir)
            return True, '', extract_dir
        # 单文件 GZIP (.gz) —— 解压为同名文件
        # 例如 input.h5ad.gz -> extract_dir/input.h5ad
        if archive_path.endswith('.gz'):
            out_name = os.path.basename(archive_path)[:-3]
            out_path = os.path.join(extract_dir, out_name)
            with gzip.open(archive_path, 'rb') as gf, open(out_path, 'wb') as out:
                shutil.copyfileobj(gf, out)
            return True, '', extract_dir
        return False, 'unsupported archive format', ''
    except Exception as e:
        return False, f'archive extract failed: {e}', ''


def _find_10x_mtx_dir(base_dir: str) -> Optional[str]:
    """在目录树中查找10x三文件目录（matrix.mtx[.gz], barcodes.tsv[.gz], features.tsv[.gz] 或 genes.tsv[.gz]）
    
    Args:
        base_dir: 搜索的根目录
    
    Returns:
        匹配的目录路径或 None
    """
    candidates_mtx = {'matrix.mtx', 'matrix.mtx.gz'}
    candidates_bc = {'barcodes.tsv', 'barcodes.tsv.gz'}
    candidates_feat = {'features.tsv', 'features.tsv.gz', 'genes.tsv', 'genes.tsv.gz'}
    for root, dirs, files in os.walk(base_dir):
        file_set = set(files)
        if (file_set & candidates_mtx) and (file_set & candidates_bc) and (file_set & candidates_feat):
            return root
    return None


def run_qc(inputs: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    QC (Quality Control) 数据质量控制分析
    
    Args:
        inputs: 输入数据路径字典，包含 'data_uri' 键指向H5AD文件或压缩包/10x目录
        params: QC参数字典，包含过滤阈值等参数
    
    Returns:
        包含artifacts、metrics和evidence的字典
    """
    # 先检查本模块容错导入的依赖是否可用
    if (np is None) or (plt is None):
        return {
            'artifacts': [],
            'metrics': {'error': 'Missing required packages: numpy and/or matplotlib (and seaborn) not installed'},
            'evidence': {}
        }

    try:
        import scanpy as sc
        import anndata as ad
        import pandas as pd
    except ImportError as e:
        return {
            'artifacts': [],
            'metrics': {'error': f'Missing required packages: {str(e)}'},
            'evidence': {}
        }
    
    # 获取输入参数
    data_uri = inputs.get('data_uri')
    if not data_uri:
        return {
            'artifacts': [],
            'metrics': {'error': 'Missing data_uri in inputs'},
            'evidence': {}
        }
    
    # QC参数
    min_genes = params.get('min_genes', 200)  # 每个细胞最少基因数
    max_genes = params.get('max_genes', 5000)  # 每个细胞最多基因数  
    min_cells = params.get('min_cells', 3)    # 每个基因最少细胞数
    max_mito = params.get('max_mito', 0.20)   # 线粒体基因比例上限
    max_ribo = params.get('max_ribo', 1.0)    # 核糖体基因比例上限
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 下载数据文件
        local_path = os.path.join(tmpdir, 'input.data')
        try:
            download_from_s3(data_uri, local_path)
        except Exception as e:
            return {
                'artifacts': [],
                'metrics': {'error': f'Failed to download data: {str(e)}'},
                'evidence': {}
            }
        
        # 嗅探类型并按类型处理
        ftype = _sniff_file_type(local_path)
        adata = None
        tenx_dir = None
        
        if ftype == 'hdf5':
            # 可能是h5ad或10x h5，先用h5py校验
            ok, reason = _validate_h5ad_file(local_path)
            if not ok:
                try:
                    size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
                    with open(local_path, 'rb') as f:
                        head = f.read(16)
                    head_hex = head.hex(' ') if head else ''
                except Exception:
                    size, head_hex = 0, ''
                return {
                    'artifacts': [],
                    'metrics': {
                        'error': f'Invalid HDF5 container: {reason}; size={size} bytes; head={head_hex}; source={data_uri}',
                        'cells': 0
                    },
                    'evidence': {}
                }
            # 先尝试按h5ad读取，失败则回退为10x h5
            try:
                adata = ad.read_h5ad(local_path)
            except Exception:
                try:
                    adata = sc.read_10x_h5(local_path)
                except Exception as e2:
                    return {
                        'artifacts': [],
                        'metrics': {'error': f'Failed to load HDF5 as h5ad or 10x h5: {str(e2)}; source={data_uri}'},
                        'evidence': {}
                    }
        elif ftype in {'zip', 'gzip'} or tarfile.is_tarfile(local_path) or zipfile.is_zipfile(local_path):
            extract_dir = os.path.join(tmpdir, 'extracted')
            ok, reason, root_dir = _extract_archive(local_path, extract_dir)
            if not ok:
                return {
                    'artifacts': [],
                    'metrics': {'error': f'Failed to extract archive: {reason}; source={data_uri}'},
                    'evidence': {}
                }
            tenx_dir = _find_10x_mtx_dir(root_dir)
            if tenx_dir:
                try:
                    adata = sc.read_10x_mtx(tenx_dir, var_names='gene_symbols', make_unique=True)
                except Exception as e:
                    return {
                        'artifacts': [],
                        'metrics': {'error': f'Failed to read 10x MTX from {tenx_dir}: {str(e)}'},
                        'evidence': {}
                    }
            else:
                # 回退：尝试读取解压后目录中的 HDF5 文件（.h5ad 或 .h5），以支持 .h5ad.gz/.h5.gz
                found_h5ad = None
                found_h5 = None
                for r, dnames, fnames in os.walk(root_dir):
                    for fn in fnames:
                        lower = fn.lower()
                        full = os.path.join(r, fn)
                        if lower.endswith('.h5ad') and not found_h5ad:
                            found_h5ad = full
                        elif lower.endswith('.h5') and not found_h5:
                            found_h5 = full
                    if found_h5ad:
                        break
                if found_h5ad:
                    try:
                        adata = ad.read_h5ad(found_h5ad)
                    except Exception as e:
                        return {
                            'artifacts': [],
                            'metrics': {'error': f'Archive extracted; found H5AD but failed to load: {e}; path={found_h5ad}'},
                            'evidence': {}
                        }
                elif found_h5:
                    # 先尝试按 10x HDF5 读取，失败再尝试 h5ad
                    try:
                        adata = sc.read_10x_h5(found_h5)
                    except Exception:
                        try:
                            adata = ad.read_h5ad(found_h5)
                        except Exception as e2:
                            return {
                                'artifacts': [],
                                'metrics': {'error': f'Archive extracted; found HDF5 but failed to load as 10x h5 or h5ad: {e2}; path={found_h5}'},
                                'evidence': {}
                            }
                else:
                    return {
                        'artifacts': [],
                        'metrics': {'error': f'Archive extracted but neither 10x matrix directory nor HDF5 (.h5ad/.h5) file found under {root_dir}.'},
                        'evidence': {}
                    }
        else:
            # 非支持的类型，直接给出诊断
            try:
                size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
                with open(local_path, 'rb') as f:
                    head = f.read(16)
                head_hex = head.hex(' ') if head else ''
            except Exception:
                size, head_hex = 0, ''
            return {
                'artifacts': [],
                'metrics': {'error': f'Unsupported input type: {ftype}; size={size} bytes; head={head_hex}; source={data_uri}'},
                'evidence': {}
            }
        
        # 记录原始数据维度
        n_cells_raw = adata.n_obs
        n_genes_raw = adata.n_vars
        
        # 计算QC指标
        # 线粒体基因（以MT-开头）
        adata.var['mt'] = adata.var_names.str.startswith('MT-')
        # 核糖体基因（以RPS或RPL开头）
        adata.var['ribo'] = adata.var_names.str.startswith(('RPS', 'RPL'))
        
        # 计算QC指标
        sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)
        
        # 检查并添加缺失的指标
        if 'pct_counts_mt' not in adata.obs.columns and 'total_counts' in adata.obs.columns:
            adata.obs['pct_counts_mt'] = (adata[:, adata.var['mt']].X.sum(axis=1).A1 / 
                                         adata.obs['total_counts']) * 100
        
        if 'pct_counts_ribo' not in adata.obs.columns and 'total_counts' in adata.obs.columns:
            adata.obs['pct_counts_ribo'] = (adata[:, adata.var['ribo']].X.sum(axis=1).A1 / 
                                           adata.obs['total_counts']) * 100
        
        # 计算双细胞评分（简化版）
        from scipy import stats
        adata.obs['doublet_score'] = stats.zscore(adata.obs['n_genes_by_counts']) + \
                                    stats.zscore(adata.obs['total_counts'])
        
        # 识别潜在双细胞（top 5%）
        doublet_threshold = np.percentile(adata.obs['doublet_score'], 95)
        adata.obs['is_doublet'] = adata.obs['doublet_score'] > doublet_threshold
        
        # 应用过滤条件
        sc.pp.filter_cells(adata, min_genes=min_genes)
        sc.pp.filter_genes(adata, min_cells=min_cells)
        
        # 过滤高线粒体、高核糖体、高基因数细胞
        if 'n_genes_by_counts' in adata.obs:
            adata = adata[adata.obs.n_genes_by_counts < max_genes, :]
        if 'pct_counts_mt' in adata.obs:
            adata = adata[adata.obs.pct_counts_mt < max_mito * 100, :]
        if 'pct_counts_ribo' in adata.obs:
            adata = adata[adata.obs.pct_counts_ribo < max_ribo * 100, :]
        
        # 过滤潜在双细胞
        if 'is_doublet' in adata.obs:
            adata = adata[~adata.obs.is_doublet, :]
        
        # 记录过滤后数据维度
        n_cells_filtered = adata.n_obs
        n_genes_filtered = adata.n_vars
        
        # 生成QC图表
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('Quality Control Metrics', fontsize=16)
        
        # 基因数分布
        axes[0, 0].hist(adata.obs['n_genes_by_counts'], bins=50, alpha=0.7)
        axes[0, 0].axvline(min_genes, color='red', linestyle='--', label=f'min_genes={min_genes}')
        axes[0, 0].axvline(max_genes, color='red', linestyle='--', label=f'max_genes={max_genes}')
        axes[0, 0].set_xlabel('Number of genes')
        axes[0, 0].set_ylabel('Number of cells')
        axes[0, 0].set_title('Genes per Cell')
        axes[0, 0].legend()
        
        # UMI数分布
        axes[0, 1].hist(adata.obs['total_counts'], bins=50, alpha=0.7)
        axes[0, 1].set_xlabel('Total UMI counts')
        axes[0, 1].set_ylabel('Number of cells')
        axes[0, 1].set_title('UMIs per Cell')
        
        # 线粒体基因比例分布
        if 'pct_counts_mt' in adata.obs:
            axes[0, 2].hist(adata.obs['pct_counts_mt'], bins=50, alpha=0.7)
            axes[0, 2].axvline(max_mito * 100, color='red', linestyle='--', 
                              label=f'max_mito={max_mito*100:.1f}%')
            axes[0, 2].set_xlabel('Mitochondrial gene %')
            axes[0, 2].set_ylabel('Number of cells')
            axes[0, 2].set_title('Mitochondrial Genes')
            axes[0, 2].legend()
        else:
            axes[0, 2].axis('off')
        
        # 基因数 vs UMI数散点图
        axes[1, 0].scatter(adata.obs['total_counts'], adata.obs['n_genes_by_counts'], 
                          alpha=0.5, s=1)
        axes[1, 0].set_xlabel('Total UMI counts')
        axes[1, 0].set_ylabel('Number of genes')
        axes[1, 0].set_title('Genes vs UMIs')
        
        # 线粒体基因比例 vs 基因数散点图
        if 'pct_counts_mt' in adata.obs:
            axes[1, 1].scatter(adata.obs['n_genes_by_counts'], adata.obs['pct_counts_mt'], alpha=0.5, s=1)
            axes[1, 1].set_xlabel('Number of genes')
            axes[1, 1].set_ylabel('Mitochondrial gene %')
            axes[1, 1].set_title('Genes vs Mitochondrial %')
        else:
            axes[1, 1].axis('off')
        
        # 核糖体基因比例 vs 基因数散点图
        if 'pct_counts_ribo' in adata.obs:
            axes[1, 2].scatter(adata.obs['n_genes_by_counts'], adata.obs['pct_counts_ribo'], alpha=0.5, s=1)
            axes[1, 2].set_xlabel('Number of genes')
            axes[1, 2].set_ylabel('Ribosomal gene %')
            axes[1, 2].set_title('Genes vs Ribosomal %')
        else:
            axes[1, 2].axis('off')
        
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # 保存图表
        plot_path = os.path.join(tmpdir, 'qc_plots.png')
        fig.savefig(plot_path, dpi=150)
        
        # 上传图表
        plot_key = f"artifacts/{inputs.get('step_run_id','unknown')}/qc_plots.png"
        try:
            upload_to_s3(plot_path, plot_key, content_type='image/png')
        except Exception:
            # 上传失败不阻断流程
            plot_key = None
        
        # 准备返回指标与证据
        cells_removed = int((n_cells_raw - n_cells_filtered))
        genes_removed = int((n_genes_raw - n_genes_filtered))
        metrics = {
            'cells_raw': int(n_cells_raw),
            'genes_raw': int(n_genes_raw),
            'cells_filtered': int(n_cells_filtered),
            'genes_filtered': int(n_genes_filtered),
            'cells_removed': cells_removed,
            'genes_removed': genes_removed,
            'cells_removal_rate': float(cells_removed / n_cells_raw) if n_cells_raw > 0 else 0.0,
            'genes_removal_rate': float(genes_removed / n_genes_raw) if n_genes_raw > 0 else 0.0,
            'mean_genes_per_cell': float(adata.obs['n_genes_by_counts'].mean()),
            'median_genes_per_cell': float(adata.obs['n_genes_by_counts'].median()),
            'mean_umis_per_cell': float(adata.obs['total_counts'].mean()),
            'median_umis_per_cell': float(adata.obs['total_counts'].median()),
            'mean_mito_pct': float(adata.obs['pct_counts_mt'].mean()) if 'pct_counts_mt' in adata.obs else None,
            'mean_ribo_pct': float(adata.obs['pct_counts_ribo'].mean()) if 'pct_counts_ribo' in adata.obs else None,
            'filters_applied': {
                'min_genes': min_genes,
                'max_genes': max_genes,
                'min_cells': min_cells,
                'max_mito': max_mito,
                'max_ribo': max_ribo,
            }
        }
        evidence = {
            'qc_plot': plot_key,
            'tenx_dir_used': tenx_dir
        }
        
        return {
            'artifacts': [{'name': 'QC Plots', 'type': 'image', 'path': plot_key}] if plot_key else [],
            'metrics': metrics,
            'evidence': evidence
        }