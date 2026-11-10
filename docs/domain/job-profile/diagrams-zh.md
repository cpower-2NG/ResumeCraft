# 岗位画像中文关系图与 UML

> 文档状态：living-design（配套图册）

> 阅读方式：每条边按“左侧数量 : 右侧数量”读取。
>
> 本图不使用鸦脚符号。原总体英文图保留。

## 1. 关系图

```mermaid
flowchart LR
    WS["工作区"]
    PROFILE["岗位画像"]
    OPP["招聘机会"]
    AUDIT["画像审计"]
    DRAFT["临时简历"]
    RESUME["正式简历"]

    WS -->|"1 : 0..N｜拥有画像"| PROFILE
    PROFILE -->|"1 : 0..N｜关联机会"| OPP
    PROFILE -->|"1 : 0..N｜修改记录"| AUDIT
    PROFILE -->|"1 : 0..N｜派生草稿"| DRAFT
    PROFILE -->|"1 : 0..N｜历史正式简历"| RESUME
    PROFILE -->|"1 : 0..1｜active 正式简历"| RESUME
```

```mermaid
flowchart LR
    OLD["原画像\n开放状态"]
    NEW["新画像\nactive"]
    OLDOPP["原画像招聘机会\n保留在原画像"]
    CURRENT["当前正式简历"]

    OLD -->|"1 : 1｜复制字段"| NEW
    OLD -->|"1 : 0..N｜不复制"| OLDOPP
    CURRENT -->|"修改前 N : 1"| OLD
    CURRENT -->|"修改后 N : 1"| NEW
```

自动复制画像时，原画像、原招聘机会不变；新画像默认没有机会，当前正式简历改指新画像。

## 2. UML 类图

```mermaid
classDiagram
    direction LR
    class WS["工作区"] {
        +整数 id
    }
    class PROFILE["岗位画像 RequirementProfile"] {
        +整数 id
        +整数 workspaceId
        +文本 name
        +文本 roleDirection
        +JSON coreRequirements
        +文本 generalRequirements
        +文本 responsibilities
        +文本 resumeStrategy
        +文本 rawJd
        +文本 sourceNote
        +文本 status
    }
    class OPP["招聘机会 JobOpportunity"] {
        +整数 id
        +整数 workspaceId
        +整数 requirementProfileId
        +文本 company
        +文本 title
        +文本 rawJd
        +文本 url
        +文本 sourceNote
        +文本 status
    }
    class AUDIT["画像审计"] {
        +整数 id
        +整数 profileId
        +文本 action
        +JSON changedFields
        +JSON beforeValues
        +JSON afterValues
    }
    class DRAFT["临时简历"] {
        +整数 id
        +整数 requirementProfileId
    }
    class RESUME["正式简历"] {
        +整数 id
        +整数 requirementProfileId
        +文本 status
    }

    WS "1" --> "0..N" PROFILE : 拥有
    PROFILE "1" --> "0..N" OPP : 来源
    PROFILE "1" --> "0..N" AUDIT : 审计
    PROFILE "1" --> "0..N" DRAFT : 派生草稿
    PROFILE "1" --> "0..N" RESUME : 全部正式简历
    PROFILE "1" --> "0..1" RESUME : active
```

## 3. 必要字段

### RequirementProfile

| 字段 | 中文含义 | 规则 |
| --- | --- | --- |
| `id` | 画像主键 | 稳定 ID |
| `workspace_id` | 工作区 | 必填外键 |
| `name` | 画像名称 | 必填 |
| `role_direction` | 岗位方向 | 可空 |
| `core_requirements_json` | 核心技术要求 | JSON 数组 |
| `general_requirements` | 一般要求 | 可空 |
| `responsibilities` | 主要职责 | 可空 |
| `resume_strategy` | 简历强调方向 | 可空 |
| `raw_jd` | 主参考 JD 文本 | 可空 |
| `source_note` | 来源备注 | 可空 |
| `status` | 生命周期 | active/archived/recycled/purged |
| `archived_at` | 归档时间 | 归档状态使用 |
| `recycled_at` | 回收时间 | 回收状态使用 |
| `purged_at` | 清理时间 | 终态使用 |
| `created_at` | 创建时间 | UTC ISO-8601 |
| `updated_at` | 修改时间 | UTC ISO-8601 |

### JobOpportunity

| 字段 | 中文含义 | 规则 |
| --- | --- | --- |
| `id` | 机会主键 | 稳定 ID |
| `workspace_id` | 工作区 | 必须与画像一致 |
| `requirement_profile_id` | 所属画像 | 必填 |
| `company` | 公司 | 可空 |
| `title` | 招聘岗位名称 | 可空 |
| `raw_jd` | 招聘原文 | 可空 |
| `url` | 招聘链接 | 可空 |
| `source_note` | 来源备注 | 可空 |
| `status` | 生命周期 | active/archived/recycled/purged |
| `created_at` / `updated_at` | 时间 | UTC ISO-8601 |

### ProfileAuditEvent

| 字段 | 中文含义 |
| --- | --- |
| `id` | 审计事件 ID |
| `workspace_id` / `profile_id` | 所属工作区和画像 |
| `actor_user_id` | 操作者 |
| `action` | created/updated/archived/restored/recycled/purged/cloned/opportunity_changed |
| `changed_fields_json` | 变化字段 |
| `before_values_json` / `after_values_json` | 变化前后值 |
| `related_profile_ids_json` | 复制等操作的关联画像 |
| `reason` | 操作原因 |
| `created_at` | 事件时间 |
