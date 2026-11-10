# 岗位画像模块规范

> 文档状态：living-design
>
> 适用模块：岗位画像、招聘原文来源、画像审计
>
> 上位文档：[功能设计书](../../functional-design.md)、[交互界面设计书](../../interaction-design.md)
>
> 结构真源：[schema.sql](schema.sql)
>
> 中文图册：[岗位画像中文关系图与 UML](diagrams-zh.md)

## 1. 范围

本规范只定义岗位画像基线及其招聘信息来源，不定义正式简历正文、版本和导出。

## 2. 核心对象

| 编号 | 对象 | 说明 |
| --- | --- | --- |
| JP-ENT-001 | RequirementProfile | 可复用的岗位需求基线 |
| JP-ENT-002 | JobOpportunity | 一条具体招聘原文来源，只归属一个画像 |
| JP-ENT-003 | ProfileAuditEvent | 画像字段、状态、招聘机会和复制动作的追加式审计 |

### 2.1 岗位画像

画像字段包括名称、岗位方向、核心技术要求、一般要求、职责、简历策略、原始 JD、来源备注和生命周期。画像不使用不可变版本；正式简历保存时生成岗位与当前招聘机会快照。

画像不保存 `identity_key`。它不是正式简历的身份，也不直接决定文件名。

### 2.2 招聘机会

招聘机会保存公司、岗位名称、原始 JD、URL 和来源备注。一条机会只属于一个画像，一个画像可以拥有多条机会。

招聘机会是来源材料，不是投递记录。投递状态、联系人和面试流程属于 deferred 能力。

## 3. 关系

| 编号 | 关系 | 基数 |
| --- | --- | --- |
| JP-REL-001 | Workspace → RequirementProfile | `1 : 0..N` |
| JP-REL-002 | RequirementProfile → JobOpportunity | `1 : 0..N` |
| JP-REL-003 | RequirementProfile → ProfileAuditEvent | `1 : 0..N` |
| JP-REL-004 | RequirementProfile → Resume | `1 : 0..N`（其中 active Resume 至多 1） |
| JP-REL-005 | RequirementProfile → LinkedResume | `1 : 0..N` |

## 4. 状态与不变量

### JP-STS-001 画像状态

`active ↔ archived`，`active/archived → recycled`，`recycled → active/archived/purged`。`purged` 是终态。

### JP-STS-002 招聘机会状态

招聘机会使用相同生命周期。终态画像清理时，其机会行同步清除业务正文并保留墓碑关系。

| 编号 | 不变量 |
| --- | --- |
| JP-INV-001 | 画像审计只追加，不可更新或删除。 |
| JP-INV-002 | 画像及其机会不可跨工作区关联。 |
| JP-INV-003 | 同一画像最多一份 active Resume；目标由简历模块部分唯一索引保证。 |
| JP-INV-004 | 画像字段修改不直接覆盖任何正式简历正文或历史版本。 |
| JP-INV-005 | 正式保存把当时画像和机会内容写入 ResumeVersion 快照。 |

## 5. 命令

| 编号 | 命令 | 规则 |
| --- | --- | --- |
| JP-CMD-001 | 创建画像 | 创建 active 画像并写 created 审计 |
| JP-CMD-002 | 更新画像 | 字段级前后值审计；不触发简历正文更新 |
| JP-CMD-003 | 归档/恢复 | 写状态审计 |
| JP-CMD-004 | 回收/清理 | 正式简历仍引用时禁止 purged |
| JP-CMD-005 | 自动复制画像 | 复制画像字段，不复制招聘机会；写 cloned 审计，新旧 ID 双向可追溯 |
| JP-CMD-006 | 维护招聘机会 | 校验画像工作区，写 opportunity_changed 审计 |

自动复制发生在“正式简历内修改借来的画像”场景。原画像和原机会保持不变，新画像默认没有机会。

## 6. 跨模块边界

- LinkedResume 和 Resume 通过 `profile_id` 引用本模块。
- 正式简历保存时读取当前画像和 active 招聘机会生成快照。
- 画像不直接保存简历正文或版本号。
- 当前实现使用 `requirement_profiles` 和 `job_opportunities`；目标结构额外要求画像审计和自动复制命令。
