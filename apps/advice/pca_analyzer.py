"""
PCA Advice Analyzer

为 PCA 分析步骤提供智能建议
"""
from typing import Dict, List, Any

class PCAAdviceAnalyzer:
    """PCA 分析结果的AI建议分析器"""

    @staticmethod
    def analyze(step_run) -> List[Dict[str, Any]]:
        metrics = step_run.metrics_json or {}
        params = step_run.params_json or {}

        suggestions: List[Dict[str, Any]] = []

        n_components = params.get('n_components', params.get('n_pcs', 30))
        explained_variance_ratio_sum = metrics.get('explained_variance_ratio_sum', 0)

        # 建议1：解释方差比例偏低，建议增加主成分数量
        if explained_variance_ratio_sum > 0 and explained_variance_ratio_sum < 0.6:
            target_components = min(50, n_components + 10)
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'medium',
                'title': 'PCA解释方差偏低，建议增加主成分数量',
                'description': f'当前{n_components}个主成分仅解释了{explained_variance_ratio_sum:.1%}的方差，建议增加到{target_components}个以捕获更多信息。',
                'evidence_text': f'PCA解释方差比例{explained_variance_ratio_sum:.1%}低于推荐值60%，可能丢失重要的生物学信号。',
                'patch_json': {
                    'n_components': target_components,
                    'n_pcs': target_components
                },
                'patch_type': 'params'
            })

        # 建议2：主成分数量过多且解释方差已足够
        if explained_variance_ratio_sum > 0.85 and n_components > 40:
            target_components = max(20, int(n_components * 0.7))
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'low',
                'title': 'PCA主成分数量可以适度减少',
                'description': f'当前{n_components}个主成分已解释{explained_variance_ratio_sum:.1%}的方差，可减少到{target_components}个以降低计算复杂度。',
                'evidence_text': f'PCA解释方差比例{explained_variance_ratio_sum:.1%}已足够高，{n_components}个主成分可能过多。',
                'patch_json': {
                    'n_components': target_components,
                    'n_pcs': target_components
                },
                'patch_type': 'params'
            })

        # 建议3：标准建议，当解释方差在合理范围但可微调
        if 0.6 <= explained_variance_ratio_sum <= 0.75 and n_components <= 25:
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'low',
                'title': '可考虑微调PCA主成分数量',
                'description': f'当前解释方差{explained_variance_ratio_sum:.1%}在合理范围内，但可尝试增加到35个主成分以获得更好的下游效果。',
                'evidence_text': f'PCA解释方差{explained_variance_ratio_sum:.1%}尚可，但略有提升空间。',
                'patch_json': {
                    'n_components': 35,
                    'n_pcs': 35
                },
                'patch_type': 'params'
            })

        return suggestions