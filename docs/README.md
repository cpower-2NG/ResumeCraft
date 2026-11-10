# ResumeCraft 文档索引

本页是 ResumeCraft 文档的入口，定义当前文档、历史快照和权威边界。

当前代码基线：`v2.0.0`

当前迁移版本：`0018_profile_photos`

索引更新日期：`2026-11-10`

## 1. 先看什么

第一次接触项目时，按以下顺序阅读：

1. [项目 README](../README.md)：用途、启动、目录和本地数据边界。
2. [功能设计书](functional-design.md)：用户能做什么，以及业务规则是什么。
3. [交互界面设计书](interaction-design.md)：页面如何组织，操作和反馈如何呈现。
4. [能力状态矩阵](capabilities.md)：哪些能力已经实现，哪些仍是目标。
5. [技术实现设计书](technical-design.md)：系统如何分层、存储、迁移和导出。

开发具体模块时，再阅读对应的领域规范。字段、外键和触发器发生争议时，以模块 `schema.sql` 的结构为准。

## 2. 文档状态

| 状态 | 含义 | 使用方式 |
| --- | --- | --- |
| living-design | 当前产品、交互或技术基准 | 实现与测试的验收依据 |
| living-plan | 当前路线、能力状态或测试计划 | 记录目标和差距，不重新定义业务行为 |
| historical | 特定版本或调查的历史快照 | 仅用于追溯，不作为当前规则 |

文档冲突时先确认职责，再修改负责该问题的文档；文件日期或篇幅不构成权威顺序。

## 3. 现行产品与交互

| 文档 | 状态 | 负责内容 |
| --- | --- | --- |
| [功能设计书](functional-design.md) | living-design | 产品目标、核心流程、业务规则和验收标准 |
| [交互界面设计书](interaction-design.md) | living-design | 信息架构、页面入口、操作、状态和错误反馈 |
| [能力状态矩阵](capabilities.md) | living-plan | implemented / target / deferred 能力及其依据 |

## 4. 当前技术基线

| 文档 | 状态 | 负责内容 |
| --- | --- | --- |
| [技术实现设计书](technical-design.md) | living-design | 总体架构、API、数据迁移、存储、安全和测试设计 |
| [系统关系总图](domain/system-map.md) | living-design | 跨模块边界、依赖和不变量 |
| [资料库关系规范](resource-library/design.md) | living-design | 事实、证据、字段、标签、审计和回收 |
| [资料库中文图册](resource-library/diagrams-zh.md) | living-design | 关系基数、UML、必要字段和关键流程 |
| [资料库 SQL 契约](resource-library/schema.sql) | living-design | 资料域可执行结构真源 |
| [岗位画像规范](domain/job-profile/design.md) | living-design | RequirementProfile、JobOpportunity、审计和复制 |
| [岗位画像 SQL](domain/job-profile/schema.sql) | living-design | 岗位画像模块结构真源 |
| [简历主链规范](domain/resume/design.md) | living-design | 临时简历、Resume、工作副本、版本和来源快照 |
| [简历主链 SQL](domain/resume/schema.sql) | living-design | 简历主链模块结构真源 |
| [模板与交付规范](domain/rendering-delivery/design.md) | living-design | 模板、渲染、偏好和导出事件 |
| [模板与交付 SQL](domain/rendering-delivery/schema.sql) | living-design | 交付模块结构真源 |

## 5. 计划与验证

| 文档 | 状态 | 负责内容 |
| --- | --- | --- |
| [项目计划](project-plan.md) | living-plan | 阶段路线、依赖、已确认决策和后续工作 |
| [测试说明](test-guide.md) | living-plan | 测试命令、覆盖范围、版式验收和已知缺口 |

## 6. 历史记录

以下文档保留当时的发布、调查或审计事实，不定义当前实现：

| 文档 | 内容 |
| --- | --- |
| [发布记录](release-notes.md) | 各版本范围和验证结果 |
| [系统差异调查日志](investigation-log-2026-09-13.md) | 2026-09-13 的调查快照 |
| [修订审计](revision-audit.md) | 2026-09 修订问题和当时验收口径 |
| [UI 审计](ui-audit-2026-09-12.md) | 2026-09-12 的前后端对照快照 |

历史文档中的旧版本号、旧接口和旧交互结论不能覆盖当前设计。个别带有真实资料或本地路径的工作记录仅保留在开发者本机，不进入公开仓库。

## 7. 权威顺序

1. 产品行为以功能设计书为准。
2. 页面与交互在功能设计约束下以交互界面设计书为准。
3. 实体、字段、关系和数据库约束以对应 `design.md` 与 `schema.sql` 为准。
4. 跨模块关系以系统关系总图和模块外键契约为准。
5. 一项能力是否已经实现以能力状态矩阵和可运行测试为准，不以路线图或历史发布记录为准。
6. 历史文档只用于追溯。

## 8. 维护规则

- 行为变化同时更新功能或交互设计、能力矩阵和相关测试。
- 结构变化同时更新模块 `design.md`、`schema.sql` 和 Alembic 迁移。
- 发布前更新发布记录和测试说明。
- 现行文档说明状态、适用模块和上位文档；历史文档明确标注“历史快照”。
- 不把真实数据库、附件、简历正文、个人联系方式或本地绝对路径写入公开文档。

文档契约由 `tests/test_domain_specs.py`、`tests/test_resource_library_spec.py` 和 `scripts/check_*.py` 检查。
