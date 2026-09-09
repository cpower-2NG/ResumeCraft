# 简历工作台

简历工作台是一个用于沉淀个人事实资料、组织岗位需求、制作岗位相关简历并管理交付版本的简历系统。

系统的目标是将“事实资料维护、岗位需求分析、临时简历生成、人工/AI 特化、正式版本管理和 HTML 交付”组织成一条可追溯的工作链路。

## 文档优先级

项目设计文档按以下顺序生效：

```text
功能设计书 > 交互界面设计书 > 实现设计书 > 项目计划
```

功能设计书定义系统用途、用户工作逻辑和必须满足的产品行为。交互界面设计书把这些行为落实为页面、状态和操作规则。实现设计书说明如何实现前两者；如果技术方案与产品或交互设计冲突，应调整技术方案。项目计划只负责开发阶段、依赖、交付和决策记录。

## 设计文档

- [功能设计书](docs/functional-design.md)：产品用途、核心概念、用户流程、功能行为、版本规则和验收标准。
- [交互界面设计书](docs/interaction-design.md)：信息架构、页面组织、用户操作、状态反馈、编辑流程和导出交互。
- [实现设计书](docs/technical-design.md)：目标架构、数据模型、前后端职责、接口、存储、版本、AI、导出和测试设计。
- [项目计划](docs/project-plan.md)：开发阶段、交付顺序、已确定决策、待确认事项和迁移工作项。

## 核心功能

- 维护个人信息、教育、经历、技能、成果、链接和作品集等事实资料。
- 管理面向招聘者的证据，包括文件、链接和说明。
- 创建岗位需求画像，并关联多个公司的招聘机会。
- 根据最新事实资料生成与需求画像联动的临时简历。
- 将临时简历转为可独立编辑的正式简历。
- 保留正式简历与事实资料的来源关系。
- 使用人工或 AI 辅助修改工作副本。
- 通过线性不可变版本管理正式简历，支持历史查看、差异比较和回退。
- 在证据变化时自动生成带原因标记的新版本。
- 输出 HTML 主文档和包含证据附件的 ZIP 包。

## 当前实现状态

当前工作区中的应用仍是早期本地原型，主要采用以下技术：

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Jinja2
- 原生 HTML/CSS

原型已经具备基本资料维护、岗位标签推荐、简历模板渲染、预览和 HTML 下载能力，但尚未完整实现设计文档中的结构化正式简历、证据管理、工作副本、版本历史、AI 辅助和 HTML/附件 ZIP 导出。

目标系统的前后端形态暂定为 TypeScript SPA + REST API，具体前端工具可以在实现阶段继续确定。当前原型只作为迁移输入和功能验证基础，不作为目标架构约束。

## 首版工作台

首版实现位于 `app/workbench_*.py` 和 `web/`，不再使用原型的服务端模板流程。它提供：

- 默认本地用户和工作区；
- 事实资料、审计记录、岗位画像和招聘机会；
- 自动保存选择状态的临时简历；
- 一画像一正式简历、自动保存工作副本和线性不可变版本；
- 历史预览与恢复到工作副本；
- 事实来源变更的待处理提醒；
- 迁移后的经典侧栏模板与一页长度提示。

原型数据库 `data/profile.db` 保持只读。新系统使用 `data/resume_workbench.db`，旧的 `ResumeDocument` 不会迁移，因为它不包含正式版本所需的完整来源和内容快照。

### 初始化和启动

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.migrate_legacy
python -m uvicorn app.main:app --reload
```

另开终端启动前端：

```powershell
cd web
pnpm install
pnpm dev
```

浏览器访问 <http://127.0.0.1:5173>。后端 API 位于 <http://127.0.0.1:8000>，测试可通过 `pytest` 运行。

### 双击启动

Windows 下可直接双击项目根目录的 `Start-ResumeWorkbench.cmd`。若工作台的 API 和前端已在运行，启动器只会打开浏览器，不会重复安装依赖、迁移或启动进程；否则它会检查依赖、执行数据库迁移和资料导入，在后台启动 API 与前端，并在服务可用后打开工作台。服务日志位于 `data/logs/`；如提示端口已被占用，请先关闭占用 `8000` 或 `5173` 端口的程序。

## 快速开始：当前原型

### 创建虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 启动服务

```bash
python -m uvicorn app.main:app --reload
```

启动后访问 <http://127.0.0.1:8000>。

首次启动会创建 `data/profile.db` 并写入原型种子数据。当前原型生成的 HTML 文件位于 `output/默认简历成品目录/`。

## 当前原型结构

```text
.
|-- app/
|   |-- main.py                    # FastAPI 路由和原型应用流程
|   |-- models.py                  # 当前 SQLAlchemy 模型
|   |-- database.py                # SQLite 连接和目录初始化
|   |-- recommend.py               # 当前标签推荐逻辑
|   |-- seed.py                    # 原型种子数据
|   |-- static/app.css             # 原型页面样式
|   `-- templates/                 # Jinja2 页面和原型简历模板
|-- data/profile.db                # 当前原型数据库
|-- output/默认简历成品目录/       # 当前原型 HTML 输出
|-- docs/
|   |-- functional-design.md       # 产品与功能行为基准
|   |-- interaction-design.md      # 信息架构与交互行为设计
|   |-- technical-design.md        # 目标技术实现说明
|   `-- project-plan.md            # 项目路线与决策记录
|-- requirements.txt               # 当前原型依赖
`-- README.md
```

## 设计原则

- 事实资料保持中立，岗位特化发生在简历工作副本中。
- 临时简历视图实时读取事实库；临时视图本身不进入正式版本，转化时才创建“格式化简历、未润色”的正式 `v1`。
- 正式简历正文独立编辑，但保留来源和证据关系。
- 正式历史版本不可覆盖；回退通过新版本实现。
- AI 可以辅助修改工作副本，但不能绕过用户正式保存。
- 证据面向招聘者验证，链接可进入正文，文件可作为附件交付。
- 本地优先实现，同时为未来多用户、PostgreSQL 和对象存储预留边界。

## 备份

当前原型的工作数据位于 `data/profile.db`，生成文件位于 `output/默认简历成品目录/`。备份时应同时保存这两个位置。目标系统的备份和恢复规则以实现设计书为准。
