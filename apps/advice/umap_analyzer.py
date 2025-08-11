"""
UMAP Advice Analyzer

为 UMAP 步骤提供智能建议
"""
from typing import Dict, List, Any

class UMAPAdviceAnalyzer:
    """UMAP 分析结果的AI建议分析器"""

    @staticmethod
    def analyze(step_run) -> List[Dict[str, Any]]:
        metrics = step_run.metrics_json or {}
        params = step_run.params_json or {}

        suggestions: List[Dict[str, Any]] = []

        n_neighbors = params.get('n_neighbors', 15)
        min_dist = params.get('min_dist', 0.5)
        gsp = metrics.get('global_structure_preservation', 0)
        lsp = metrics.get('local_structure_preservation', 0)

        # 建议1：全局结构保存较低，建议增大 n_neighbors
        if gsp > 0 and gsp < 0.5:
            target_neighbors = min(50, max(n_neighbors + 10, 20))
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'medium',
                'title': '全局结构保持较差，建议增大 n_neighbors',
                'description': f'当前全局结构保持度 {gsp:.2f} 较低，增大邻居数有助于保留全局结构。',
                'evidence_text': f'global_structure_preservation={gsp:.2f} < 0.5',
                'patch_json': {
                    'n_neighbors': target_neighbors
                },
                'patch_type': 'params'
            })

        # 建议2：局部结构保存较低，建议减小 min_dist
        if lsp > 0 and lsp < 0.6:
            target_min_dist = max(0.05, min_dist * 0.5)
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'low',
                'title': '局部结构保持一般，建议减小 min_dist',
                'description': f'当前局部结构保持度 {lsp:.2f} 一般，减小 min_dist 可增强类内紧凑性。',
                'evidence_text': f'local_structure_preservation={lsp:.2f} < 0.6',
                'patch_json': {
                    'min_dist': target_min_dist
                },
                'patch_type': 'params'
            })

        # 建议3：若两个指标都不错，但可微调
        if gsp >= 0.5 and lsp >= 0.8 and n_neighbors > 20:
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'low',
                'title': 'UMAP表现良好，可略降 n_neighbors 提高分离度',
                'description': '在保持全局与局部结构的前提下，适度降低 n_neighbors 有时能提升类间分离。',
                'evidence_text': f'GSP={gsp:.2f}, LSP={lsp:.2f} 均较好',
                'patch_json': {
                    'n_neighbors': max(15, int(n_neighbors * 0.8))
                },
                'patch_type': 'params'
            })

        return suggestions