# ResumeCraft 能力状态矩阵

> 文档状态：living-plan
>
> 用途：区分已实现、目标设计和暂缓能力，避免把目标文字误判为当前功能。
>
> 规则：产品行为仍由[功能设计书](functional-design.md)定义；目标结构和模块边界由各领域规范定义。
>
> 基线：代码 `v2.0.0`，数据库迁移 `0018_profile_photos`，最近核对 `2026-11-10`。

## 1. 状态定义

| 状态 | 含义 |
| --- | --- |
| implemented | 当前运行代码和测试已经提供该能力 |
| target | 已确认目标，但当前实现尚未完成或尚未完全对齐 |
| deferred | 已明确暂缓，当前不承诺交付时间和最终数据形状 |

## 2. 能力清单

| 编号 | 能力 | 状态 | 当前依据 / 剩余差距 |
| --- | --- | --- | --- |
| CAP-FACT-001 | 分类事实、结构化明细、审计和回收站 | implemented | `fact_records`、五类强类型明细、`fact_audit_events`、证据审计和回收测试 |
| CAP-FACT-002 | 强类型关联、经历场景、成果归属、技能关联和受控标签 | implemented | `category_code / schema_version_id / business_key`、技能分组、经历技能关联与资源 API |
| CAP-FACT-003 | 目标强类型资料库迁移 | implemented | `0016_target_resource_model`、`0017_target_guard_completion` 与 `0018_profile_photos`；迁移链在干净数据库和升级副本上通过检查 |
| CAP-FACT-004 | 个人档案照片上传、替换、历史、移除和恢复 | implemented | `0018_profile_photos`、档案照片 API 与个人档案编辑卡片 |
| CAP-FACT-005 | 档案照片在模板中的显示、裁剪和正式版本视觉快照 | target | 照片资产与档案关系已实现；模板排版和 Resume 展示设置留待独立实现 |
| CAP-PROFILE-001 | 岗位画像 CRUD 与回收恢复 | implemented | `tests/test_profiles.py` |
| CAP-PROFILE-002 | 招聘机会 API | implemented | `tests/test_profiles.py`；前端管理入口仍不完整 |
| CAP-PROFILE-003 | 画像字段审计与自动复制画像 | implemented | `profile_audit_events`、简历内画像复制 API 与目标测试 |
| CAP-PROFILE-004 | 每条招聘机会只归属一个画像、画像可有多条机会 | implemented | 当前 `job_opportunities` 和 API |
| CAP-RESUME-001 | 临时简历选择和模板预览 | implemented | `tests/test_linked_resume.py` |
| CAP-RESUME-002 | 临时简历转正式 `v1` | implemented | 当前转换 API 和生命周期测试 |
| CAP-RESUME-003 | 一画像最多一份 active Resume | implemented | 转换、恢复与部分唯一索引共同保证 |
| CAP-RESUME-004 | 临时草稿到 Resume 的来源关系 | implemented | `converted_resume_id` 与一次性转化约束 |
| CAP-RESUME-005 | 简历上下文修改画像时自动复制画像 | implemented | `PATCH /api/resumes/{id}/profile` 与审计 |
| CAP-RESUME-006 | 工作副本、线性版本、历史恢复 | implemented | `tests/test_resume_lifecycle.py` |
| CAP-RESUME-007 | 正文、证据同步和基线三项正交状态 | implemented | `content_state`、`evidence_sync_state`、`baseline_state` |
| CAP-EVIDENCE-001 | 事实证据的链接、文件、内联预览、失效和恢复 | implemented | `tests/test_facts.py`、`tests/test_comprehensive_workflows.py` |
| CAP-EVIDENCE-002 | 简历当前引用和正式版本证据快照 | implemented | 当前/版本事实与证据引用表 |
| CAP-EVIDENCE-003 | 证据变化自动生成 `evidence_sync` 版本 | implemented | 证据元数据/状态变化不吞并未保存正文 |
| CAP-TEMPLATE-001 | 内置模板选择、A4 预览和导出渲染 | implemented | 13 个 active 内置模板；模板测试 |
| CAP-TEMPLATE-002 | 全局内置模板目录和工作区偏好 | implemented | 全局 `templates` 表和工作区偏好 API |
| CAP-TEMPLATE-003 | 模板切换不创建正式版本 | implemented | 只更新 Resume/WorkingCopy 当前模板与偏好 |
| CAP-TEMPLATE-004 | 用户创建、复制或编辑模板 | deferred | 当前产品明确只读选择 |
| CAP-EXPORT-001 | 确定正式版本的独立 HTML 导出 | implemented | `tests/test_export.py` |
| CAP-EXPORT-002 | 导出事件、警告和强制导出审计 | implemented | 默认阻止有警告的导出，并逐次记录 ExportEvent |
| CAP-EXPORT-003 | ZIP、附件目录和 `manifest.json` | deferred | 当前只交付独立 HTML |
| CAP-AI-001 | AI 工作副本编辑与变更记录 | deferred | 当前没有 AI Provider 或变更记录实现 |
| CAP-MULTI-001 | 多用户、账号和工作区成员权限 | deferred | 当前固定单工作区本地模式 |
| CAP-TRACK-001 | 投递状态、联系人和面试跟踪 | deferred | 当前只保存招聘机会原文与画像关联 |
| CAP-DOC-001 | living / historical 文档状态和统一索引 | implemented | 本文件、`docs/README.md`、模块图册和文档检查器 |

## 3. 已完成迁移映射

| 当前实现 | 目标模型 | 迁移规则 |
| --- | --- | --- |
| `resume_identities` / `ResumeIdentity` | `resumes` / `Resume` | 保留 `id`；一份记录映射为一份正式简历；移除用户可见 `identity_key` |
| `identity_key` | 无 | 不再参与 URL、导出文件名或业务身份判断 |
| `linked_resumes` | `linked_resumes` | 保留草稿；增加 `converted_resume_id` 和状态 |
| `resume_working_copies.dirty` | `content_state` | `dirty=true → dirty`，否则 `clean` |
| 隐含证据同步/冲突状态 | `evidence_sync_state` | 当前默认 `clean`；目标流程写入 `pending/conflict` |
| `base_version_id` 比较 | `baseline_state` | 基线等于当前版本为 `current`，否则 `stale` |
| `resume_templates` + `template_versions` | 全局 `templates` | 每个 slug 解析到稳定 Template；旧版本 ID 保留在迁移映射中 |
| ResumeVersion 的 `template_version_id` | Resume 的 `template_id` | 版本不再冻结视觉；迁移时把对应模板归属到 Resume |
| 直接从 API 下载 HTML | `export_events` | 导出业务记录写入事件表，生成文件仍可即时返回 |

## 4. 当前实现注意事项

- 现有后端测试安全区以当前实现为准；能力状态矩阵不会自动改变运行行为。
- `tests/conftest.py` 继续使用内存 SQLite，不得连接或修改真实 `data/resume_workbench.db`。
- 2026-11-09 已完成目标强类型资料库、REST 契约和 SPA 的整体迁移；2026-11-10 在迁移链末尾加入 `0018_profile_photos`，当前目标 revision 为 `0018_profile_photos`。
- 数据库、备份和附件只保存在开发者本机，`data/` 与常见数据库文件均由 `.gitignore` 排除，不进入源码仓库。
- 当前模板目录包含 13 个 active 内置模板；14 个旧 slug 通过 `RETIRED_TEMPLATES` 解析到承接模板。能力描述不把历史模板行计为可选模板。
- 发布记录中的版本号只说明历史发布，不决定当前能力状态。
