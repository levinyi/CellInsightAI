# CellInsight AI - 单细胞数据分析平台

一个现代化的单细胞生物信息学分析平台，支持多租户管理、智能参数建议和实时分析流水线。

## 功能特性

- 🔬 **完整的单细胞分析流水线**: 质量控制、高变基因选择、降维、聚类等
- 🏢 **多租户架构**: 支持组织级别的数据隔离和权限管理
- 🤖 **智能参数建议**: AI驱动的参数优化和分析建议
- 📊 **实时监控**: WebSocket实时追踪分析进度
- �� **报告生成**: 自动生成分析报告和可视化结果
- 🔒 **完整审计**: 详细的操作日志和变更追踪

## 技术栈

- **后端**: Django + Django REST Framework
- **任务队列**: Celery + Redis
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **前端**: 原生 JavaScript + HTML5
- **容器化**: Docker + Docker Compose

## 快速开始

### 环境要求

- Python 3.12+
- Docker & Docker Compose
- Redis (用于 Celery)

### 开发环境搭建

1. **克隆项目**
```bash
git clone <repository-url>
cd CellInsightAI
```

2. **创建虚拟环境**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **环境配置**
```bash
cp .env.example .env
```

5. **数据库迁移**
```bash
python manage.py migrate
python manage.py createsuperuser
```

6. **启动开发服务器**
```bash
python manage.py runserver
```

7. **访问应用**
- 工作台: http://localhost:8000/
- API 文档: http://localhost:8000/api/v1/
- 管理后台: http://localhost:8000/admin/

## 使用指南

1. 打开工作台页面
2. 点击右上角"Demo 登录"获取会话
3. 选择分析步骤并点击"运行所选步骤"
4. 实时查看分析进度和结果

## 多租户支持

- 每个用户属于一个组织 (Organization)
- 支持组织级别的数据隔离
- 角色管理 (admin/member/viewer)

## 许可证

MIT License
