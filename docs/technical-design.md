# ResumeCraft 实现设计书

> 文档状态：living-design
>
> 2026-11 实施基线：事实资料采用公共主表加五类强类型明细表；简历区块使用结构化 `fields` 与 `display_fields`；正式编辑采用只读 A4 预览加编辑卡片/右键菜单；档案照片与证据文件本地存储并进入正式版本快照；正式版本支持独立 A4 HTML 导出，ZIP 附件包暂未纳入本阶段。
>
> 资料域规范：[资料库关系规范](resource-library/design.md)。本文不再另行定义资料域实体、字段、状态和约束；发生冲突时以该文档及其 `schema.sql` 为准。
>
> 模块规范：[岗位画像](domain/job-profile/design.md)、[简历主链](domain/resume/design.md)、[模板与交付](domain/rendering-delivery/design.md)、[系统关系总图](domain/system-map.md)。实现状态以[能力状态矩阵](capabilities.md)为准。

> 文档性质：目标系统的技术说明
>
> 上位文档：[功能设计书](functional-design.md)
>
> 设计原则：实现方式必须服务于功能设计；技术便利性不能改变产品行为

## 1. 文档地位与范围

本文档说明如何实现功能设计书中的ResumeCraft，不重新定义产品功能。功能设计书是产品行为的唯一权威来源；当本文档与功能设计书冲突时，以功能设计书为准并修正本文档。

本文档描述目标架构。当前实现和目标差距以[能力状态矩阵](capabilities.md)为准；运行实现采用 FastAPI、SQLAlchemy、SQLite 和 TypeScript SPA。

目标系统需要支持：

- 本地优先运行；
- 结构化简历编辑；
- 事实资料与正式简历正文分离；
- 来源关系和证据追踪；
- 工作副本与不可变版本；
- 证据变化自动生成版本；
- 全局只读模板目录和 HTML/ZIP 导出；
- 可插拔 AI 服务；
- 从数据模型开始预留未来多用户。

## 2. 总体架构

### 2.1 目标形态

```text
Browser
  |
  | HTTPS / JSON REST / upload
  v
TypeScript SPA
  |
  v
FastAPI REST API
  |
  +-- Application services
  |     +-- Fact service
  |     +-- Requirement profile service
  |     +-- Resume workspace service
  |     +-- Version service
  |     +-- Evidence service
  |     +-- Template service
  |     +-- Export service
  |     +-- AI orchestration service
  |
  +-- Repositories
  |     +-- SQL repository
  |     +-- File repository
  |     +-- AI provider adapter
  |
  +-- SQLite (development/local)
  +-- Local file storage (development/local)
  |
  +-- PostgreSQL adapter (future)
  +-- Object storage adapter (future)
```

### 2.2 分层职责

| 层 | 责任 | 不负责的内容 |
| --- | --- | --- |
| SPA | 页面状态、结构化编辑、预览、差异展示、交互校验 | 事实规则、版本落库和权限判断 |
| REST API | 认证上下文、请求校验、资源访问和错误映射 | 直接承担复杂页面状态 |
| 应用服务 | 编排业务流程、事务边界和版本规则 | HTML 页面布局 |
| 领域模型 | 事实、画像、简历、版本和证据的业务约束 | 数据库连接细节 |
| 仓储 | 数据和文件的持久化抽象 | 决定产品行为 |
| 渲染/导出 | 将结构化内容和模板转为 HTML/ZIP | 修改事实资料 |
| AI 适配器 | 对接不同模型服务并统一结果 | 自动发布正式版本 |

### 2.3 产品与技术优先级

```text
functional-design.md
        |
        v
technical-design.md
        |
        v
project-plan.md
        |
        v
implementation
```

技术设计如果发现无法满足功能设计，应提出替代实现并修改技术方案。不得通过删除来源关系、取消版本、跳过用户确认或把正式简历重新绑定事实库来简化实现。

## 3. 领域对象

### 3.1 对象关系

跨模块基数和依赖见[系统关系总图](domain/system-map.md)。本技术设计只保留集成约束：

- Workspace `1 : 0..N` RequirementProfile；画像 `1 : 0..N` JobOpportunity。
- 画像 `1 : 0..N` LinkedResume；画像 `1 : 0..1` active Resume。
- LinkedResume `0..1 : 1` Resume；Resume `1 : 1` WorkingCopy；Resume `1 : 1..N` ResumeVersion。
- 资料库 Fact/Evidence 通过当前使用表和正式版本快照被 Resume 引用。
- Template 是全局只读目录；Workspace `1 : 0..1` TemplatePreference。
- AI、ZIP、多用户和投递跟踪为 deferred，不进入当前目标 ER。

旧实现中的 `ResumeIdentity`、`TemplateVersion` 和固定版本视觉只出现在迁移映射中。

### 3.2 User 与 Workspace

即使本地模式只有一个使用者，也应在所有业务对象上保留 `workspace_id`，并通过工作区确定数据隔离边界。未来多用户时，用户可以属于一个或多个工作区；权限不应依赖全局单例资料。

本地模式启动时创建或选择一个默认用户和默认工作区，不需要第一阶段实现完整注册登录，但服务层不能假设所有表只有一条记录。

### 3.3 FactRecord 与 FactCategory

资料域实体、字段、业务身份键、强类型明细、受控扩展字段和物理约束统一见[资料库关系规范](resource-library/design.md)。实现围绕 `FactRecord`、分类 schema、强类型明细和字段级审计建立事务化领域命令，不把新旧字段混写在兼容 `content` JSON 中。

旧迁移中的 `content` 只作为一次性输入；运行事实的结构化字段来自对应分类明细和受控扩展字段。分类不能在普通编辑中原地修改，转类、合并和拆分都必须记录旧新 ID 映射。

### 3.4 Evidence

证据是工作区内可复用的独立材料，类型的必填元数据、有效/失效/归档状态、不可变内容和事实引用规则以[资料库关系规范](resource-library/design.md)为准。

同一证据可以被多条事实和多个简历区块复用。证据 URL、文件引用、文件属性或说明内容变化时创建新证据并归档旧记录；标题和状态的修改通过证据审计记录。简历的展示方式保存在简历当前使用或正式版本快照关系中，而不是写回证据本体。

### 3.5 岗位画像与招聘机会

完整字段、复制命令和生命周期见[岗位画像模块规范](domain/job-profile/design.md)。技术边界如下：

- `RequirementProfile` 是可复用岗位基线，按工作区隔离；
- `JobOpportunity` 只属于一个画像，画像可有 `0..N` 条机会；
- 画像与机会使用追加式审计，不建立不可变版本；
- 同画像最多一份 active Resume，历史归档/回收 Resume 可多条；
- 正式版本保存画像和机会快照，画像后续修改不覆盖正文。

### 3.6 Resume 与临时草稿

正式简历对象统一为 `Resume`，数据库 ID 即业务身份。`ResumeIdentity` 和 `identity_key` 只存在于旧迁移输入，不再出现在 API、URL 或用户文案中。

`LinkedResume` 保存临时选择；转化后保留草稿并记录唯一来源 Resume。简历内修改借来的画像时自动复制画像字段，不复制机会，原画像不变。

### 3.7 ResumeWorkingCopy

每份 Resume 恰有一份工作副本。目标状态拆成三个正交维度：

```text
content_state:       clean | dirty
evidence_sync_state: clean | pending | conflict
baseline_state:      current | stale
```

工作副本另保存 `base_version_id` 和 `pending_reason`。未保存正文与证据同步待处理可以同时存在，不能压成一个互斥状态。正文仍使用受控 Markdown 子集，模板只决定呈现。

### 3.8 ResumeVersion

版本正文、岗位与机会快照、事实来源和证据清单不可变。版本只允许线性追加，禁止更新或删除历史正文。

版本原因只包括 `format_conversion`、`user_save`、`rollback` 和 `evidence_sync`。模板切换、显示名称变化和导出不产生版本。

内容哈希覆盖正文、岗位与机会快照、来源关系和证据清单，不包含模板、文件名、导出时间或 HTML。详细字段见[简历主链模块规范](domain/resume/design.md)。

## 4. 生命周期与事务

### 4.1 临时简历

临时简历不是 `ResumeVersion`，而是由需求画像、事实资料当前值、用户选择状态和当前模板计算出的实时视图。草稿状态为 `open / converted / abandoned`，转化后保留并记录来源 Resume。

临时简历只支持选择事实条目、调整顺序和预览；不提供文本编辑、人工改写、AI 修改或正式正文保存能力。这些操作只在转化后的正式简历工作副本中可用。

临时视图的生成流程：

1. 加载需求画像和最新招聘机会信息。
2. 读取当前未归档事实资料。
3. 使用推荐服务提供排序辅助，但不强制筛选。
4. 生成初始结构化内容和来源引用。
5. 将用户选择结果保存为临时工作状态。
6. 使用选定模板渲染实时预览。

### 4.2 转为正式简历

用户确认转化后，系统在同一事务中完成以下操作：

1. 将临时选择结果复制为正式简历结构和工作副本；
2. 创建正式简历的第一个不可变版本 `v1`；
3. 将版本原因设为 `format_conversion`，用户可见原因显示为“格式化简历、未润色”；
4. 将该版本设为当前正式版本；
5. 将工作副本的 `base_version_id` 指向 `v1`，供用户继续人工或 AI 编辑。
6. 将 LinkedResume 标记为 `converted` 并记录 `converted_resume_id`。
7. 同一画像已有 active Resume 时拒绝转化。

转化后的工作副本仍然可以有未保存修改，但这些修改不能回写或覆盖 `v1`。用户后续点击正式保存时，从当前工作副本追加 `v2` 或更高版本。

### 4.3 正式保存

正式保存必须在一个事务中完成：

1. 校验工作副本的结构、来源和证据引用。
2. 读取当前版本号并申请下一个线性版本号。
3. 保存完整内容快照、岗位/机会快照、来源关系和证据清单。
4. 写入版本原因和变更摘要。
5. 更新 `current_version_id`。
6. 记录操作者和时间。

如果并发保存检测到当前版本已经变化，应拒绝覆盖并要求重新载入工作副本；本地单用户模式也应使用同一规则，避免未来扩展时改变行为。

### 4.4 从历史版本编辑和回退

从历史版本编辑时，系统复制该版本到工作副本。用户可以修改后保存为新版本。

回退操作也只把历史版本复制到工作副本。用户确认并保存后生成新的当前版本，版本原因标记为 `rollback`。原历史版本和被回退前的当前版本都保留。

不支持传统 Git 分支和合并。用户如果要从新的岗位基线创建另一份正式简历，应使用另一份画像创建新的 `Resume`，而不是在原 Resume 上建立隐藏分支。

### 4.5 事实变化

事实条目普通变化不会修改正式简历正文或自动生成正式版本。系统通过 `source_refs` 查询受影响的正式简历区块，显示差异提醒：

- 来源内容被修改；
- 来源内容被归档或删除；
- 来源证据发生变化。

用户可以选择性地把事实变化同步到工作副本；同步后的正式保存由用户触发并使用 `user_save` 原因。

### 4.6 证据变化（target）

证据变化需要自动保持当前交付物的证据清单一致：

1. 证据服务完成文件、链接或说明的事务提交。
2. 查询引用该证据的当前正式简历。
3. 以每份简历最近一个已保存版本为基线，生成只包含证据关系和附件清单变化的自动版本。
4. 若存在未保存工作副本，将最新证据变化合并到工作副本的证据状态，但不覆盖正文修改，并标记工作副本为“证据更新待处理”。
5. 自动版本原因设为 `evidence_sync`；旧版本继续保留旧证据清单和旧导出哈希。
6. 如果证据引用或用户未保存的展示设置无法安全合并，则保留工作副本并创建待处理状态，不覆盖用户内容。

自动版本不能包含用户尚未显式保存的人工或 AI 正文修改。用户必须显式保存，正文变化才可以进入正常正式版本。

### 4.7 简历内修改画像与恢复冲突

在简历内修改借来的岗位要求时：

1. 复制当前画像字段创建新的 active 画像。
2. 不复制原画像的招聘机会。
3. 当前 Resume 改指新画像，原画像及其机会保持不变。
4. 下一次正常正式保存把新画像和当前机会写入版本快照。

同一画像已有 active Resume 时恢复旧 Resume，接口返回冲突。界面只允许“归档当前 Resume 后恢复旧记录”或“取消”，不能静默形成两个 active。

## 5. 模板与渲染

### 5.1 模板职责

模板只负责把结构化简历内容呈现为 HTML，不负责选择事实、修改正文或决定版本。模板应通过稳定的渲染上下文读取区块，而不是直接依赖某一个数据库表的全部字段。

### 5.2 Template

模板是系统全局内置只读目录。Template 保存稳定 key、渲染器 key、支持区块和 available/retired 状态，不建立用户可见 TemplateVersion。

模板代码原地升级，Resume 保存当前 template_id。模板变化不修改内容哈希、不产生版本、不修饰正文。模板不支持的区块必须在预览校验中报错，不能静默丢失内容。

历史版本只保证正文、岗位、来源和证据可复现；所有版本使用 Resume 当前模板渲染，允许视觉改变。详细规则见[模板与交付模块规范](domain/rendering-delivery/design.md)。

### 5.3 渲染流程

```text
ResumeVersion
  +-- structured content
  +-- source/evidence manifest
  `-- current Resume template
          |
          v
     render context
          |
          v
       HTML
```

渲染器应在输出前检查：必填字段、外链协议、附件相对路径、未支持区块和模板错误。渲染失败不得生成半成品并标记为成功。

## 6. 导出与文件存储

### 6.1 FileStorage 接口

```text
put(stream, metadata) -> storage_key, checksum
open(storage_key) -> readable stream
mark_unavailable(storage_key) -> result
exists(storage_key) -> boolean
```

用户操作只能将证据标记失效或归档，不触发物理删除。物理文件清理如果未来需要实现，只能作为独立的、可审计的存储回收任务，并不得破坏历史版本复现。开发期实现为工作区内的本地附件目录，目录路径不得由用户输入直接决定。上传层执行 PDF、PNG、JPEG、WEBP 白名单校验、单文件 10 MB 限制和单简历附件包 100 MB 限制。未来实现可以替换为 S3 兼容对象存储，不改变领域服务接口。

### 6.2 ZIP 导出结构

> ZIP、附件目录和 `manifest.json` 属于 deferred 目标；当前已实现独立 HTML 导出。

```text
{readable-name}-v{version}.zip
|-- resume.html
|-- attachments/
|   |-- evidence-001.ext
|   `-- evidence-002.ext
`-- manifest.json
```

目标 `manifest.json` 记录 Resume、版本、导出时间、当前 Template、证据名称、附件路径和校验和。HTML 使用包内相对路径引用附件；外部链接保留为可点击 URL。

导出服务必须防止路径穿越、重复文件名覆盖、非法 MIME 类型和 ZIP 炸弹式输入。文件名使用用户可读名称和稳定版本号；修改显示名称不改变 Resume ID 和历史版本关系。每次导出追加 ExportEvent。

## 7. AI 服务设计（deferred）

### 7.1 适配接口

```text
AiProvider.generate_edit(request) -> AiEditResult

AiEditRequest
  provider_model
  target_profile
  selected_fact_content
  selected_evidence_metadata
  current_blocks
  user_instruction

AiEditResult
  proposed_blocks
  changed_block_ids
  explanation
  warnings
  provider_metadata
```

应用服务只依赖 `AiProvider` 接口，不绑定具体厂商。云端或本地模型均可作为适配器实现。

### 7.2 发送和变更规则

- 用户显式选择发送范围后才发起请求。
- 默认只发送当前区块、用户选定的事实来源、关联证据元数据、相关岗位画像字段和用户指令。
- 不发送附件原文件、未选中的事实、其他简历或工作区无关内容。
- AI 可以写入工作副本，但不能写入不可变版本。
- AI 结果应用前保存修改前后的结构化差异。
- `AiChangeRecord` 记录模型、请求范围、时间、结果和用户是否应用。
- AI 返回失败、超时或无法解析时，工作副本保持不变。
- AI 输出不得自动提升事实可信度，也不得创建虚构来源或证据。

## 8. REST API 设计

API 使用资源化 JSON 接口。具体字段以功能设计书和领域模型为准，以下是第一阶段的资源边界和主要操作。

| 资源 | 主要接口 | 用途 |
| --- | --- | --- |
| facts | `GET/POST/PATCH /api/facts` | 事实资料查询和维护 |
| deletion | `DELETE /api/facts/{id}`、`DELETE /api/requirement-profiles/{id}`、`DELETE /api/resumes/{id}` | 先移入回收站；事实仅在没有当前或正式历史引用且二次确认后清理为匿名墓碑 |
| recovery | `POST /api/{resource}/{id}/restore` | 恢复进入回收站的资料、画像或正式简历 |
| fact audits | `GET /api/facts/{id}/audits` | 查看事实修改记录 |
| evidence | `GET/POST/PATCH /api/evidence`、`GET /api/evidence/{id}/file` | 证据上传、链接、说明、归档和文件内联预览；不提供物理删除 |
| fact evidence | `GET /api/facts/{id}/evidence`、`POST /api/evidence`、`POST /api/evidence/upload` | 查询、添加链接和上传事实证据 |
| profile photo | `GET/POST /api/facts/{id}/profile-photo`、`DELETE /api/profile-photos/{id}`、`POST /api/profile-photos/{id}/restore` | 档案照片上传、当前照片、历史照片、移除与恢复；当前照片元数据进入基本信息块，上传变化同步到现有工作副本，HTML 导出将原图内嵌为 data URL |
| profiles | `GET/POST/PATCH /api/requirement-profiles` | 需求画像管理 |
| opportunities | `GET/POST/PATCH /api/opportunities` | 招聘机会来源管理 |
| linked resumes | `GET/POST/PATCH /api/linked-resumes` | 临时联动简历和选择状态 |
| resumes | `GET/POST/PATCH /api/resumes` | 正式 Resume；ID 即身份，不返回 identity_key |
| resume profile copy | `PATCH /api/resumes/{id}/profile` | 简历内修改画像时复制画像，不复制机会 |
| working copies | `GET/PATCH /api/resumes/{id}/working-copy` | 正式简历工作副本编辑 |
| versions | `GET /api/resumes/{id}/versions` | 版本历史和差异 |
| version actions | `POST /api/resumes/{id}/versions/{version}/restore` | 从历史版本恢复工作副本 |
| templates | `GET /api/templates` | 全局 only-read 模板目录 |
| template preferences | `GET/PATCH /api/template-preferences` | 工作区默认和最近使用模板 |
| AI | `POST /api/ai/edit` | deferred；未来生成待确认的工作副本修改 |
| exports | `POST /api/resumes/{id}/versions/{version}/export` | 生成当前模板下的 HTML 并追加 ExportEvent；ZIP 为 deferred |
| export events | `GET /api/export-events` | 查询版本、模板、警告和输出哈希 |

### 8.1 通用 API 规则

- 所有业务资源必须带工作区归属并在服务端校验。
- `PATCH` 只修改当前工作状态，不直接修改正式历史。
- 正式保存使用显式动作接口，例如 `POST /api/resumes/{id}/save`。
- 版本接口只允许读取、比较和恢复，不允许直接修改版本。
- 上传接口返回证据 ID 和校验和，不返回任意服务器绝对路径。
- 错误响应包含稳定错误码、用户可读消息和可选字段级错误。
- 并发更新使用版本号或 `ETag` 检测，冲突返回 `409 Conflict`。

### 8.2 差异 API

差异比较以结构化区块为单位返回：

```json
{
  "from_version": 2,
  "to_version": 4,
  "changes": [
    {
      "section_id": "experience",
      "block_id": "block-1",
      "kind": "modified",
      "before": "旧内容",
      "after": "新内容",
      "source_refs_changed": false,
      "evidence_refs_changed": true
    }
  ]
}
```

比较服务不能只比较最终 HTML，因为 HTML 中的排版变化不应掩盖正文、来源和证据的业务变化。

### 8.3 事实写入与响应

`v2.0.0` 运行契约只接受受控分类代码与字段对象，不再接受旧 `category`、`details` 或 `content`：

```json
{
  "category_code": "experience",
  "schema_version_id": 3,
  "title": "机器人数据采集项目",
  "fields": {
    "experience_kind": "project",
    "period_text": "2026.05 - 至今",
    "organization": "实验室",
    "work_summary": "完成数据采集与模型训练。"
  },
  "tags": ["具身智能", "数据采集"],
  "skill_ids": [12, 15]
}
```

响应额外返回 `business_key`、`skill_group`、`linked_skills` 和 `evidence_count`。业务键由分类规范化字段生成，只在同一工作区和分类的非墓碑事实中唯一。技能必须引用工作区 `skill_groups`，成果主经历必须引用 `experience` 分类事实。

待处理事项使用 `GET/PATCH /api/pending-issues`，每条返回 `section_code`、`block_key` 和显式 `source`；招聘机会统一使用 `GET/POST /api/opportunities` 与 `PATCH/DELETE /api/opportunities/{id}`。

## 9. 前端实现设计

### 9.1 应用区域

SPA 至少包含以下区域：

- 事实资料库；
- 证据管理；
- 需求画像和招聘机会；
- 临时简历；
- 正式简历列表和 Resume 详情；
- 结构化编辑器；
- 版本历史与差异比较；
- 模板管理；
- 预览和导出。

### 9.2 状态边界

- 服务器状态由 API 数据和查询缓存管理。
- 编辑器状态只代表当前工作副本，未保存修改不能伪装成正式版本。
- 每次进入历史版本编辑都创建新的前端工作副本状态。
- AI 结果先进入待应用状态，用户确认后才更新工作副本。
- 证据自动同步以最近已保存版本生成自动版本；如果工作副本存在未保存修改，只更新其证据状态并显示“证据更新待处理”，不覆盖正文。

### 9.3 结构化编辑器

编辑器不直接以 HTML 源码为主要编辑对象。每个区块应提供：

- 内容编辑；
- 来源引用查看；
- 证据选择；
- 显示/隐藏；
- 顺序调整；
- AI 修改入口；
- 修改前后差异查看。

HTML 只作为预览和导出结果。用户内容不能直接变成任意 HTML、脚本或自定义 CSS；任何未来扩展都必须通过模板预先定义的受控区块实现。

v1 前端实现将正式编辑区拆分为只读 `Canvas` 和独立 `BlockEditor` 弹层：`BlockView` 只渲染预览，点击/右键时通过 `BlockRef` 打开编辑卡片或上下文菜单；标题、字段和正文更新仍写入结构化 `content`，继续沿用分页片段 `fragment_index`，不改变工作副本与版本接口。

## 10. 数据库、迁移与兼容性

### 10.1 数据库策略

当前正式目标使用 SQLite，资料域可执行结构以[目标 SQL](resource-library/schema.sql)为准。业务服务仍依赖仓储和事务接口，未来若进入多用户服务端阶段，再另立存储迁移决策。

必须使用正式迁移工具管理表结构、索引和数据转换。应用启动不能把 `create_all` 作为迁移方案。

### 10.2 索引要求

至少建立以下索引：

- 所有业务表的 `workspace_id`；
- `Resume(workspace_id, requirement_profile_id)` 在 active 状态下的部分唯一索引；
- `ResumeVersion(resume_id, version_number)` 唯一索引；
- 文件证据 `Evidence(workspace_id, checksum)` 唯一索引；
- 来源引用查询所需的关联表索引；
- 需求画像与招聘机会的外键索引；
- 审计记录的对象 ID 与时间索引。

### 10.3 旧数据迁移

迁移工具应能把当前数据库中的个人资料、教育、经历、技能、成果、岗位和模板转换为新领域对象。资料事实只写入系统登记的结构化字段；无法自动判断的原文保留在脱敏执行记录或来源说明中，不通过自定义字段重新引入。项目链接改为挂接经历或成果的证据。

当前旧的简历记录如只有条目 ID，迁移后只能作为“来源不完整的旧记录”处理；新系统正式版本必须保存完整结构化快照。

`0016_target_resource_model` 已把现有数据库从 revision 15 升级到目标资源模型：复制旧事实、明细、标签、证据、审计和简历引用，规范化业务键与技能分组，随后删除旧表和兼容列；`0017_target_guard_completion` 补齐字段目录、标签命名空间和扩展值的目标触发器；`0018_profile_photos` 增加个人档案照片及历史关系。该迁移链不可逆，正式执行前必须保留数据库备份。

迁移过程要求：

1. 迁移前备份数据库和输出目录。
2. 在事务或可恢复批次中执行。
3. 输出未映射字段和失败条目报告。
4. 迁移后运行数量、来源和渲染校验。
5. 不覆盖原始数据库文件，直到验收完成。

## 11. 安全与隐私

- 多用户边界以工作区归属为基础，所有查询和写入都必须服务端过滤。
- 本地模式仍应避免把个人资料暴露到任意外部地址。
- AI 请求必须显式确认发送范围，并记录发送对象和模型信息。
- 文件上传检查大小、类型、文件名和内容校验和。
- HTML 模板和用户内容分离，模板执行权限只对可信模板开放。
- 外部链接只允许安全协议，避免脚本协议和路径注入。
- ZIP 导出防止路径穿越和附件覆盖。
- 正式版本和审计记录只追加，不允许普通接口删除。
- 当前未来工作区按平等成员预留；后续实现账号体系时再增加会话、密码哈希、CSRF 或同等请求来源防护。

## 12. 测试设计

### 12.1 领域与服务测试

- 同一画像最多一份 active Resume；归档和回收历史可保留多条。
- 临时简历读取事实当前值，事实变化后重新打开能反映变化。
- 临时简历自身不会产生正式版本；转化动作会立即创建原因标记为 `format_conversion` 的正式 `v1`。
- 转化后的后续正式保存从 `v2` 开始生成连续版本号和完整快照。
- 历史版本不能被 PATCH 或 DELETE。
- 从历史版本恢复后保存会生成新的当前版本。
- 普通事实变化只产生差异提醒，不自动生成正式版本。
- 证据变化自动生成 `evidence_sync` 版本。
- 证据自动版本以最近已保存版本为基线，不包含未保存的人工或 AI 正文。
- 证据变化可以合并到未保存工作副本的证据状态，但不能覆盖正文；无法合并时创建待处理状态。
- 简历内修改画像会复制新画像且不复制机会，原画像保持不变。
- 并发保存返回冲突，不覆盖他人的工作副本。
- 不支持的证据格式或超过 10 MB 单文件/100 MB 单包限制时上传失败。

### 12.2 API 测试

- 资源无法跨工作区读取或修改。
- 字段错误返回稳定错误码和字段级信息。
- AI 发送范围未确认时请求被拒绝。
- AI 失败时工作副本不发生变化。
- 差异 API 返回区块级、来源级和证据级差异。
- 导出接口只能导出存在且有权限访问的正式版本。

### 12.3 渲染与导出测试

- 历史版本的正文、岗位、来源和证据在资料变化后仍能复现；模板视觉允许更新。
- 外部链接可点击，附件使用有效相对路径。
- 未选择的证据不进入 HTML 或 ZIP。
- 文件名、MIME 类型和附件校验和写入清单。
- 模板不支持的区块不会静默丢失。
- 中文内容、长文本和空区块不会导致渲染失败。

### 12.4 前端测试

- 工作副本未保存时离开页面会提示丢失修改。
- AI 修改可以查看差异并应用或放弃。
- 历史版本可以加载到工作副本而不修改历史。
- 证据自动同步后显示版本原因和变更摘要。
- 模板预设的可选区块可以启用、关闭、排序和恢复；用户不能自由新增结构。

## 13. 性能与可运维性

- 列表查询分页，避免一次加载整个事实库或附件目录。
- 大文件上传使用流式写入，避免完整载入内存。
- HTML 预览可以缓存版本级渲染结果，但缓存键必须包含 ResumeVersion 和当前 Template；模板升级需使缓存失效。
- ZIP 导出使用版本快照，不读取会变化的临时内容。
- 关键操作记录结构化日志：保存版本、证据同步、AI 调用、导出和迁移。
- 失败的 AI 调用和导出任务可重试，但重试不能重复创建相同版本。
- 未来需要异步任务时，把 AI 和导出放入任务队列，接口仍返回可查询的任务状态。

## 14. 实现验收

技术实现只有同时满足以下条件才算完成：

1. 用户可以按功能设计书完成事实维护、画像管理、临时简历、正式编辑、版本管理和导出。
2. 正式简历正文与事实库独立，但来源和证据关系可追溯。
3. 历史版本能够复现当时的业务内容、岗位、来源和证据清单；视觉可按当前模板演进。
4. 证据变化自动产生有明确原因的正式版本。
5. AI 不会绕过用户确认创建正式版本。
6. 技术接口无法绕过工作区隔离、版本不可变和权限校验。
7. 模板和存储实现可以在不改变业务行为的前提下替换。
8. 所有待确认设计项都通过可替换配置或清晰边界隔离，不把暂定方案写死在历史数据中。
