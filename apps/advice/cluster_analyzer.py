"""
Clustering Advice Analyzer

为 Clustering 步骤提供智能建议
"""
from typing import Dict, List, Any

class ClusteringAdviceAnalyzer:
    """聚类步骤的AI建议分析器"""

    @staticmethod
    def analyze(step_run) -> List[Dict[str, Any]]:
        metrics = step_run.metrics_json or {}
        params = step_run.params_json or {}

        suggestions: List[Dict[str, Any]] = []

        method = params.get('method', metrics.get('method', 'leiden'))
        resolution = params.get('resolution', metrics.get('resolution', 0.8))
        silhouette = metrics.get('silhouette_score', 0)
        n_clusters = metrics.get('n_clusters', 0)

        # 建议1：轮廓系数偏低，建议提高分辨率
        if silhouette > 0 and silhouette < 0.35:
            target_res = min(1.5, round(resolution + 0.2, 2))
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'medium',
                'title': '聚类轮廓系数偏低，建议提高分辨率',
                'description': f'当前 silhouette_score={silhouette:.2f} 偏低，增大 resolution 有助于提升类间分离。',
                'evidence_text': f'silhouette_score={silhouette:.2f} < 0.35',
                'patch_json': {
                    'resolution': target_res
                },
                'patch_type': 'params'
            })

        # 建议2：类簇过多，建议降低分辨率
        if n_clusters > 20 and resolution >= 0.8:
            suggestions.append({
                'advice_type': 'parameter_optimization',
                'risk_level': 'low',
                'title': '聚类簇数较多，建议降低分辨率以合并过细簇',
                'description': f'当前簇数 {n_clusters} 个，可能过细，建议适度降低分辨率以获得更稳定的簇结构。',
                'evidence_text': f'n_clusters={n_clusters} > 20 且 resolution={resolution}',
                'patch_json': {
                    'resolution': max(0.4, round(resolution * 0.8, 2))
                },
                'patch_type': 'params'
            })

        # 建议3：方法选择提示
        if method == 'louvain' and silhouette < 0.4:
            suggestions.append({
                'advice_type': 'method_suggestion',
                'risk_level': 'low',
                'title': '建议尝试 Leiden 聚类方法',
                'description': 'Leiden 通常在单细胞聚类任务中表现更稳定，建议从 Louvain 切换到 Leiden。',
                'evidence_text': f'当前方法 {method} 的轮廓系数 {silhouette:.2f} 一般，Leiden 常常提供更稳定的结果。',
                'patch_json': {
                    'method': 'leiden'
                },
                'patch_type': 'params'
            })

        return suggestions