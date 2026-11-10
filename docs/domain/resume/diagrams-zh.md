# 简历主链中文关系图、UML 与流程

> 文档状态：living-design（配套图册）

> 所有关系边按“左侧数量 : 右侧数量”读取。本图不使用鸦脚符号。

## 1. 核心关系

```mermaid
flowchart LR
    PROFILE["岗位画像"]
    DRAFT["临时简历 LinkedResume"]
    RESUME["正式简历 Resume"]
    COPY["工作副本"]
    VERSION["正式版本"]
    FACT["事实"]
    EVID["证据"]
    ISSUE["待处理事项"]
    TEMPLATE["当前模板"]

    PROFILE -->|"1 : 0..N｜派生草稿"| DRAFT
    PROFILE -->|"1 : 0..N｜历史 Resume"| RESUME
    PROFILE -->|"1 : 0..1｜active Resume"| RESUME
    DRAFT -->|"0..1 : 1｜来源草稿"| RESUME
    RESUME -->|"1 : 1｜唯一工作副本"| COPY
    RESUME -->|"1 : 1..N｜线性版本"| VERSION
    RESUME -->|"1 : 0..N｜当前事实引用"| FACT
    VERSION -->|"1 : 0..N｜历史事实快照"| FACT
    RESUME -->|"1 : 0..N｜当前证据引用"| EVID
    VERSION -->|"1 : 0..N｜历史证据快照"| EVID
    RESUME -->|"1 : 1｜当前视觉"| TEMPLATE
    FACT -->|"1 : 0..N｜可产生问题"| ISSUE
    EVID -->|"1 : 0..N｜可产生问题"| ISSUE
    RESUME -->|"1 : 0..N｜受影响"| ISSUE
```

## 2. UML 类图

```mermaid
classDiagram
    direction LR
    class PROFILE["岗位画像"] {
        +整数 id
        +文本 status
    }
    class DRAFT["临时简历 LinkedResume"] {
        +整数 id
        +整数 requirementProfileId
        +整数 templateId
        +JSON selection
        +文本 status
        +整数 convertedResumeId
    }
    class RESUME["正式简历 Resume"] {
        +整数 id
        +整数 requirementProfileId
        +整数 originLinkedResumeId
        +整数 templateId
        +文本 displayName
        +整数 currentVersionId
        +文本 status
    }
    class COPY["工作副本"] {
        +整数 resumeId
        +整数 baseVersionId
        +JSON content
        +文本 contentState
        +文本 evidenceSyncState
        +文本 baselineState
        +文本 pendingReason
    }
    class VERSION["正式版本"] {
        +整数 id
        +整数 resumeId
        +整数 versionNumber
        +JSON content
        +JSON profileSnapshot
        +哈希 contentHash
        +文本 reason
    }
    class FACT["事实来源"] {
        +整数 id
    }
    class EVID["证据来源"] {
        +整数 id
    }
    class ISSUE["待处理事项"] {
        +整数 id
        +文本 kind
        +文本 status
        +整数 factId
        +整数 evidenceId
        +整数 profileId
        +整数 resumeId
    }
    PROFILE "1" --> "0..N" DRAFT : 派生
    DRAFT "0..1" --> "1" RESUME : 转化来源
    PROFILE "1" --> "0..1" RESUME : active
    RESUME "1" --> "1" COPY : 工作副本
    RESUME "1" --> "1..N" VERSION : 版本
    RESUME "1" --> "0..N" FACT : 当前引用
    VERSION "1" --> "0..N" FACT : 历史快照
    RESUME "1" --> "0..N" EVID : 当前引用
    VERSION "1" --> "0..N" EVID : 历史快照
    FACT "1" --> "0..N" ISSUE : 来源
    EVID "1" --> "0..N" ISSUE : 来源
```

## 3. 状态机

```mermaid
stateDiagram-v2
    state "临时草稿" as Draft {
        [*] --> open
        open --> converted : 转化成功
        open --> abandoned : 放弃
        converted --> [*]
        abandoned --> [*]
    }

    state "正式简历" as Resume {
        [*] --> active
        active --> archived : 主动停用
        archived --> active : 恢复
        active --> recycled : 删除
        archived --> recycled : 删除
        recycled --> active : 恢复
        recycled --> archived : 停用
        recycled --> purged : 终态清理
        purged --> [*]
    }
```

## 4. 创建与转化时序

```mermaid
sequenceDiagram
    actor U as 用户
    participant UI as 简历工作区
    participant D as 临时简历
    participant P as 岗位画像
    participant T as 模板目录
    participant R as 正式简历
    participant V as 正式版本

    U->>UI: 从画像创建临时简历
    UI->>P: 读取当前画像和机会
    UI->>T: 读取可用模板
    UI->>D: 创建 open 草稿
    U->>D: 选择事实并调整顺序
    U->>UI: 转为正式简历
    UI->>D: 校验草稿仍为 open
    UI->>R: 创建 active Resume 与唯一工作副本
    R->>V: 创建 format_conversion v1
    V->>V: 保存画像、来源和证据快照
    UI->>D: 标记 converted 并写 converted_resume_id
```

## 5. 简历内修改画像

```mermaid
sequenceDiagram
    actor U as 用户
    participant E as 正式简历编辑
    participant R as Resume
    participant P1 as 原岗位画像
    participant P2 as 新岗位画像

    U->>E: 修改借来的岗位要求
    E->>P1: 读取画像字段
    E->>P2: 复制画像字段
    Note over P2: 不复制招聘机会
    E->>R: 将 requirement_profile_id 改为新画像
    Note over P1: 原画像和原招聘机会保持不变
```

## 6. 保存与恢复

```mermaid
sequenceDiagram
    actor U as 用户
    participant C as 工作副本
    participant R as Resume
    participant V as 正式版本

    U->>C: 编辑正文或调整来源
    C->>C: content_state = dirty
    U->>R: 保存正式版本
    R->>C: 校验 content/evidence/baseline 三项状态
    R->>V: 追加下一版本和来源快照
    R->>C: content_state = clean
    U->>R: 以 vN 创建工作副本
    R->>C: 复制历史内容
    C->>C: baseline_state = stale
    U->>R: 再次保存
    R->>V: 追加 reason=rollback 的新版本
```

## 7. 必要字段

| 实体 | 必要字段 | 关键约束 |
| --- | --- | --- |
| LinkedResume | `id`, `workspace_id`, `requirement_profile_id`, `template_id`, `selection_json`, `status`, `converted_resume_id`, `created_at`, `updated_at` | status 为 open/converted/abandoned；converted 必须指向 Resume |
| Resume | `id`, `workspace_id`, `requirement_profile_id`, `origin_linked_resume_id`, `template_id`, `display_name`, `current_version_id`, `status` | 每画像最多一份 active；草稿来源唯一 |
| ResumeVersion | `id`, `workspace_id`, `resume_id`, `version_number`, `content_json`, `profile_snapshot_json`, `source_manifest_json`, `evidence_manifest_json`, `content_hash`, `reason`, `created_at` | 版本号线性唯一；记录不可变 |
| WorkingCopy | `id`, `workspace_id`, `resume_id`, `base_version_id`, `template_id`, `content_json`, `content_state`, `evidence_sync_state`, `baseline_state`, `pending_reason` | 每 Resume 一份；三个状态维度正交 |
| ResumeFactUse | `resume_id`, `fact_id`, `section_code`, `block_key`, `display_order`, `fact_content_hash` | 当前编辑来源 |
| VersionFactSnapshot | `resume_version_id`, `fact_id`, `section_code`, `block_key`, `display_order`, `fact_content_hash` | 历史来源，不可变 |
| ResumeEvidenceUse | `resume_id`, `evidence_id`, `section_code`, `block_key`, `display_mode`, `label`, `display_order` | 展示方式属于引用 |
| VersionEvidenceSnapshot | `resume_version_id`, `evidence_id`, `section_code`, `block_key`, `display_mode`, `label`, `display_order` | 历史证据，不可变 |
| PendingIssue | `id`, `workspace_id`, `kind`, `status`, `fact_id`, `evidence_id`, `profile_id`, `resume_id`, `section_code`, `block_key`, `message` | 至少一个来源外键非空，不得跨工作区 |
