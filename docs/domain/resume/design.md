# 简历主链模块规范

> 文档状态：living-design
>
> 适用模块：临时简历、正式简历、工作副本、版本、来源引用、跨模块待处理
>
> 上位文档：[功能设计书](../../functional-design.md)、[交互界面设计书](../../interaction-design.md)
>
> 结构真源：[schema.sql](schema.sql)
>
> 中文图册：[简历主链中文关系图、UML、状态与时序](diagrams-zh.md)

## 1. 对象

| 编号 | 对象 | 说明 |
| --- | --- | --- |
| RS-ENT-001 | LinkedResume | 从岗位画像创建的临时选择状态 |
| RS-ENT-002 | Resume | 正式简历文档；数据库 ID 即稳定身份 |
| RS-ENT-003 | ResumeVersion | 正式简历的不可变业务快照 |
| RS-ENT-004 | ResumeWorkingCopy | Resume 当前唯一的可编辑副本 |
| RS-ENT-005 | ResumeFactUse | 当前 Resume 使用的事实 |
| RS-ENT-006 | VersionFactSnapshot | 正式版本固定的事实来源 |
| RS-ENT-007 | ResumeEvidenceUse | 当前 Resume 使用的证据与展示方式 |
| RS-ENT-008 | VersionEvidenceSnapshot | 正式版本固定的证据与展示方式 |
| RS-ENT-009 | PendingIssue | 跨模块待处理事项 |

`ResumeIdentity` 不再出现在目标模型。迁移时 `ResumeIdentity.id` 直接映射为 `Resume.id`，用户可见和 API 层都不再出现 `identity_key`。

## 2. 关系

| 编号 | 关系 | 基数与规则 |
| --- | --- | --- |
| RS-REL-001 | RequirementProfile → LinkedResume | `1 : 0..N` |
| RS-REL-002 | LinkedResume → Resume | `0..1 : 1`；Resume 的来源草稿可空且唯一 |
| RS-REL-003 | RequirementProfile → Resume | 全部记录 `1 : 0..N`，active 至多 `1` |
| RS-REL-004 | Resume → WorkingCopy | `1 : 1` |
| RS-REL-005 | Resume → ResumeVersion | `1 : 1..N`，线性编号 |
| RS-REL-006 | Resume → ResumeFactUse | `1 : 0..N` |
| RS-REL-007 | ResumeVersion → VersionFactSnapshot | `1 : 0..N` |
| RS-REL-008 | Resume → ResumeEvidenceUse | `1 : 0..N` |
| RS-REL-009 | ResumeVersion → VersionEvidenceSnapshot | `1 : 0..N` |
| RS-REL-010 | Resume/Template → Template | 每个 Resume 当前只有一个模板 |
| RS-REL-011 | Fact/Evidence → PendingIssue | 每条业务对象可有 `0..N` 个待处理事项 |

## 3. 生命周期

### RS-STS-001 Resume

`active ↔ archived`，`active/archived → recycled`，`recycled → active/archived/purged`。同一画像最多一份 active；恢复旧 Resume 时如果新 Resume 已 active，必须返回冲突，由用户选择“归档当前并恢复旧记录”或“取消”。

### RS-STS-002 LinkedResume

`open → converted` 或 `open → abandoned`。`converted` 必须指向一份 Resume；`abandoned` 和 `open` 不得带转化目标。

### RS-STS-003 WorkingCopy

三个正交维度：

| 维度 | 值 |
| --- | --- |
| 内容 | `clean / dirty` |
| 证据同步 | `clean / pending / conflict` |
| 版本基线 | `current / stale` |

因此 `dirty + pending + current` 是合法状态，表示正文有未保存修改且证据同步待处理。

### RS-STS-004 PendingIssue

`open → resolved` 或 `open → dismissed`；终态不回到 open，新的变化创建新事项。

## 4. 不变量

| 编号 | 不变量 |
| --- | --- |
| RS-INV-001 | Resume.current_version 必须属于同一 Resume。 |
| RS-INV-002 | LinkedResume 最多转化一次且转化状态与目标 ID 必须一致。 |
| RS-INV-003 | 一个草稿最多产生一份 Resume，一份 Resume 最多有一个来源草稿。 |
| RS-INV-004 | 版本正文、岗位快照、来源、证据和内容哈希不可修改或删除。 |
| RS-INV-005 | 版本来源和证据快照不可修改或删除。 |
| RS-INV-006 | 仍有正式 Resume 历史的画像不能清理为 purged。 |
| RS-INV-007 | 所有引用必须属于同一工作区。 |
| RS-INV-008 | Resume 内容哈希覆盖正文、岗位快照、来源关系和证据清单，不包含模板或导出结果。 |

## 5. 命令

| 编号 | 命令 | 结果 |
| --- | --- | --- |
| RS-CMD-001 | 创建临时简历 | 创建 `open` LinkedResume；读取画像、事实和模板 |
| RS-CMD-002 | 转化正式简历 | 同事务创建 Resume 与 `format_conversion` v1、WorkingCopy、来源/证据使用，并把草稿改为 converted |
| RS-CMD-003 | 保存正式版本 | 校验三项工作副本状态，追加线性 ResumeVersion 和版本快照，更新 current_version |
| RS-CMD-004 | 恢复历史版本 | 把版本内容复制到 WorkingCopy，基线标记 stale，下一次保存形成 rollback |
| RS-CMD-005 | 简历内修改画像 | 自动复制画像字段，不复制机会；当前 Resume 改指新画像，原画像不变 |
| RS-CMD-006 | 切换模板 | 更新 Resume 和 WorkingCopy 的 `template_id`；不改内容哈希、不产生版本 |
| RS-CMD-007 | 证据变化 | 目标能力：更新当前证据关系并按规则产生 `evidence_sync` 版本；正文修改仍由用户保存 |
| RS-CMD-008 | 解决待处理事项 | 只把对应 PendingIssue 设为 resolved/dismissed，不直接改写 Resume 正文 |

## 6. API 契约

| 资源/命令 | 目标接口 | 规则 |
| --- | --- | --- |
| 临时简历 | `/api/linked-resumes` | 创建、保存选择和查询预览 |
| 转化 | `POST /api/linked-resumes/{id}/convert` | 返回 `resume_id`，建立 origin draft |
| 正式简历 | `/api/resumes` | 返回 Resume，不含 identity_key |
| 简历内复制画像 | `PATCH /api/resumes/{id}/profile` | 有字段变化则自动创建新画像，不复制机会 |
| 工作副本 | `/api/resumes/{id}/working-copy` | 三项状态分开返回 |
| 正式保存 | `POST /api/resumes/{id}/save` | 追加版本，不接受模板导致的内容哈希变化 |
| 历史恢复 | `POST /api/resumes/{id}/versions/{n}/restore` | 恢复旧内容到新 WorkingCopy |
| 模板切换 | `PATCH /api/resumes/{id}/template` | 只改当前 Resume 视觉偏好 |
| 待处理 | `/api/pending-issues` | 返回显式来源对象和定位字段 |

自 `v2.0.0` 起上述接口为运行契约。资源不得回退到 `identity_key` 或旧 `pending-items` 命名；待处理事项统一使用 `/api/pending-issues`。

## 7. 迁移边界

| 当前实现 | 目标 |
| --- | --- |
| `resume_identities` | `resumes` |
| `ResumeIdentity.identity_key` | 删除，Resume.id 即身份 |
| `resume_versions.template_version_id` | 删除版本级模板；使用 `resumes.template_id` |
| `resume_working_copies.dirty` | `content_state` |
| 无证据同步状态 | `evidence_sync_state` |
| `base_version_id` 推导 | 显式 `baseline_state` |
| `pending_items` | `pending_issues` 显式来源外键 |
