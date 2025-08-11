"""
AI建议分析器 - Phase 7实现
根据StepRun的metrics和evidence生成可执行的建议补丁
"""
import json
from typing import Dict, List, Any
from apps.projects.models import StepRun, Advice
from .hvg_analyzer import HVGAdviceAnalyzer
from .pca_analyzer import PCAAdviceAnalyzer
from .umap_analyzer import UMAPAdviceAnalyzer
from .cluster_analyzer import ClusteringAdviceAnalyzer


class QCAdviceAnalyzer:
    """质量控制步骤的AI建议分析器"""
    
    @staticmethod
    def analyze(step_run: StepRun) -> List[Dict[str, Any]]:
        """分析QC结果并生成建议"""
        metrics = step_run.metrics_json or {}
        params = step_run.params_json or {}
        
        suggestions = []
        
        # 检查线粒体基因比例过高
        high_mito = metrics.get('high_mito', 0)
        if high_mito > 0.15:
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'medium',
                'title': '线粒体基因比例阈值建议调整',
                'description': f'当前有{high_mito:.1%}的细胞线粒体基因比例过高，建议调整过滤阈值以改善数据质量。',
                'evidence_text': f'检测到{high_mito:.1%}细胞线粒体基因占比超标，可能影响下游分析质量',
                'patch_json': {
                    'max_mito': max(0.05, high_mito * 0.8)  # 适度降低阈值
                },
                'patch_type': 'params'
            })
        
        # 检查双细胞率
        doublet_rate = metrics.get('doublet_rate', 0)
        if doublet_rate > 0.05:
            suggestions.append({
                'advice_type': 'quality_improvement',
                'risk_level': 'high',
                'title': '双细胞检测率偏高',
                'description': f'检测到{doublet_rate:.1%}的双细胞率，建议增强过滤或重新评估实验条件。',
                'evidence_text': f'双细胞率{doublet_rate:.1%}超过推荐值5%，可能需要额外的过滤步骤',
                'patch_json': {
                    'enable_doublet_filter': True,
                    'doublet_threshold': 0.8
                },
                'patch_type': 'params'
            })
        
        # 检查基因数范围
        min_genes = params.get('min_genes', 200)
        max_genes = params.get('max_genes', 5000)
        cell_count = metrics.get('cells', 0)
        
        if cell_count < 1000:
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'medium',
                'title': '细胞数量较少，建议放宽过滤条件',
                'description': f'当前仅保留{cell_count}个细胞，建议适当放宽基因数过滤条件以保留更多细胞。',
                'evidence_text': f'过滤后细胞数{cell_count}可能不足以进行稳健的下游分析',
                'patch_json': {
                    'min_genes': max(100, min_genes - 50),
                    'max_genes': max_genes + 1000
                },
                'patch_type': 'params'
            })
        
        return suggestions


class AdviceEngine:
    """主要的建议引擎"""
    
    ANALYZERS = {
        'qc': QCAdviceAnalyzer,
        'hvg': HVGAdviceAnalyzer,
        'pca': PCAAdviceAnalyzer,
        'umap': UMAPAdviceAnalyzer,
        'clustering': ClusteringAdviceAnalyzer,
        # 后续可扩展其他分析器
    }
    
    @classmethod
    def generate_advice(cls, step_run: StepRun):
        """为给定的StepRun生成AI建议"""
        step_type = step_run.step.step_type
        analyzer = cls.ANALYZERS.get(step_type)
        
        if not analyzer:
            return  # 暂不支持的步骤类型
        
        suggestions = analyzer.analyze(step_run)
        
        # 保存建议到数据库
        for suggestion in suggestions:
            advice = Advice.objects.create(
                step_run=step_run,
                advice_type=suggestion['advice_type'],
                risk_level=suggestion['risk_level'],
                title=suggestion['title'],
                description=suggestion['description'],
                evidence_text=suggestion['evidence_text'],
                patch_json=suggestion['patch_json'],
                patch_type=suggestion['patch_type']
            )
            
        return len(suggestions)