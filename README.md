# 简历工坊 ResumeCraft

简历工坊（ResumeCraft）是一个本地优先的个人简历系统，把事实资料、证据、岗位画像、临时简历、正式版本和 HTML 交付组织成一条可追溯的工作链路。

当前正式版本：`v1.0.6`

## 功能概览

- **事实资料库**：按基本信息、教育经历、项目与实践、技能、成果、链接与作品集等分类维护事实，支持扩展字段、证据文件与链接、审计记录和回收站。
- **岗位画像**：记录岗位方向、核心技术要求、简历策略和原始 JD；一个岗位画像对应一份正式简历。
- **临时简历**：从岗位画像出发，在固定 A4 画布上按栏目选择事实资料，实时预览并自动保存选择状态。
- **正式简历**：把临时简历转为正式简历并立即生成 `v1`；工作副本自动保存，正文可独立修改，同时保留事实来源关系。
- **版本管理**：每次正式保存追加线性不可变版本，支持历史查看和从历史版本恢复工作副本。
- **来源变化提醒**：被引用的事实发生变化时，在 ResumeCraft 和对应条目上标记待处理，不自动改写正式正文。
- **导出**：正式版本支持独立严格 A4 HTML 导出。

## 使用流程

```text
维护事实资料与证据
    -> 建立岗位画像
    -> 创建临时简历并选择事实
    -> 转为正式简历
    -> 编辑工作副本
    -> 保存正式版本
    -> 导出 HTML
```

1. 在资料库中维护事实资料，并按需补充证据文件或可验证链接。
2. 建立岗位画像，写清岗位方向、核心技术要求和简历强调方向。
3. 从岗位画像创建临时简历，在固定 A4 画布上点击栏目并选择要呈现的事实。
4. 将临时简历转为正式简历，系统会创建原因标记为“格式化简历、未润色”的 `v1`。
5. 在正式简历工作区继续编辑工作副本：A4 页面保持只读预览，点击条目打开编辑卡片，右键打开快捷菜单。
6. 点击“保存正式版本”追加新的不可变版本，或从版本历史导出正式 HTML。

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- pnpm

### 手动启动

在项目根目录启动后端：

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

浏览器访问 <http://127.0.0.1:5173>，后端 API 位于 <http://127.0.0.1:8000>。

Windows 下也可以直接双击项目根目录的 `Start-ResumeCraft.cmd`，启动器会检查依赖、执行迁移并在后台启动前后端。

### 测试与构建

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

前端生产构建：

```powershell
cd web
pnpm build
```

## 项目结构

```text
app/          FastAPI + SQLAlchemy 后端
web/          TypeScript + React SPA 前端
docs/         功能、交互、技术、项目计划、测试和发布说明
migrations/   Alembic 数据库迁移
tests/        后端测试
scripts/      启动器与辅助脚本
data/         本地数据库与附件目录（不纳入版本库）
```

## 设计文档

- [功能设计书](docs/functional-design.md)：产品用途、核心概念、用户流程、功能行为、版本规则和验收标准。
- [交互界面设计书](docs/interaction-design.md)：信息架构、页面组织、用户操作、状态反馈、编辑流程和导出交互。
- [实现设计书](docs/technical-design.md)：架构、数据模型、前后端职责、接口、存储、版本和导出设计。
- [项目计划](docs/project-plan.md)：开发阶段、交付顺序、已确定决策和待确认事项。
- [测试说明](docs/test-guide.md)：测试运行方式、现有测试和仍需补充的测试。
- [发布记录](docs/release-notes.md)：正式版本范围、交互变化和验证结果。
- [修订审计](docs/revision-audit.md)：2026-09 修订问题、不可违反的交互约束和验收清单。

## 当前范围

`v1.0.0` 已实现本地事实维护、证据管理、岗位画像、临时简历选择、正式简历编辑、工作副本自动保存、线性版本和独立 A4 HTML 导出。

AI 辅助编辑、附件 ZIP 交付、多用户、PostgreSQL 和对象存储等能力仍保留在后续计划中，具体路线以 [项目计划](docs/project-plan.md) 为准。

## 许可证

本项目使用 [MIT License](LICENSE)。

## 持续更新与反馈

项目会持续更新，欢迎提出建议、反馈使用问题或贡献代码。
