# ResumeCraft 简历工坊

ResumeCraft 是一个本地优先的个人简历生产系统。它把事实资料、证据、岗位画像、临时简历、正式简历版本和 HTML 交付连成一条可追溯的工作链，适合需要针对不同岗位反复组织同一批真实经历的求职者。

当前代码版本：`v2.0.0`

当前数据库迁移版本：`0018_profile_photos`

## 核心能力

- **事实资料库**：以个人档案、教育、经历、技能和成果五类强类型事实组织内容，支持证据、标签、技能关系、成果归属、审计和回收恢复。
- **岗位画像**：分离岗位需求与招聘机会，记录岗位方向、核心要求、招聘来源和简历策略；修改采用追加式审计。
- **临时简历**：从岗位画像出发，在固定 A4 画布上选择事实并实时预览；事实库更新会反映到尚未正式化的临时内容。
- **正式简历**：将临时简历转换为正式 `v1`，之后编辑自动保存的工作副本，并显式保存为不可变版本。
- **版本与来源追踪**：版本线性追加，支持查看和恢复；事实或证据变化通过待处理事项提示，不静默覆盖已保存正文。
- **模板库**：13 套全局只读模板，覆盖侧栏双栏、单栏、横幅、表格、线式、时间轴和标签栏等版式。
- **独立 HTML 导出**：从确定的正式版本生成严格 A4 的单文件 HTML，记录导出事件、警告、内容哈希和输出哈希。
- **本地照片与证据**：支持个人档案照片以及 PDF、PNG、JPEG、WebP 证据文件；文件保存在本地数据目录。

## 工作流

```text
维护事实与证据
    -> 建立岗位画像
    -> 创建临时简历并选择事实
    -> 转换为正式 v1
    -> 编辑工作副本
    -> 保存不可变版本
    -> 导出 A4 HTML
```

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12+、FastAPI、SQLAlchemy 2、Alembic |
| 前端 | TypeScript、React、Vite |
| 存储 | 本地 SQLite + 本地附件目录 |
| 测试 | pytest、Vitest、Playwright 辅助脚本 |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- pnpm 或 npm

### Windows 一键启动

双击根目录的 `Start-ResumeCraft.cmd`。启动器会：

1. 创建 `.venv` 并安装 Python 依赖；
2. 安装前端依赖；
3. 执行 `alembic upgrade head`；
4. 在后台启动 API 和前端；
5. 打开 <http://127.0.0.1:5173>。

### 手动启动

在项目根目录准备后端：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

另开终端启动前端：

```powershell
cd web
pnpm install
pnpm dev
```

- Web 界面：<http://127.0.0.1:5173>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

首次启动会在 `data/` 下创建空数据库和附件目录。仓库不包含任何真实数据库、附件、导出文件或个人资料。

## 本地数据与隐私

数据库和上传文件是运行数据，不属于源码：

```text
data/resume_workbench.db   # 本地 SQLite 数据库
data/attachments/          # 证据与档案照片
data/logs/                 # 启动日志
output/                    # 本地导出与测试产物
```

这些路径以及 `*.db`、`*.sqlite`、日志和 `.env` 文件均被 `.gitignore` 排除。更新或迁移前请自行备份 `data/`；不要将真实数据库提交到 Git。

如果你有旧版 `data/profile.db`，启动器会在主数据库迁移完成后自动调用兼容迁移工具。只使用当前版本时无需额外执行迁移脚本。

## 测试与构建

后端与文档契约：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_domain_specs.py
.\.venv\Scripts\python.exe scripts\check_resource_library_spec.py
```

前端测试与生产构建：

```powershell
cd web
pnpm test
pnpm build
```

测试使用内存 SQLite，不会连接、修改或清空本地真实数据库。

## 项目结构

```text
app/
  domain/                 领域服务与目录
  main.py                 FastAPI 路由与请求模型
  services.py             查询、序列化、排版与 HTML 渲染
  workbench_models.py     SQLAlchemy 数据模型
  workbench_database.py   SQLite 会话配置
web/
  src/pages/              React 页面
  src/components/         A4 画布与通用组件
  src/lib/                简历分页、模板和客户端模型
migrations/               Alembic 迁移链
docs/                     产品、交互、技术、领域与测试文档
tests/                    后端与文档契约测试
scripts/                  启动、迁移、审计和版式辅助脚本
```

## 文档

文档入口与权威边界见 [docs/README.md](docs/README.md)。

- [功能设计](docs/functional-design.md)：产品行为、业务规则和验收标准。
- [交互设计](docs/interaction-design.md)：页面结构、操作流程和状态反馈。
- [技术设计](docs/technical-design.md)：架构、接口、存储、版本与导出。
- [能力状态矩阵](docs/capabilities.md)：区分已实现、目标和暂缓能力。
- [系统关系总图](docs/domain/system-map.md)：跨模块关系和不变量。
- [资料库规范](docs/resource-library/design.md)：事实、证据、字段、关系和约束。
- [岗位画像规范](docs/domain/job-profile/design.md)：招聘需求与机会模型。
- [简历主链规范](docs/domain/resume/design.md)：临时简历、正式简历、工作副本与版本。
- [模板与交付规范](docs/domain/rendering-delivery/design.md)：模板、渲染和导出事件。
- [测试说明](docs/test-guide.md)：测试命令、覆盖范围和手工验收方法。
- [项目计划](docs/project-plan.md)：交付阶段、已确认决策和后续工作。
- [发布记录](docs/release-notes.md)：历史版本变化与验证结果。

## 当前边界

`v2.0.0` 已实现资料库、岗位画像、临时简历、正式版本、模板、照片、证据和 HTML 导出主链。以下能力仍属于后续范围：

- AI 辅助编辑和工作副本变更记录；
- ZIP 附件包及 `manifest.json` 交付；
- 账号、多用户、成员权限和多工作区隔离；
- PostgreSQL、对象存储和后台任务；
- 投递状态、联系人和面试跟踪。

## 许可证

本项目使用 [MIT License](LICENSE)。

欢迎通过 Issue 提交问题、使用反馈和改进建议。
