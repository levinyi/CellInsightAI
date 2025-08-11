#!/usr/bin/env python
"""
端到端测试脚本 - 验证系统完整功能
"""
import os
import django
import sys
import json
import time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bioai_platform.settings')
django.setup()

from apps.projects.models import Project, Sample, Step, StepRun
from apps.projects.api import trigger_run
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.http import JsonResponse

def test_full_pipeline():
    """测试完整分析链路"""
    print("=== CellInsightAI 端到端测试 ===\n")
    
    # 1. 确保默认步骤存在
    print("1. 确保默认步骤...")
    from apps.projects.viewsets import StepViewSet
    request = RequestFactory().post('/')
    viewset = StepViewSet()
    viewset.request = request
    response = viewset.ensure_defaults(request)
    print(f"   Created steps: {response.data}")
    
    # 2. 创建项目和样本
    print("\n2. 创建测试项目和样本...")
    User = get_user_model()
    user, _ = User.objects.get_or_create(username='testuser')
    
    project = Project.objects.create(
        name='Test Project',
        description='E2E test project',
        owner=user
    )
    
    sample = Sample.objects.create(
        project=project,
        name='Test Sample',
        sample_type='single_cell'
    )
    
    print(f"   Project: {project.name} (ID: {project.id})")
    print(f"   Sample: {sample.name} (ID: {sample.id})")
    
    # 3. 获取第一个步骤
    step = Step.objects.first()
    print(f"   Using Step: {step.name} (Type: {step.step_type})")
    
    # 4. 创建 StepRun 并运行
    print("\n3. 运行分析步骤...")
    test_params = {
        'min_genes': 200,
        'max_genes': 5000,
        'max_mito': 0.1  # 小数形式
    }
    
    run = StepRun.objects.create(
        sample=sample,
        step=step,
        params_json=test_params,
        status='PENDING'
    )
    
    print(f"   Created StepRun: {run.id}")
    print(f"   Parameters: {json.dumps(test_params, indent=2)}")
    
    # 5. 手动调用任务（由于启用了 eager 模式）
    from apps.projects.tasks import run_step
    print("   Executing task...")
    result = run_step(str(run.id))
    
    # 6. 检查结果
    run.refresh_from_db()
    print(f"\n4. 任务执行结果:")
    print(f"   Status: {run.status}")
    print(f"   Metrics: {json.dumps(run.metrics_json, indent=2)}")
    print(f"   Evidence: {json.dumps(run.evidence_json, indent=2)}")
    
    # 7. 检查建议
    from apps.projects.models import Advice
    advice_count = Advice.objects.filter(step_run=run).count()
    print(f"\n5. AI建议生成:")
    print(f"   Generated {advice_count} advice(s)")
    
    if advice_count > 0:
        for i, advice in enumerate(Advice.objects.filter(step_run=run)):
            print(f"   Advice {i+1}: {advice.title}")
            print(f"      Risk: {advice.risk_level}")
            print(f"      Patch: {json.dumps(advice.patch_json, indent=6)}")
    
    # 8. 测试其他步骤类型
    print("\n6. 测试其他Runner类型...")
    for step_type in ['hvg', 'pca', 'umap', 'clustering']:
        try:
            step_obj = Step.objects.filter(step_type=step_type).first()
            if step_obj:
                test_run = StepRun.objects.create(
                    sample=sample,
                    step=step_obj,
                    params_json={'test': True},
                    status='PENDING'
                )
                result = run_step(str(test_run.id))
                test_run.refresh_from_db()
                print(f"   {step_type.upper()}: {test_run.status} - {len(test_run.metrics_json or {})} metrics")
        except Exception as e:
            print(f"   {step_type.upper()}: ERROR - {str(e)}")
    
    print("\n=== 测试完成 ===")
    print(f"Total Steps: {Step.objects.count()}")
    print(f"Total Runs: {StepRun.objects.count()}")
    print(f"Total Advice: {Advice.objects.count()}")
    
    return True

if __name__ == '__main__':
    try:
        test_full_pipeline()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)