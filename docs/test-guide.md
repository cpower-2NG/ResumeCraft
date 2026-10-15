# ResumeCraft 测试说明

## 1. 如何运行

后端测试在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

前端单元测试（Vitest，覆盖 SPA 分页模型 `lib/resume.ts`）：

```powershell
cd web
npx vitest run
npx tsc -b --noEmit
```

浏览器交互冒烟测试：

```powershell
cd web
npm install
npx playwright install chromium
npm run test:ui
```

脚本位于 `web/scripts/interaction-smoke.mjs`，会真实点击资料库、岗位画像、ResumeCraft、回收站和返回按钮，填写并保存资料与岗位画像，并把浏览器控制台错误作为失败条件。

### 版式与分页的实测验收

分页估算（`LAYOUT_METRICS`/`PAGE_BUDGET_PX`）是纯计算，既可能低估（导出正文越过 A4 底边被裁掉）也可能高估（页面过早切断）。改动版式、列宽、字号或估算常数后，必须按下面的闭环复测：

```powershell
# 1) 生成 12 个模板 × 3 种密度样本的导出 HTML 到 output/tmp
.\.venv\Scripts\python.exe scripts\gen_samples.py
# 2) 无头浏览器逐页测量填充率与裁切像素
cd web; node scripts\measure_pages.mjs ..\output\tmp > ..\output\tmp\metrics.json; cd ..
# 3) 汇总并过验收门槛（任何一页不得裁切，非末页填充不得低于 74%）
.\.venv\Scripts\python.exe scripts\summarize_metrics.py
```

并排节奏（整宽行 vs 并排行、以及哪些栏目被并排）用 `node web/scripts/count_pairs.mjs output/tmp` 看：按版式检查"整宽为主、并排为辅"，并确认单栏系列没有任何并排行。

门槛取 74% 而不是更高：栏目是原子单元，一页最多会空掉"下一个放不下的栏目"那么高，实测最差 75%–77%（quill 线式版式落在栏目边界上；单栏版式没有并排可以吸收余量），而这个门槛要抓的过早切断在历史上是 13%–28%。阈值放在合法最差值之下一点：既不放过真正半空的页，也不把正常的栏目边界当故障。

需要按实测重标估算常数时：

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_layout.py   # 用真实渲染器产出校准探针
cd web; node scripts\measure_calib.mjs ..\output\tmp\calib > ..\output\tmp\calib.json
node scripts\show_calib.mjs ..\output\tmp\calib.json      # 打印可直接抄进 LAYOUT_METRICS 的数
```

校准探针的正文是**纯中文**，每行容量按**字宽单位**统计（全角 2、半角 1，见 `app/services.py` 的 `text_units`）。这两点都不能改回去：用拉丁字母较多的文本标定出的每行容量对纯中文正文偏乐观，估算会少算近三成行数、把正文顶出 A4 底边；只按纯中文字符数标定又会把带拉丁词的真实简历估高一截（非末页只剩七成满）。

定位“估算与渲染对不上”时：

- `node web/scripts/dump_page.mjs <导出 HTML>`：打印单个页面里每个栏目/条目的真实高度与裁切量。
- `node web/scripts/check_chars_per_line.mjs <导出 HTML>…`：对比各段落实际折出的每行字宽单位数。
- `node web/scripts/crop_page.mjs <导出 HTML> <out.png> <x> <y> <w> <h> [倍率]`：放大某一小块，用于核对小字号下的字形与颜色。

### 配色可读性与字号一致性

改调色板、深色底样式或任何字号后：

```powershell
# 注册表级：白纸角色 vs 白纸、栏目标题 vs 标题条底色、深色面角色 vs sidebar_bg
.\.venv\Scripts\python.exe scripts\audit_contrast.py
# 注册表体检：打印派生出的 on_dark_accent / tint 与逐模板对比度
.\.venv\Scripts\python.exe scripts\show_palettes.py
# 渲染级：真实浏览器合成祖先背景后逐处文本算 WCAG 对比度（应 0 处低于 4.5:1）
cd web; node scripts\audit_render_contrast.mjs ..\output\tmp 4.5; cd ..
# 预览字号：量 SPA 画布各角色的计算字号（应与导出的 pt 值一致）
cd web; node scripts\probe_canvas_type.mjs
```

### 画布（SPA）的对比度与渲染检查

导出 HTML 与 SPA 画布是两套样式表，`audit_render_contrast.mjs` 只覆盖前者。**改画布样式、深色面规则或 CSS 变量后，必须同时跑画布这一侧**——v1.0.13 的"侧栏深色底上字看不见"就是只审导出漏掉的：

```powershell
# 需要应用在运行：powershell -File scripts\Start-ResumeCraft.ps1 -NoBrowser
# 连到真实应用，逐套模板切换后逐处文本算对比度（12 套模板、编辑态，应 0 处低于 4.5:1）
cd web; node scripts\audit_canvas_contrast.mjs http://127.0.0.1:5173 4.5
# 只想看某一份简历的某个模板：打印侧栏每处文本的实际颜色/背景/字号，并截图
cd web; node scripts\inspect_canvas.mjs http://127.0.0.1:5173 5 ..\output\tmp\canvas.png "经典侧栏"
# 栏目隐藏/恢复：逐步断言（消失 → 出现恢复入口 → 恢复 → 入口收起）
cd web; node scripts\smoke_section_visibility.mjs http://127.0.0.1:5173
```

这两个脚本会切换简历的模板来遍历模板库，跑完用 `python scripts\restore_resume_template.py <简历 id> <模板 slug>`
把它改回去。它们**每一步都显式断言**（切到某模板后校验画布上的模板确实是它、走不到位就报错）：
首版曾把点击失败 catch 掉，结果审计其实是在"碰巧打开的"页面上跑，界面一改版就会静默审错对象。

画布的深色面规则另有一条结构性约束，改 `Canvas.tsx` 时要守住：侧栏里的栏目必须带
`sidebar-section` 类（由 `inSidebarStream(layout, section.id)` 推导）。少了这个类，整套深色面
配色都不会生效，而**任何只审导出的检查都发现不了**。

核对"某个模板在纸面上到底长什么样"时，`python scripts\dump_resume_content.py [简历 id]` 会打印该版本保存的内容，便于区分"版式问题"和"内容本身就是空的"。

测试夹具位于 `tests/conftest.py`。每个测试使用内存 SQLite、独立工作区和一个可用模板，不依赖真实数据库资料。

## 2. 现有测试脚本

### `tests/test_facts.py`

- `test_fact_crud_structured_fields_and_audit`：创建带结构化字段的事实，修改字段，检查详情和审计记录；再验证按分类、回收和恢复的基本行为。
- `test_fact_recycle_bin_lists_recycled_fact_and_restore`：创建被正式简历引用的事实，删除后确认进入回收站而不是物理删除，恢复后重新出现在有效资料中。
- `test_evidence_link_is_reachable_from_fact`：给事实添加证据链接，再从事实的证据接口读取，确认链接可追溯。

### `tests/test_linked_resume.py`

- `test_linked_resume_starts_empty_and_only_selected_facts_enter_preview`：创建临时简历，确认未选择事实时正文为空；只选择指定事实后，预览只包含被选择的事实。
- `test_fact_update_changes_linked_preview_but_not_formal_version`：修改事实后确认临时简历预览跟随变化，但已经转换的正式版本保持原内容不变。

### `tests/test_profiles.py`

- `test_profile_crud_and_opportunity_grouping`：创建岗位画像，修改岗位方向和核心要求，创建招聘机会，再确认机会挂在正确画像下。
- `test_profile_recycle_bin_is_reversible_when_it_owns_a_resume`：有正式简历的岗位画像删除时进入回收站，恢复后重新变为有效画像。
- `test_profile_list_exposes_active_formal_resume`：转换正式简历后，岗位画像列表返回对应的 `active_resume_id`，用于界面直接打开正式简历。

### `tests/test_resume_lifecycle.py`

- `test_conversion_creates_v1_save_creates_v2_and_restore_creates_dirty_copy`：临时简历转换为正式 v1，编辑工作副本并保存为 v2，再从 v1 创建新的脏工作副本。
- `test_formal_resume_contains_editable_job_target`：确认正式简历默认生成求职目标块，岗位方向和核心要求进入可编辑字段；修改并保存后仍能从正式版本读回。
- `test_deleted_resume_is_visible_in_recycle_bin_and_same_profile_can_create_new_resume`：删除正式简历后确认正式列表为空、回收站可见；同一岗位画像可以重新转换新正式简历；恢复旧简历后两份都存在。

### `tests/test_export.py`

- `test_export_is_fixed_a4_and_paginates_long_formal_content`：写入超长正文，导出正式 HTML，确认包含固定 A4 尺寸、分页页面和完整长文本。
- `test_export_with_link_block_renders_anchor`：链接类条目渲染为可点击的 `<a>`。
- `test_render_markdown_keeps_line_breaks`：正文里的换行渲染成 `<br>`（曾经按换行分段后又用空串拼接，把作者分好的行黏成一行），列表成组渲染、行尾换行不产生多余空行、加粗/斜体仍生效。

### `tests/test_template_compatibility.py`

覆盖 12 个内置模板的四层契约（描述符完整、导出可用、前端同步、接口可用）：

- 描述符：slug/色板/布局合法且名称唯一，六种布局都有模板覆盖，模板库维持在 10–12 套。
- 导出结构：每种布局的页面骨架、色板注入、无未渲染占位符；**姓名只出现在页头/侧栏页头，基本信息不再重复成栏目**；时间轴不并排。
- 内容编排：**导出端不排没有内容的栏目**（数据里空着的个人简介/链接与作品集此前会留一条空标题），而**画布端保留它们作为"点击选择资料"的占位入口**——两者刻意分开，不能合并；空栏目占位不计版面预算，预览与导出的断页因此一致（前端 `App.test.ts` 有用例）。
- 并排（一行两栏）：**只有表格版式会并排**（额度 3），单栏/横幅/线式/时间轴一律整宽通排，侧栏版式用"侧栏 + 主栏"的页级两栏结构。逐模板验证"一页并排行数不超过额度"。取舍依据（Greenhouse 把 columned layout 列进解析失败原因、经历必须整宽等）写在 `app/services.py` 的 `PAIR_BUDGET_BY_LAYOUT` 注释与排版的 `parsingNote()` 里。
- 退役模板：`RETIRED_TEMPLATES` 里的 slug 必须解析到同版式的承接模板，启动钩子把它们的数据库行改为停用而不是删除。
- 排版常数一致：逐项比对导出样式表与 `web/src/styles.css` 里真正影响分页的数值（正文行高、元信息字号、栏目/条目间距、侧栏间距、时间轴时间栏宽度与轴线位置，以及栏目/条目/正文/侧栏各档字号）。
- 分页行为：长内容分页并带“（续）”标记；**被切片的条目只渲染一次标题**（续段不再重复标题）。
- 前端同步：`/api/templates` 下发 layout/serif/tokens，画布消费 CSS 变量，无逐模板硬编码主题类。
- 接口全链路：启动建库 → 模板列表 → 选择模板 → 转为正式 → 导出。

### `tests/test_template_contrast.py`

把"纸面上的字能不能看清"变成门槛，而不是靠肉眼：

- 白纸角色（heading/title/meta/meta_label/copy/accent）在 `#ffffff` 上必须达 AA（4.5:1）。
- 栏目标题在它自己的标题条底色（`tint`）上必须达 AA；`tint` 本身不得深到盖住正文。
- 深色面角色（sidebar_fg/sidebar_muted/sidebar_heading/on_dark_accent）在 `sidebar_bg` 上必须达 AA，且只对真有深色文字面的版式（侧栏/横幅/表格表头）要求。
- `on_dark_accent` 必须有派生来源：达标或由 `accent` 派生，不允许既没覆盖也不达标。
- 导出样式表里，画在深色面上的文字规则不得引用白纸角色——侧栏条目的时间与字段值曾经就是这样被涂成深色底上的深色字（渲染级实测 110 处低于 3:1）。
- 深色面上必须显式使用深色面角色（时间、链接、字段值），不能靠继承碰运气。

### `tests/test_workflow.py`

- `test_conversion_save_restore_and_source_alert`：串联事实、岗位画像、临时简历、正式保存、历史恢复、事实更新和来源变化提醒。
- `test_evidence_and_unreferenced_fact_deletion`：确认未被引用的事实可物理删除，证据链接仍能正常读写。
- `test_structured_fact_details_empty_linked_page_and_html_export`：测试结构化个人资料、空临时预览、选择资料、转换和 HTML 导出。
- `test_fact_details_can_be_updated_and_export_renders_fields_and_long_text`：测试详细字段和自定义字段修改，并确认导出包含修改后的字段且长内容会分页。

### `tests/test_comprehensive_workflows.py`

- `test_every_resume_section_has_editable_title_fields_and_body`：为基本信息、求职目标、个人简介、教育经历、项目与实践、技能、成果、链接与作品集准备资料，逐个修改标题、正文和字段，再保存并重新读取，确认每个栏目都能持久化编辑。
- `test_resume_source_warning_is_visible_then_resolved_after_save_and_refresh`：修改正式简历引用的事实，确认顶部提示数据和简历警告数出现；保存处理后的正文后确认待处理接口为空、警告数归零，页面刷新后不再显示提示。
- `test_navigation_data_for_home_profiles_resumes_and_recycle_bin`：检查健康状态、首页概览计数、岗位画像列表、正式简历列表、删除后的回收站列表以及恢复后的列表状态，对应验证主要导航按钮的后端目标。
- `test_dangerous_actions_return_explicit_state_and_are_reversible`：分别测试未引用资料永久删除、已引用资料回收、资料恢复、正式简历回收和恢复，确认每个危险操作都有明确结果且可恢复操作确实恢复。
- `test_fact_schema_and_all_categories_can_be_loaded_for_edit_forms`：逐类读取资料编辑表单的字段 schema，确认六类资料都有字段，非法分类返回 404。
- `test_profile_edit_duplicate_identity_and_opportunity_routes`：测试画像编辑的身份冲突提示、招聘机会新增和读取、无效画像路径返回 404。
- `test_duplicate_active_resume_is_rejected_but_recycled_resume_can_be_recreated`：重复生成活跃正式简历返回 409；正式简历回收后，同一岗位画像可以重新生成新的正式简历。
- `test_working_copy_save_is_dirty_then_clean_and_versions_are_linear`：修改工作副本后确认 dirty，保存后确认 clean，再次编辑保存确认版本号线性增长。
- `test_version_restore_does_not_overwrite_immutable_history`：从历史版本恢复工作副本，确认历史版本列表仍完整且不存在的版本返回 404。
- `test_evidence_validation_and_archive_flow`：测试非法证据链接、有效证据链接、证据回收和非法文件格式，确认危险和输入错误都有明确状态码。
- `test_missing_resources_and_invalid_payloads_are_reported`：集中验证事实、简历、临时简历和证据不存在时返回 404，避免界面点击后出现静默失败。

## 交互测试脚本

`web/scripts/interaction-smoke.mjs` 是浏览器层冒烟脚本，不是接口模拟。它验证：

- 首页三个模块按钮是否进入正确页面。
- 顶部品牌按钮是否回到首页。
- 资料库新增资料、保存后列表是否出现新资料。
- 岗位画像新建、输入、保存后列表是否出现新画像。
- 正式简历入口、回收站切换、返回正式简历是否正常。
- 资料库回收站入口是否正常。
- 全流程是否产生 React 控制台错误。

本次已使用集成浏览器手动执行同等流程，确认页面跳转、表单输入、保存、回收站切换和恢复操作可用。自动脚本需要先安装 Playwright 浏览器依赖。

## 3. 当前验证结果

本次修改后已运行：

```text
.venv\Scripts\python.exe -m pytest -q           221 passed, 6 skipped
cd web; npx vitest run                          8 passed
cd web; npx tsc -b --noEmit                     通过
```

版式密度验收（13 个模板 × 3 种密度样本 = 39 份导出 HTML）：

```text
renders 39  pages 40  single-page 38
clipped renders: 0
under-filled non-final pages: 0
```

即：没有任何一页把内容裁在 A4 底边之外，也没有“只有一两行的尾页”。全量运行覆盖资料、证据、岗位画像、临时简历、正式简历生命周期、求职目标、来源提示、危险操作、HTML 导出与模板兼容性。运行时有 FastAPI/httpx 弃用警告，以及 `.pytest_cache` 无写权限警告；它们不影响测试结果。

## 4. 仍需新增的测试

1. **前端组件测试**：用 Vitest + Testing Library 测试岗位画像已有 `active_resume_id` 时显示“打开正式简历”，没有时显示“创建临时简历”；测试正式简历和回收站列表的空态、加载态和错误态。当前 `web/package.json` 虽有 `vitest` 命令，但尚未配置测试文件和 Testing Library。
2. **求职目标编辑交互测试**：验证标题、岗位方向、核心要求和强调方向四类输入都能修改，自动保存后重新加载仍保留；同时验证回收站正式简历为只读。
3. **接口错误状态测试**：覆盖活跃正式简历重复转换返回 409、回收后可重新转换、转换后列表和概览计数同步变化。
4. **回收站边界测试**：验证删除后正式列表不显示、回收站显示；恢复后只回到正式列表，不产生重复身份或重复版本。
5. **数据隔离测试**：创建第二个工作区，确认资料、岗位画像、临时简历和正式简历不会跨工作区出现。当前实现固定使用 `WORKSPACE_ID = 1`，这是上线前必须补的风险测试。
6. **导出视觉回归测试**：编辑器/A4 预览在多视口下的布局截图对比仍缺自动化。导出侧的“留白与裁切”已由上面的实测闭环覆盖（逐页填充率 + 裁切像素），但**像素级截图对比**尚未纳入 CI，模板改版后仍需人工看图确认观感。
7. **浏览器按钮与跳转测试**：安装并配置 Playwright，逐个点击首页三个模块、顶部品牌、来源提示、返回按钮、资料分类、岗位画像编辑/创建、正式简历打开/回收站、事实编辑/证据、临时简历选择/生成、正式简历保存/导出/恢复/删除，断言 URL 或页面标题和接口请求一致。
8. **字段焦点与可编辑性测试**：在 Playwright 中遍历所有输入框、文本框、选择框、复选框和正式编辑卡片字段，确认可聚焦、可输入、值变化可见、保存刷新后仍保留；检查回收状态下编辑控件不可写。
9. **危险操作确认测试**：拦截并确认删除资料、删除正式简历、回收证据等操作的确认对话框；点击取消后数据不变，点击确认后状态改变，回收站恢复后页面列表和顶部提示正确刷新。
10. **故障恢复测试**：模拟保存接口失败、加载接口失败和版本基线冲突，确认界面显示错误且不会丢失当前编辑内容。
11. **多会话并发测试**：使用两个数据库会话修改同一正式简历，真正触发工作副本基线冲突并验证 409 和重新加载流程；单会话测试不能证明这个场景。

## 5. 判断测试是否有效

有效测试应满足三点：

- 有独立的准备数据和明确的操作请求，不依赖手工点击或已有本地数据库。
- 至少检查一个可观察结果，例如 HTTP 状态、返回字段、数据库状态、版本号、导出内容或页面状态。
- 能在实现出错时失败，而不是只检查请求成功；尤其要检查列表是否显示、内容是否持久化、旧版本是否不变和回收状态是否正确。
