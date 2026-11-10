# 模板与交付中文关系图、UML 和时序

> 文档状态：living-design（配套图册）

> 所有关系边按“左侧数量 : 右侧数量”读取。本图不使用鸦脚符号。

## 1. 关系图

```mermaid
flowchart LR
    WS["工作区"]
    PREF["模板偏好"]
    TEMPLATE["全局内置模板"]
    RESUME["正式简历"]
    VERSION["正式版本"]
    EXPORT["导出事件"]

    WS -->|"1 : 1｜模板偏好"| PREF
    PREF -->|"0..N : 1｜默认模板"| TEMPLATE
    PREF -->|"0..N : 1｜最近模板"| TEMPLATE
    TEMPLATE -->|"1 : 0..N｜当前视觉"| RESUME
    RESUME -->|"1 : 1..N｜版本"| VERSION
    VERSION -->|"1 : 0..N｜重复导出"| EXPORT
    TEMPLATE -->|"1 : 0..N｜实际渲染"| EXPORT
```

## 2. UML 类图

```mermaid
classDiagram
    direction LR
    class TEMPLATE["模板"] {
        +整数 id
        +文本 templateKey
        +文本 displayName
        +文本 rendererKey
        +JSON supportedSections
        +文本 status
        +整数 successorTemplateId
    }
    class PREF["工作区模板偏好"] {
        +整数 workspaceId
        +整数 defaultTemplateId
        +整数 lastSelectedTemplateId
    }
    class RESUME["正式简历"] {
        +整数 id
        +整数 templateId
    }
    class VERSION["正式版本"] {
        +整数 id
        +整数 resumeId
        +哈希 contentHash
    }
    class EXPORT["导出事件"] {
        +整数 id
        +整数 resumeVersionId
        +整数 templateId
        +文本 format
        +JSON warnings
        +布尔 forced
        +哈希 outputHash
    }

    TEMPLATE "1" --> "0..N" PREF : 默认或最近
    TEMPLATE "1" --> "0..N" RESUME : 当前模板
    RESUME "1" --> "1..N" VERSION : 线性版本
    VERSION "1" --> "0..N" EXPORT : 多次导出
    TEMPLATE "1" --> "0..N" EXPORT : 渲染
```

## 3. 模板生命周期

```mermaid
stateDiagram-v2
    [*] --> available
    available --> available : 原地更新代码
    available --> retired : 退役
    retired --> [*]
```

退役模板不能重新启用；已有 Resume 若仍引用退役模板，只能切换到可用模板或 successor。

## 4. 渲染与导出

```mermaid
sequenceDiagram
    actor U as 用户
    participant R as Resume
    participant V as ResumeVersion
    participant T as 当前Template
    participant X as 导出服务
    participant E as ExportEvent

    U->>R: 请求导出 vN
    R->>V: 读取正文、岗位、来源和证据快照
    R->>T: 读取 Resume 当前模板
    T->>X: 提供当前渲染器
    X->>X: 生成 HTML
    X->>E: 追加导出事件与输出哈希
    X-->>U: 返回生成文件
```

同一版本再次导出时，正文业务内容保持一致，但模板升级可能改变视觉和 `output_hash`。

## 5. 必要字段

| 实体 | 必要字段 | 约束 |
| --- | --- | --- |
| Template | `id`, `template_key`, `display_name`, `description`, `renderer_key`, `supported_sections_json`, `default_sections_json`, `status`, `successor_template_id`, `updated_at` | template_key 全局唯一；只能依次退役 |
| WorkspaceTemplatePreference | `workspace_id`, `default_template_id`, `last_selected_template_id`, `updated_at` | 每工作区一行 |
| Resume | `template_id` | 当前 Resume 的视觉选择；不进入内容哈希 |
| ExportEvent | `id`, `workspace_id`, `resume_id`, `resume_version_id`, `template_id`, `format`, `warnings_json`, `forced`, `content_hash`, `output_hash`, `created_at` | 可重复；输出哈希逐次记录 |
