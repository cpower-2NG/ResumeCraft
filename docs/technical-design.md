# 简历工作台实现设计书

> 文档性质：目标系统的技术说明
>
> 上位文档：[功能设计书](functional-design.md)
>
> 设计原则：实现方式必须服务于功能设计；技术便利性不能改变产品行为

## 1. 文档地位与范围

本文档说明如何实现功能设计书中的简历工作台，不重新定义产品功能。功能设计书是产品行为的唯一权威来源；当本文档与功能设计书冲突时，以功能设计书为准并修正本文档。

本文档描述目标架构。当前工作区中的 FastAPI、SQLite、服务端模板和现有数据只能作为迁移输入，不作为新系统的结构约束。

目标系统需要支持：

- 本地优先运行；
- 结构化简历编辑；
- 事实资料与正式简历正文分离；
- 来源关系和证据追踪；
- 工作副本与不可变版本；
- 证据变化自动生成版本；
- 模板版本和 HTML/ZIP 导出；
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

```text
User
  +-- Workspace
        +-- FactRecord
        |     +-- Evidence
        |     `-- FactAudit
        |
        +-- RequirementProfile
        |     `-- JobOpportunity
        |
        +-- ResumeIdentity
        |     +-- ResumeWorkingCopy
        |     `-- ResumeVersion
        |           +-- SourceReference
        |           +-- EvidenceManifest
        |           `-- TemplateVersion
        |
        +-- Template
        |     `-- TemplateVersion
        |
        `-- AiChangeRecord
```

### 3.2 User 与 Workspace

即使本地模式只有一个使用者，也应在所有业务对象上保留 `workspace_id`，并通过工作区确定数据隔离边界。未来多用户时，用户可以属于一个或多个工作区；权限不应依赖全局单例资料。

本地模式启动时创建或选择一个默认用户和默认工作区，不需要第一阶段实现完整注册登录，但服务层不能假设所有表只有一条记录。

### 3.3 FactRecord

事实资料采用分类加结构化内容的形式：

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定主键 |
| `workspace_id` | 所属工作区 |
| `category` | 个人信息、教育、经历、技能、成果、链接等 |
| `title` | 条目名称 |
| `content` | 该分类的结构化 JSON 内容 |
| `tags` | 标准化标签集合 |
| `status` | 当前、已归档等 |
| `source_note` | 来源说明 |
| `created_at` / `updated_at` | 时间信息 |

具体分类字段应由领域校验器检查，不应把所有业务字段都退化为无约束文本。新增分类可以增加新的内容校验器和模板适配器，不应修改历史事实的含义。

事实资料采用当前值加审计记录。每次修改写入 `fact_audits`，包含操作者、修改时间、变化摘要和必要的旧值/新值。事实资料不采用正式简历同等级的不可变版本模型。

### 3.4 Evidence

证据是可对外展示的验证材料，与事实条目或正式简历区块建立多对多关系。

```text
Evidence
  id
  workspace_id
  kind: file | link | note
  title
  description
  url              # link 类型使用
  storage_key      # file 类型使用
  mime_type
  size_bytes
  checksum
  status: active | archived
  created_at
  updated_at
```

文件内容通过 `FileStorage` 接口保存，数据库只保存元数据和存储键。文件名、MIME 类型、大小和校验和必须在上传时校验。外部链接保存原始 URL，并在渲染时进行安全协议检查。

第一版文件白名单为 PDF、PNG、JPEG 和 WEBP。单文件最大 10 MB，单份简历附件包最大 100 MB。超过限制或格式不支持时拒绝上传。证据不允许物理删除，只能标记失效或归档。

证据的展示方式不属于证据本体，而属于简历区块与证据的引用关系：

```text
ResumeEvidenceReference
  resume_identity_id / version_id
  section_id / block_id
  evidence_id
  display_mode: hidden | inline_link | attachment | reference
  label
  order
```

同一证据可以被多个事实条目和简历区块复用，每个引用关系独立保存展示方式、说明和排序。

证据更新由事务事件触发正式简历同步。只有影响交付内容的变化才触发同步：正文链接、附件文件、附件说明、引用关系和证据失效。内部备注变化不触发版本。

### 3.5 RequirementProfile

需求画像是复用岗位要求和决定简历身份的对象，不直接等于公司岗位。建议字段如下：

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定主键 |
| `workspace_id` | 所属工作区 |
| `name` | 用户可读名称 |
| `role_direction` | 岗位方向 |
| `core_requirements` | 核心技术要求 |
| `general_requirements` | 一般能力要求 |
| `responsibilities` | 主要职责 |
| `resume_strategy` | 简历强调方向 |
| `fingerprint_candidate` | 系统计算的候选指纹 |
| `identity_key` | 用户确认的简历身份键 |
| `created_at` / `updated_at` | 时间信息 |

`identity_key` 是用户确认的稳定业务键，不直接等同于文件名。系统可以根据标准化字段计算候选指纹，但不能未经用户确认就自动拆分正式简历身份。

候选指纹当前只使用岗位方向、核心技术要求和简历策略。标准化处理为去首尾空格、合并连续空白、英文统一小写、技术要求去重并排序，中文保留原文；简历策略使用归一化后的完整文本。未来词库或 AI 判断只能生成辅助候选值，不能直接改变用户确认的身份键。

### 3.6 JobOpportunity

招聘机会保存画像的具体来源：

- 公司；
- 岗位名称；
- 原始 JD；
- 招聘页面链接；
- 来源备注；
- 关联的 `requirement_profile_id`。

第一阶段不实现投递状态、联系人和提醒，但数据模型应允许后续增加这些字段。

### 3.7 ResumeIdentity

`ResumeIdentity` 表示一份围绕需求画像维护的正式简历。建议字段如下：

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定主键 |
| `workspace_id` | 所属工作区 |
| `requirement_profile_id` | 当前需求画像 |
| `identity_key` | 用户确认的唯一业务键 |
| `display_name` | 用户可读名称 |
| `filename_stem` | 导出文件名基础部分 |
| `current_version_id` | 当前正式版本 |
| `status` | 活跃、归档等 |

同一工作区内，`identity_key` 唯一。`display_name` 和 `filename_stem` 可以变化，但变化不会创建新的简历身份；如果用户确认创建新身份，则新身份必须拥有新的 `identity_key`。

### 3.8 ResumeWorkingCopy

工作副本保存正在编辑的结构化简历内容，并记录其编辑基线：

```text
ResumeWorkingCopy
  resume_identity_id
  base_version_id
  content
  dirty: boolean
  evidence_sync_pending: boolean
  merge_status: clean | pending | conflict
  updated_at
```

`base_version_id` 用于判断工作副本是否落后于当前正式版本。证据自动版本产生后，带有未保存正文的工作副本保持原基线并进入 `evidence_sync_pending` 状态，不能静默覆盖或伪装成已同步。

工作副本的结构化内容示例：

```json
{
  "sections": [
    {
      "id": "section-1",
      "type": "profile",
      "title": "个人简介",
      "order": 10,
      "visibility": "visible",
      "blocks": [
        {
          "id": "block-1",
          "type": "paragraph",
          "content": "经用户编辑的文本",
          "source_refs": ["fact:123"],
          "evidence_refs": ["evidence:456"],
          "origin": "fact | user | ai"
        }
      ]
    }
  ]
}
```

核心区块使用固定类型；模板可以声明可选区块，工作副本只能启用或关闭这些已声明区块，不能自由新增结构、改变布局或编辑模板几何样式。正文内容独立保存，来源引用和证据引用作为元数据保存，不在事实库与简历正文之间建立自动覆盖关系。

正文存储为纯文本加受控 Markdown 子集，允许段落、粗体、斜体、无序列表和链接；禁止标题、表格、图片、HTML、脚本和自定义 CSS。渲染前必须清洗并解析 Markdown，不能直接把用户内容当作 HTML 输出。

### 3.9 ResumeVersion

正式版本是不可变记录，必须保存足以复现交付物的信息：

- 完整结构化简历内容；
- 事实来源引用及其显示状态；
- 证据清单和附件引用；
- 使用的模板版本；
- 需求画像摘要和身份键；
- 版本号、创建人、创建时间和版本原因；
- 内容快照哈希和导出清单哈希。

版本原因至少包括：`format_conversion`、`user_save`、`rollback`、`identity_copy`、`evidence_sync` 和 `template_change`。`format_conversion` 对应用户可见的“格式化简历、未润色”版本原因。

版本只允许在线性链上追加。禁止更新历史版本正文、删除历史版本或把历史版本直接覆盖为当前版本。

## 4. 生命周期与事务

### 4.1 临时简历

临时简历不是 `ResumeVersion`，而是由需求画像、事实资料当前值、用户选择状态和模板当前版本计算出的实时视图。用户选择可以保存为临时工作状态，但该状态不进入正式历史。

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

转化后的工作副本仍然可以有未保存修改，但这些修改不能回写或覆盖 `v1`。用户后续点击正式保存时，从当前工作副本追加 `v2` 或更高版本。

### 4.3 正式保存

正式保存必须在一个事务中完成：

1. 校验工作副本的结构、来源和证据引用。
2. 读取当前版本号并申请下一个线性版本号。
3. 保存完整内容快照、模板版本和证据清单。
4. 写入版本原因和变更摘要。
5. 更新 `current_version_id`。
6. 记录操作者和时间。

如果并发保存检测到当前版本已经变化，应拒绝覆盖并要求重新载入工作副本；本地单用户模式也应使用同一规则，避免未来扩展时改变行为。

### 4.4 从历史版本编辑和回退

从历史版本编辑时，系统复制该版本到工作副本。用户可以修改后保存为新版本。

回退操作也只把历史版本复制到工作副本。用户确认并保存后生成新的当前版本，版本原因标记为 `rollback`。原历史版本和被回退前的当前版本都保留。

不支持传统 Git 分支和合并。用户如果要针对新的需求画像维护另一份简历，应创建新的 `ResumeIdentity`，而不是在原身份上建立隐藏分支。

### 4.5 事实变化

事实条目普通变化不会修改正式简历正文或自动生成正式版本。系统通过 `source_refs` 查询受影响的正式简历区块，显示差异提醒：

- 来源内容被修改；
- 来源内容被归档或删除；
- 来源证据发生变化。

用户可以选择性地把事实变化同步到工作副本；同步后的正式保存由用户触发并使用 `user_save` 原因。

### 4.6 证据变化

证据变化需要自动保持当前交付物的证据清单一致：

1. 证据服务完成文件、链接或说明的事务提交。
2. 查询引用该证据的当前正式简历。
3. 以每份简历最近一个已保存版本为基线，生成只包含证据关系和附件清单变化的自动版本。
4. 若存在未保存工作副本，将最新证据变化合并到工作副本的证据状态，但不覆盖正文修改，并标记工作副本为“证据更新待处理”。
5. 自动版本原因设为 `evidence_sync`；旧版本继续保留旧证据清单和旧导出哈希。
6. 如果证据引用或用户未保存的展示设置无法安全合并，则保留工作副本并创建待处理状态，不覆盖用户内容。

自动版本不能包含用户尚未显式保存的人工或 AI 正文修改。用户必须显式保存，正文变化才可以进入正常正式版本。

### 4.7 新简历身份

需求画像核心字段变化时，系统计算候选指纹差异并提示用户。用户选择创建新身份后：

1. 校验新 `identity_key` 在工作区内唯一。
2. 创建新的 `ResumeIdentity`。
3. 将当前正式版本复制到新身份工作副本。
4. 保留原身份和完整历史。
5. 新身份第一次正式保存时从 `v1` 开始编号。

## 5. 模板与渲染

### 5.1 模板职责

模板只负责把结构化简历内容呈现为 HTML，不负责选择事实、修改正文或决定版本。模板应通过稳定的渲染上下文读取区块，而不是直接依赖某一个数据库表的全部字段。

### 5.2 Template 与 TemplateVersion

模板实体保存名称、说明、支持的区块类型和状态；模板版本保存具体 HTML/CSS、版本号、校验和和创建信息。正式简历版本必须引用确定的模板版本。

模板更新创建新模板版本，不修改历史模板版本。模板不支持的区块必须有明确的降级策略：默认显示为通用文本区块或在预览校验中报错，不能静默丢失内容。

正式简历工作副本可以切换模板。切换模板和可选区块变化属于工作副本变化，用户正式保存后生成新版本；历史版本始终引用原模板版本。模板应声明其支持的核心区块和可选区块，编辑器不得让用户启用模板未声明的区块。

### 5.3 渲染流程

```text
ResumeVersion
  +-- structured content
  +-- source/evidence manifest
  `-- template_version
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

```text
{readable-name}-v{version}.zip
|-- resume.html
|-- attachments/
|   |-- evidence-001.ext
|   `-- evidence-002.ext
`-- manifest.json
```

`manifest.json` 记录简历身份、版本、导出时间、模板版本、证据名称、附件路径和校验和。HTML 使用包内相对路径引用附件；外部链接保留为可点击 URL。

导出服务必须防止路径穿越、重复文件名覆盖、非法 MIME 类型和 ZIP 炸弹式输入。文件名使用用户可读名称和稳定版本号，名称需经过文件系统安全化处理；修改显示名称不改变简历身份键和历史版本关系。

## 7. AI 服务设计

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
| fact audits | `GET /api/facts/{id}/audits` | 查看事实修改记录 |
| evidence | `GET/POST/PATCH /api/evidence` | 证据上传、链接、说明和归档；不提供物理删除 |
| profiles | `GET/POST/PATCH /api/requirement-profiles` | 需求画像管理 |
| opportunities | `GET/POST/PATCH /api/opportunities` | 招聘机会来源管理 |
| linked resumes | `GET/POST/PATCH /api/linked-resumes` | 临时联动简历和选择状态 |
| resume identities | `GET/POST/PATCH /api/resumes` | 正式简历身份管理 |
| working copies | `GET/PATCH /api/resumes/{id}/working-copy` | 正式简历工作副本编辑 |
| versions | `GET /api/resumes/{id}/versions` | 版本历史和差异 |
| version actions | `POST /api/resumes/{id}/versions/{version}/restore` | 从历史版本恢复工作副本 |
| templates | `GET/POST/PATCH /api/templates` | 模板和模板版本管理 |
| AI | `POST /api/ai/edit` | 生成并应用 AI 工作副本修改 |
| exports | `POST /api/resumes/{id}/versions/{version}/export` | 生成 HTML/ZIP 交付物 |

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

## 9. 前端实现设计

### 9.1 应用区域

SPA 至少包含以下区域：

- 事实资料库；
- 证据管理；
- 需求画像和招聘机会；
- 临时简历工作台；
- 正式简历列表和身份详情；
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

## 10. 数据库、迁移与兼容性

### 10.1 数据库策略

开发期和本地模式使用 SQLite；生产或多用户模式使用 PostgreSQL。业务服务依赖仓储和事务接口，不直接依赖 SQLite 特有语法。

必须使用正式迁移工具管理表结构、索引和数据转换。应用启动不能把 `create_all` 作为迁移方案。

### 10.2 索引要求

至少建立以下索引：

- 所有业务表的 `workspace_id`；
- `ResumeIdentity(workspace_id, identity_key)` 唯一索引；
- `ResumeVersion(resume_identity_id, version_number)` 唯一索引；
- `Evidence(workspace_id, checksum)`；
- 来源引用查询所需的关联表索引；
- 需求画像与招聘机会的外键索引；
- 审计记录的对象 ID 与时间索引。

### 10.3 旧数据迁移

迁移工具应能把当前数据库中的个人资料、教育、经历、技能、成果、岗位和模板转换为新领域对象。无法确定的字段保留在来源说明或自定义字段中，不应静默丢弃。

当前旧的简历记录如只有条目 ID，迁移后只能作为“来源不完整的旧记录”处理；新系统正式版本必须保存完整结构化快照。

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

- 同一工作区内重复 `identity_key` 被拒绝，不同工作区可以重复。
- 临时简历读取事实当前值，事实变化后重新打开能反映变化。
- 临时简历自身不会产生正式版本；转化动作会立即创建原因标记为 `format_conversion` 的正式 `v1`。
- 转化后的后续正式保存从 `v2` 开始生成连续版本号和完整快照。
- 历史版本不能被 PATCH 或 DELETE。
- 从历史版本恢复后保存会生成新的当前版本。
- 普通事实变化只产生差异提醒，不自动生成正式版本。
- 证据变化自动生成 `evidence_sync` 版本。
- 证据自动版本以最近已保存版本为基线，不包含未保存的人工或 AI 正文。
- 证据变化可以合并到未保存工作副本的证据状态，但不能覆盖正文；无法合并时创建待处理状态。
- 新身份继承当前版本但从 `v1` 开始独立编号。
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

- 历史版本在事实库、模板和证据发生变化后仍能复现。
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
- HTML 预览可以缓存版本级渲染结果，但缓存键必须包含版本和模板版本。
- ZIP 导出使用版本快照，不读取会变化的临时内容。
- 关键操作记录结构化日志：保存版本、证据同步、AI 调用、导出和迁移。
- 失败的 AI 调用和导出任务可重试，但重试不能重复创建相同版本。
- 未来需要异步任务时，把 AI 和导出放入任务队列，接口仍返回可查询的任务状态。

## 14. 实现验收

技术实现只有同时满足以下条件才算完成：

1. 用户可以按功能设计书完成事实维护、画像管理、临时简历、正式编辑、版本管理和导出。
2. 正式简历正文与事实库独立，但来源和证据关系可追溯。
3. 历史版本能够复现当时的内容、模板和证据清单。
4. 证据变化自动产生有明确原因的正式版本。
5. AI 不会绕过用户确认创建正式版本。
6. 技术接口无法绕过工作区隔离、版本不可变和权限校验。
7. 模板和存储实现可以在不改变业务行为的前提下替换。
8. 所有待确认设计项都通过可替换配置或清晰边界隔离，不把暂定方案写死在历史数据中。
