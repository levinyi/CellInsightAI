"""
HVG Advice Analyzer

为 HVG 分析步骤提供智能建议
"""
from typing import Dict, List, Any

class HVGAdviceAnalyzer:
    """HVG 分析结果的AI建议分析器（返回建议字典列表，由 AdviceEngine 统一入库）"""

    @staticmethod
    def analyze(step_run) -> List[Dict[str, Any]]:
        metrics = step_run.metrics_json or {}
        params = step_run.params_json or {}

        suggestions: List[Dict[str, Any]] = []

        n_hvgs = metrics.get('n_hvgs', 0)
        current_method = params.get('method', 'seurat_v3')

        # 建议1：HVG数量偏少
        if n_hvgs and n_hvgs < 1000:
            target = max(1000, min(3000, n_hvgs * 2))
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'medium',
                'title': 'HVG数量偏少，建议提高 n_top_genes',
                'description': f'当前仅检测到 {n_hvgs} 个高变基因，建议增加到 {target} 以提升后续PCA和聚类的效果。',
                'evidence_text': f'HVG数量 {n_hvgs} 低于推荐范围（1000-3000），可能导致维度降低和聚类不稳。',
                'patch_json': {
                    'n_top_genes': target,
                    'method': 'seurat_v3'
                },
                'patch_type': 'params'
            })

        # 建议2：HVG数量过多
        if n_hvgs and n_hvgs > 5000:
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'low',
                'title': 'HVG数量过多，建议适度减少',
                'description': f'当前检测到 {n_hvgs} 个高变基因，数量偏多可能引入噪声，建议将 n_top_genes 调整到 2000。',
                'evidence_text': f'HVG数量 {n_hvgs} 超过推荐上限，过多的HVG可能影响聚类稳定性。',
                'patch_json': {
                    'n_top_genes': 2000
                },
                'patch_type': 'params'
            })

        # 建议3：方法建议，从 cell_ranger 切换到 seurat_v3
        if current_method == 'cell_ranger' and n_hvgs:
            suggestions.append({
                'advice_type': 'method_suggestion',
                'risk_level': 'low',
                'title': '建议切换HVG检测方法至 Seurat v3',
                'description': '在多数数据集上，Seurat v3 的高变基因选择更加稳健，建议从 Cell Ranger 切换到 Seurat v3。',
                'evidence_text': f'当前方法为 {current_method}，检测到 HVG 数量 {n_hvgs}。多数场景下 Seurat v3 更稳健。',
                'patch_json': {
                    'method': 'seurat_v3'
                },
                'patch_type': 'params'
            })

        return suggestions