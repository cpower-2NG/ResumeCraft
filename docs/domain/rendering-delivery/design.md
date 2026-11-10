# 模板与交付模块规范

> 文档状态：living-design
>
> 适用模块：全局内置模板、工作区模板偏好、HTML/ZIP 渲染、导出事件
>
> 上位文档：[功能设计书](../../functional-design.md)、[交互界面设计书](../../interaction-design.md)
>
> 结构真源：[schema.sql](schema.sql)
>
> 中文图册：[模板与交付中文关系图、UML 和时序](diagrams-zh.md)

## 1. 对象

| 编号 | 对象 | 说明 |
| --- | --- | --- |
| RD-ENT-001 | Template | 系统全局内置模板与当前渲染器 |
| RD-ENT-002 | WorkspaceTemplatePreference | 工作区默认和最近选择模板 |
| RD-ENT-003 | ExportEvent | 一次具体导出的事实记录 |

模板不是用户内容，不归属工作区，也不进入 ResumeVersion 的内容哈希。

## 2. 关系

| 编号 | 关系 | 基数 |
| --- | --- | --- |
| RD-REL-001 | Template → Resume | `1 : 0..N`，Resume 保存当前视觉选择 |
| RD-REL-002 | Template → WorkspaceTemplatePreference.default | `1 : 0..N` |
| RD-REL-003 | Template → WorkspaceTemplatePreference.last_selected | `1 : 0..N` |
| RD-REL-004 | ResumeVersion → ExportEvent | `1 : 0..N` |
| RD-REL-005 | Template → ExportEvent | `1 : 0..N` |

一个 Template 可被多份 Resume 和导出事件引用。同一 ResumeVersion 可以导出多次，事件逐次追加。

## 3. 模板规则

### RD-STS-001 模板状态

模板状态只有 `available → retired`。用户只能为新建或切换操作选择 available 模板。retired 模板不可回到 available；需要替代时登记 successor。

### 3.1 视觉透明

- 模板代码原地升级，不建立用户可见 TemplateVersion 历史。
- Resume 的历史版本不冻结模板或 HTML。
- 切换模板只更新 Resume/WorkingCopy 的模板选择，不改变正文哈希，不标记内容脏，不创建正式版本。
- 同一正式版本未来再次导出时允许视觉及输出哈希变化。

### 3.2 内容哈希

ResumeVersion 的 `content_hash` 只覆盖正文、岗位快照、来源关系和证据清单。模板 key、文件名、导出时间和生成 HTML 不参与。

## 4. 不变量

| 编号 | 不变量 |
| --- | --- |
| RD-INV-001 | 被 Resume 引用的模板不能物理删除。 |
| RD-INV-002 | 导出事件只追加，不可更新或删除。 |
| RD-INV-003 | ExportEvent 的 ResumeVersion 必须属于同一 Resume 和工作区。 |
| RD-INV-004 | 模板更新不触发 ResumeVersion，也不改变 Resume 内容哈希。 |
| RD-INV-005 | 导出结果必须记录实际使用的模板、警告和输出哈希。 |

## 5. 命令

| 编号 | 命令 | 规则 |
| --- | --- | --- |
| RD-CMD-001 | 选择 Resume 模板 | 更新 Resume 和 WorkingCopy 的 template_id；不产生版本 |
| RD-CMD-002 | 更新工作区偏好 | 更新默认或最近使用模板 |
| RD-CMD-003 | 渲染正式版本 | 读取版本内容、当前 Resume 模板和证据快照 |
| RD-CMD-004 | 导出 HTML | 生成文件并追加 ExportEvent |
| RD-CMD-005 | 导出 ZIP | deferred；实现后同样追加 ExportEvent |

## 6. API 契约

| 资源/命令 | 目标接口 | 说明 |
| --- | --- | --- |
| 模板目录 | `GET /api/templates` | 只返回全局 available 模板 |
| 工作区偏好 | `GET/PATCH /api/template-preferences` | 默认和最近使用模板 |
| 简历模板 | `PATCH /api/resumes/{id}/template` | 只改视觉，不生成版本 |
| HTML 导出 | `POST /api/resumes/{id}/versions/{n}/export` | 返回文件并写 ExportEvent |
| 导出事件 | `GET /api/export-events` | 查询历史导出记录 |

自 `v2.0.0` 起上述接口为运行契约。模板对象以 `id` 作为稳定选择 ID，`template_key` 作为稳定代码键；不再返回或接受 `template_version_id`。

## 7. 迁移边界

当前 `resume_templates` 与 `template_versions` 暂时按工作区保存。目标把模板收敛为全局 Template：

- `template.slug` 映射为稳定 `template_key`；
- 同一 key 的当前渲染代码映射为 `renderer_key`；
- 旧 `template_version_id` 只用于历史迁移，不进入目标 ResumeVersion；
- ResumeVersion 中的模板引用迁移到所属 Resume 的 `template_id`；
- 旧模板行和退役 slug 保留为迁移记录，不计入可选模板目录。
