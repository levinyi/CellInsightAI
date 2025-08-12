# CellInsight AI

[English](#english) | [中文](#chinese)

---

<a id="english"></a>
## English

A modern single-cell bioinformatics analysis platform with multi-tenant management, AI-powered parameter suggestions, and real-time analysis pipelines.

### ✨ Features

- 🔬 **End-to-end single-cell pipeline**: QC, HVG selection, dimensionality reduction, clustering, etc.
- 🏢 **Multi-tenant architecture**: Organization-level data isolation and access control
- 🤖 **AI suggestions**: AI-driven parameter optimization and analysis guidance
- 📊 **Real-time monitoring**: Track analysis progress via WebSocket
- 📈 **Report generation**: Automatic reports and visualizations
- 🔒 **Full audit**: Detailed operation logs and change tracking

### 🛠 Tech Stack

- **Backend**: Django + Django REST Framework
- **Task Queue**: Celery + Redis
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Frontend**: Vanilla JavaScript + HTML5
- **Containerization**: Docker + Docker Compose

### 🚀 Quick Start

#### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- Redis (for Celery)

#### Development Setup

1. **Clone the repo**
```bash
git clone <repository-url>
cd CellInsightAI
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Database setup**
```bash
python manage.py migrate
python manage.py createsuperuser
```

5. **Start services**
```bash
# Start Redis
redis-server

# Start Celery Worker (new terminal)
celery -A bioai_platform worker --loglevel=info

# Start Django server
python manage.py runserver
```

6. **Access the app**
- Workbench: http://localhost:8000/
- API Docs: http://localhost:8000/api/v1/
- Admin: http://localhost:8000/admin/

#### Docker Quick Start
```bash
docker-compose up -d
```

### 📖 Usage

1. Open the Workbench and click "Demo Login"
2. Upload your single-cell data (`.h5ad`, `.h5`, `.csv`, `.mtx`, `.zip`)
3. Configure analysis steps and parameters
4. Monitor real-time progress and view results

### 🏢 Multi-Tenancy
- Organization-level data isolation
- Role-based access control (admin/member/viewer)
- Resource management per organization

### 📄 License
MIT License

---

<a id="chinese"></a>
## 中文

一个现代化的单细胞生物信息学分析平台，支持多租户管理、智能参数建议和实时分析流水线。

### ✨ 功能特性

- 🔬 **完整的单细胞分析流水线**: 质量控制、高变基因选择、降维、聚类等
- 🏢 **多租户架构**: 支持组织级别的数据隔离和权限管理
- 🤖 **智能参数建议**: AI驱动的参数优化和分析建议
- 📊 **实时监控**: WebSocket实时追踪分析进度
- 📈 **报告生成**: 自动生成分析报告和可视化结果
- 🔒 **完整审计**: 详细的操作日志和变更追踪

### 🛠 技术栈

- **后端**: Django + Django REST Framework
- **任务队列**: Celery + Redis
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **前端**: 原生 JavaScript + HTML5
- **容器化**: Docker + Docker Compose

### 🚀 快速开始

#### 环境要求
- Python 3.12+
- Docker & Docker Compose
- Redis (用于 Celery)

#### 开发环境搭建

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

4. **数据库配置**
```bash
python manage.py migrate
python manage.py createsuperuser
```

5. **启动服务**
```bash
# 启动Redis
redis-server

# 启动Celery Worker（新终端）
celery -A bioai_platform worker --loglevel=info

# 启动Django服务器
python manage.py runserver
```

6. **访问应用**
- 工作台: http://localhost:8000/
- API 文档: http://localhost:8000/api/v1/
- 管理后台: http://localhost:8000/admin/

#### Docker快速启动
```bash
docker-compose up -d
```

### 📖 使用指南

1. 打开工作台页面，点击"Demo 登录"
2. 上传单细胞数据文件（支持 `.h5ad`, `.h5`, `.csv`, `.mtx`, `.zip`）
3. 配置分析步骤和参数
4. 实时监控分析进度并查看结果

### 🏢 多租户支持
- 组织级别的数据隔离
- 基于角色的访问控制（admin/member/viewer）
- 按组织管理资源分配

### 📄 许可证
MIT License
