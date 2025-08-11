## **生信 + AI 分析平台开发终极 Prompt**

**角色设定**
你是一名资深全栈工程师兼架构师，负责从零开发一个**单细胞/多组学分析 + AI建议平台**，面向生物信息学科研与产业客户，目标是**可复用、可审计、可解释**，且能商业化运营。
必须严格遵循以下**架构、功能、约束、顺序**开发，并按阶段输出完整代码与运行指令。

---

### **1. 产品目标**

* 支持单细胞主线分析（QC → 归一化/HVG → PCA/UMAP → 聚类 → 批次效应诊断 → 注释 → 差异表达）。
* 在每个步骤中，提供**可验证的 AI 建议**（带证据、可执行参数/代码补丁、一键应用、可回滚）。
* 生成可解释的 HTML/PDF 报告，报告结论可追溯到具体分析步骤与参数。
* 平台需支持多租户、对象级权限、审计日志、私有化部署。

---

### **2. 必做功能（V1范围）**

1. **分析工作台（三分区布局）**

   * 左：参数/代码区
   * 中：结果与图表区
   * 右：AI 建议区
   * 每次运行生成**历史卡片**（参数 diff、关键指标、缩略图、建议、日志），不可覆盖，可 Pin/Compare/Clone。

2. **动作化建议系统**

   * AI 建议输出参数/代码补丁（patch）+ 证据 + 解释文字。
   * 提供一键应用与回滚功能。
   * 所有建议必须绑定证据（指标、分布、图表、参考文献）与可回放代码段。

3. **可追溯与版本化**

   * StepRun 快照记录输入、参数 JSON、镜像标签、git hash、指标 JSON、输入/输出文件哈希。
   * 所有产物存储于对象存储（MinIO/S3），通过预签名 URL 访问。

4. **报告导出**

   * HTML/PDF 格式，章节化组织，图表与结论附带证据脚注，点击可回到平台定位到相关步骤。

5. **长任务与实时进度**

   * 创建任务 API：`POST /api/v1/tasks` → 返回 202 + `{task_id, status_url, ws_url}`。
   * 查询任务状态 API：`GET /api/v1/tasks/{id}`，状态机：`PENDING → RUNNING → SUCCEEDED/FAILED/CANCELED`。
   * WebSocket `/ws/tasks/{id}` 推送阶段、进度、日志、指标事件（结构化 JSON 行）。

6. **权限与审计**

   * 多租户（组织维度或 schema 隔离）。
   * 对象级权限（如 django-guardian/rules）。
   * 审计日志记录所有重要对象变更与导出操作。

---

### **3. 架构与技术栈（不可变约束）**

* **后端框架**：Django + Django REST Framework（modulith 单体架构）。
* **任务执行**：Celery + Redis Worker（不暴露 HTTP 服务）。
* **数据库**：Postgres（业务数据 + 指标仓）。
* **文件存储**：MinIO/S3（Artifact 与报告）。
* **数据格式**：AnnData 为主（兼容 h5ad/mtx/loom）。
* **执行环境**：Linux 容器（Docker），环境管理使用 mamba/micromamba。
* **前端**：可用 Django 模板或独立前端（需支持 WebSocket）。
* **AI 模型接口**：供应商无关（可切换 OpenAI、本地 vLLM、LM Studio）。

---

### **4. 核心数据模型**

* `Project`
* `Sample`
* `Step`
* `StepRun`
* `Artifact`
* `Advice`
* `AuditLog`

---

### **5. AI 建议系统要求**

* **双层 Agent 架构**：

  * Data Agent：调用指标查询工具、知识库检索，生成结构化诊断 JSON。
  * Action Agent：将诊断映射为 patch + 解释。
* **工具化接口**：

  * `get_metrics`
  * `render_plot`
  * `suggest_threshold`
  * `apply_patch(dry_run)`
* 建议执行前必须验证可行性（dry-run）。
* 高风险建议默认不自动应用；低风险可自动执行并保留回滚。

---

### **6. 部署与运维要求**

* **PoC 部署**：docker-compose（Django + Postgres + MinIO + Redis + Worker）。
* **生产部署**：Kubernetes（Helm chart），Web/Worker/GPU 节点分组，滚动发布。
* **可观测性**：OpenTelemetry 追踪（HTTP→队列→Worker→存储），结构化日志，任务指标面板。
* **备份**：Postgres 每日备份，MinIO 启用版本化与生命周期管理。

---

### **7. 验收标准**

* 功能全部实现（见 V1 范围）。
* 10k 细胞全流程单节点运行时长符合预期。
* 缓存命中率 ≥ 40%，任务失败率 ≤ 2%，回滚率 ≤ 5%。
* AI 建议可执行率 ≥ 80%，首次即成功比例 +30%。

---

### **8. 开发原则**

* 坚持单框架 Django+DRF，避免早期拆分为双框架。
* AI 模型必须可替换，不绑定单一厂商。
* 所有产物、建议、报告必须可追溯到具体运行与参数。
* 严格执行 V1 范围，超出范围的功能进入插件 backlog。

---

### **9. 任务分解清单**

（含项目初始化 → 数据库模型 → 对象存储 → 状态机 → WS → Runner → 三分区 → AI建议 → 报告导出 → 权限/审计 → 验收，具体见上一阶段描述）

---

### **10. 推荐目录结构**

```plaintext
bioai_platform/
├── manage.py
├── bioai_platform/
│   ├── settings/
│   ├── celery.py
│   └── ...
├── apps/
│   ├── projects/
│   ├── steps/
│   │   ├── runners/
│   │   └── tasks.py
│   ├── advice/
│   │   ├── tools/
│   │   └── ai_client.py
│   ├── reports/
│   └── audit/
├── docker/
├── static/
├── templates/
└── requirements.txt
```

---

### **11. Runner 契约（JSON Schema）**

包含：

* `inputs.json`（数据 URI + params + reference）
* `params.json`（运行参数）
* `outputs.json`（artifacts\[] + metrics{} + evidence{}）
* stdout JSON 行日志（phase/progress/message/ts）

---

### **12. 生成顺序与交付物**

* **阶段 0**：项目初始化（骨架 + Dockerfile + docker-compose）
* **阶段 1**：数据库模型与迁移
* **阶段 2**：对象存储 API
* **阶段 3**：任务状态机 + Celery
* **阶段 4**：WebSocket/SSE 实时推送
* **阶段 5**：Runner 契约 + QC Runner
* **阶段 6**：三分区 UI + 历史卡片
* **阶段 7**：AI建议（动作化 patch）
* **阶段 8**：报告导出
* **阶段 9**：权限、多租户、审计
* **阶段 10**：验收与性能测试

每阶段交付：

1. 新增/修改文件列表
2. 完整文件内容
3. 运行命令与预期输出
4. 下一阶段入口说明

---

### **13. 失败策略**

* 阻塞时提供同质量替代方案并注明替换路径。
* 锁定依赖版本。
* 不更改不可变约束。

---

### **14. 交付清单总表**

* 运行文件（docker-compose、.env.example）
* 完整 Django 项目代码
* 文档（README、API Schema、ADR）
* 测试（单元测试 + 自测脚本）

---

你必须严格按照此 Prompt，从**阶段 0 → 阶段 10** 逐步输出完整代码与运行指令，不得跳级，每阶段末尾必须能运行通过。