"""内置模板兼容性测试。

BUILTIN_TEMPLATES 注册表中的每个模板都必须同时满足四层契约：
- 描述符完整：布局合法、色板齐全、slug 可安全用于 CSS 类名与数据库唯一键；
- 导出可用：render_resume_html 产出自包含、正确分页、无渲染残留的 A4 HTML；
- 前端同步：/api/templates 与简历负载下发完整色板/衬线描述符，SPA 画布以
  CSS 变量消费同一份数据，不再维护逐模板的 theme-*/thumb-* 样式；
- 接口可用：启动建库 -> /api/templates -> 选择模板 -> 转正式 -> 导出全链路畅通。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app, sync_global_catalogues
from app.services import PAIR_BUDGET_BY_LAYOUT, PAGE_BUDGET_PX, pair_height, render_resume_html
from app.templates import BUILTIN_TEMPLATES, COLOUR_TOKENS, RETIRED_TEMPLATES, descriptor_for
from app.workbench_database import WorkbenchBase, get_db
from app.workbench_models import Template, User, Workspace

WEB_STYLES = Path(__file__).resolve().parents[1] / "web" / "src" / "styles.css"

REQUIRED_TOKENS = {"name", "description", "layout", "sidebar_bg", "sidebar_fg", "sidebar_muted", "sidebar_heading", "on_dark_accent", "heading", "title", "meta", "meta_label", "copy", "accent", "rule"}
LAYOUTS = {"sidebar", "plain", "banner", "grid", "line", "timeline", "rail"}
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_RE = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)

# 六种布局各留一到三套配色，作为端到端回归的代表样本。
NEW_TEMPLATES = sorted(BUILTIN_TEMPLATES)


SAMPLE_TITLES = {"target": "后端开发工程师", "profile": "个人简介", "education": "华东理工大学 · 自动化", "awards": "校级优秀毕业设计"}


def pairable_content() -> dict:
    """给短栏目填上内容，用于验证"哪些布局会把相邻短栏目并排"。"""
    content = sample_content()
    for index, sid in enumerate(("target", "profile", "education", "awards"), start=1):
        content["sections"][index]["blocks"] = [
            {"id": f"fact-{sid}", "type": "fact", "title": SAMPLE_TITLES[sid], "content": "一段简短的说明文字。", "fields": {}, "field_labels": {}, "display_fields": [], "source_refs": [9], "origin": "fact"},
        ]
    content["sections"][7]["blocks"] = [
        {"id": "fact-links", "type": "fact", "title": "作品集", "content": "example.com", "fields": {}, "field_labels": {}, "display_fields": [], "source_refs": [9], "origin": "fact"},
    ]
    return content


def sample_content(long: bool = False) -> dict:
    """结构与 build_resume_content 输出一致的最小简历内容。"""
    experience_body = "负责中台服务的设计与落地，沉淀了可复用的组件与规范。" * (120 if long else 2)
    return {
        "sections": [
            {"id": "basics", "type": "basics", "title": "基本信息", "visibility": True, "blocks": [
                {"id": "fact-1", "type": "fact", "title": "陈晓", "content": "", "fields": {"phone": "13800000000", "email": "chen@example.com", "city": "杭州"}, "field_labels": {}, "display_fields": ["phone", "email", "city"], "source_refs": [1], "origin": "fact"},
            ]},
            {"id": "target", "type": "target", "title": "求职目标", "visibility": True, "blocks": []},
            {"id": "profile", "type": "profile", "title": "个人简介", "visibility": True, "blocks": []},
            {"id": "experience", "type": "experience", "title": "项目与实践", "visibility": True, "blocks": [
                {"id": "fact-2", "type": "fact", "title": "电商中台重构", "content": experience_body, "fields": {"period": "2024-2025", "organization": "某科技公司", "role": "后端负责人"}, "field_labels": {}, "display_fields": ["period", "organization", "role"], "source_refs": [2], "origin": "fact"},
            ]},
            {"id": "education", "type": "education", "title": "教育经历", "visibility": True, "blocks": []},
            {"id": "skills", "type": "skills", "title": "技能", "visibility": True, "blocks": [
                {"id": "fact-3", "type": "fact", "title": "Python 工程化", "content": "Web 服务与数据处理。", "fields": {"skill_category": "语言", "proficiency": "熟练"}, "field_labels": {}, "display_fields": ["skill_category", "proficiency"], "source_refs": [3], "origin": "fact"},
            ]},
            {"id": "awards", "type": "awards", "title": "成果", "visibility": True, "blocks": []},
            {"id": "links", "type": "links", "title": "链接与作品集", "visibility": True, "blocks": []},
        ]
    }


def sample_content_with_photo() -> dict:
    content = sample_content()
    content["sections"][0]["blocks"][0]["photo"] = {
        "photo_id": 7,
        "evidence_id": 8,
        "preview_url": "/api/evidence/8/file",
        "filename": "portrait.png",
        "mime_type": "image/png",
        "data_url": "data:image/png;base64,cG9ydHJhaXQ=",
    }
    return content


# ---------------------------------------------------------------- 注册表契约

def test_builtin_descriptors_are_complete():
    assert BUILTIN_TEMPLATES, "注册表不能为空"
    names = set()
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        assert SLUG_RE.match(slug), f"slug {slug!r} 必须是小写标识符，才能用于 CSS 类名与 code-rendered 内容"
        missing = REQUIRED_TOKENS - set(descriptor)
        assert not missing, f"模板 {slug} 缺少字段: {sorted(missing)}"
        assert descriptor["layout"] in LAYOUTS, f"模板 {slug} 的 layout 非法"
        for token in COLOUR_TOKENS:
            assert HEX_RE.match(descriptor[token]), f"模板 {slug} 的 {token} 不是 6 位十六进制颜色"
        assert descriptor["name"].strip() and descriptor["description"].strip(), f"模板 {slug} 的名称与说明不能为空"
        names.add(descriptor["name"])
    assert len(names) == len(BUILTIN_TEMPLATES), "模板名称必须唯一"
    # 六种布局都必须有模板覆盖，保证分页与导出路径始终被使用。
    assert {item["layout"] for item in BUILTIN_TEMPLATES.values()} == LAYOUTS


# ---------------------------------------------------------------- 导出渲染

@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_export_html_is_valid_for_every_template(slug):
    descriptor = BUILTIN_TEMPLATES[slug]
    html = render_resume_html(sample_content(), "测试简历", 1, slug)

    # A4 自包含骨架。
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    assert "@page" in html and "size: A4" in html and "width:210mm" in html and 'lang="zh-CN"' in html
    # 色板全部注入 CSS，不允许出现未渲染的占位表达式。
    for token in COLOUR_TOKENS:
        assert descriptor[token] in html, f"模板 {slug} 的 {token} 未注入导出 CSS"
    assert "{d[" not in html and "{'" not in html, "导出 HTML 中存在未渲染的模板表达式"

    # 布局结构标记（CSS 规则对任何布局都会输出，因此只断言 body 的页面结构）。
    if descriptor["layout"] == "sidebar":
        assert '<section class="page">' in html and "<aside class=\"sidebar\">" in html
        assert "grid-template-columns:58mm 1fr" in html
        assert 'class="page page-plain"' not in html and 'class="page page-banner-page"' not in html
    elif descriptor["layout"] == "plain":
        assert 'class="page page-plain"' in html
        assert "<aside class=\"sidebar\">" not in html
    elif descriptor["layout"] == "banner":
        assert 'class="page page-banner-page"' in html and 'class="page-banner"' in html
        assert "<aside class=\"sidebar\">" not in html
    elif descriptor["layout"] == "grid":
        assert 'class="page page-grid"' in html and 'class="grid-head"' in html
        assert "<aside class=\"sidebar\">" not in html
        assert 'class="page page-plain"' not in html
    elif descriptor["layout"] == "line":
        assert 'class="page page-line"' in html and 'class="line-head"' in html
        assert "<aside class=\"sidebar\">" not in html
        assert 'class="page page-plain"' not in html
    elif descriptor["layout"] == "rail":
        assert 'class="page page-rail"' in html and 'class="rail-head"' in html
        assert "<aside class=\"sidebar\">" not in html
        assert 'class="page page-plain"' not in html
    else:  # timeline
        assert 'class="page page-timeline"' in html and "main-timeline" in html
        assert "<aside class=\"sidebar\">" not in html
        assert 'class="page page-plain"' not in html

    # 正文块完整渲染；姓名一律出现在页头/侧栏页头。
    assert "电商中台重构" in html and "技能" in html
    assert "陈晓" in html
    # 基本信息不再重复成栏目：侧栏布局的姓名与联系方式已由侧栏页头（姓名 +
    # 联系方式 + 简介）呈现，重复会让同一段内容在侧栏出现两次，并白占一行
    # 栏目标题的高度。
    assert "基本信息" not in html, f"模板 {slug} 重复渲染了基本信息栏目"

    # 并排只发生在有额度的版式（表格），其余版式一律整宽通排，详见
    # test_single_column_layouts_never_pair / test_form_layout_pairs_short_sections_side_by_side。
    if not PAIR_BUDGET_BY_LAYOUT[descriptor["layout"]]:
        assert 'class="pair"' not in html, f"模板 {slug} 不应并排"


@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_optional_profile_photo_renders_in_every_template(slug):
    html = render_resume_html(sample_content_with_photo(), "照片简历", 1, slug)
    assert html.count('class="resume-photo ') == 1, f"模板 {slug} 未渲染照片"
    assert 'src="data:image/png;base64,cG9ydHJhaXQ="' in html
    assert 'alt="陈晓的档案照片"' in html


@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_profile_photo_is_optional_and_leaves_layout_unchanged_when_absent(slug):
    html = render_resume_html(sample_content(), "无照片简历", 1, slug)
    body = html.split("<body>", 1)[-1].split("</body>", 1)[0]
    assert "resume-photo" not in body
    assert " has-photo" not in body


@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_sections_without_content_are_not_rendered(slug):
    """没有内容的栏目不出现在纸面上。

    样本里 个人简介/链接与作品集/求职目标/教育经历/成果 一条条目都没有。改前它们
    照样排出栏目标题，纸面上留下一条只有标题的空条（时间轴还多一个悬空圆点）。
    """
    html = render_resume_html(sample_content(), "空栏目", 1, slug)
    for title in ("个人简介", "链接与作品集", "求职目标", "教育经历"):
        assert title not in html, f"模板 {slug} 为空栏目 {title} 排了标题"
    assert "项目与实践" in html and "技能" in html


@pytest.mark.parametrize("slug", ["classic", "ink", "atlas", "lumen"])
def test_hidden_section_is_not_rendered(slug):
    """整栏隐藏后导出端不再排它。

    隐藏写在内容的 visibility 里（工作副本 → 版本），此导出端此前只按"有没有内容"筛栏目、
    没读 visibility，于是栏目只在画布里消失、纸面上照样出现。预览侧用同一字段过滤
    （web/src/lib/resume.ts 的 sectionVisible），两边的断页才对得上。
    """
    content = pairable_content()
    content["sections"][3]["visibility"] = False  # experience
    html = render_resume_html(content, "隐藏", 1, slug)
    assert "项目与实践" not in html, f"模板 {slug} 仍然排出了被隐藏的栏目"
    assert "技能" in html
    # 隐藏不影响别的栏目：把同一份内容全部显示出来作对照。
    for section in pairable_content()["sections"]:
        section["visibility"] = True
    visible_html = render_resume_html(pairable_content(), "全显", 1, slug)
    assert "项目与实践" in visible_html


def test_only_the_target_section_left_still_exports_one_page():
    """全空/全隐藏的简历仍要出一页骨架，避免零页导出。"""
    content = sample_content()
    for section in content["sections"]:
        section["visibility"] = section["id"] == "target"
        if section["id"] == "target":
            section["blocks"] = [{"id": "t", "type": "fact", "title": "后端开发工程师", "content": "", "fields": {}, "field_labels": {}, "display_fields": [], "source_refs": [], "origin": "profile"}]
    html = render_resume_html(content, "空简历", 1, "ink")
    assert html.count('class="page') == 1


@pytest.mark.parametrize("slug", ["atlas", "flint"])
def test_form_layout_pairs_short_sections_side_by_side(slug):
    """表格表单版式把相邻短栏目并排成表格行——这是它自己的排版语汇。"""
    content = pairable_content()
    html = render_resume_html(content, "双栏", 1, slug)
    assert 'class="pair"' in html, f"模板 {slug} 的相邻短栏目没有并排"
    assert html.count('class="section"') >= 3


@pytest.mark.parametrize("slug", ["classic", "onyx", "merlot"])
def test_sidebar_layout_keeps_its_main_column_full_width(slug):
    """侧栏布局一页已经是两列（58mm 侧栏 + 主栏），主栏再并排就成三列——额度为 0。"""
    html = render_resume_html(pairable_content(), "侧栏", 1, slug)
    assert 'class="pair"' not in html, f"模板 {slug} 的侧栏主栏不应并排"


@pytest.mark.parametrize("slug", ["ink", "forest", "vermilion", "azure", "regent", "quill", "lumen"])
def test_single_column_layouts_never_pair(slug):
    """单栏系列一律整宽通排。

    版式调研给出的硬约束：Greenhouse 官方把 "columned layout" 与 "tables" 列进
    解析失败原因清单，TopResume 说解析器读不了右栏、会把信息打乱，各来源一致要求
    工作经历/项目经历整宽独行。单栏系列的取舍是"兼容性优先，宁可多一页"，
    并排（一行两栏）只保留在表格版式与侧栏版式的页级两栏结构里。
    """
    html = render_resume_html(pairable_content(), "单栏", 1, slug)
    assert 'class="pair"' not in html, f"模板 {slug} 应保持单栏"


def test_pair_budget_keeps_full_width_rows_the_default():
    """一页里的并排行数不得超过该版式的额度（侧栏/单栏/时间轴为 0，表格为 3）。"""
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        budget = PAIR_BUDGET_BY_LAYOUT[descriptor["layout"]]
        html = render_resume_html(pairable_content(), "配额", 1, slug)
        for number, page in enumerate(html.split('<section class="page')[1:], start=1):
            on_page = page.count('<div class="pair">')
            assert on_page <= budget, f"{slug} 第 {number} 页并排了 {on_page} 行，超出额度 {budget}"


def test_pair_height_does_not_reject_uneven_columns():
    """高度不齐本身不是拒绝配对的理由。

    曾经加过"两栏高度差超过四行就不并排"的规则，本意是修短栏底下的空白，实测却把本来
    省版面的配对推掉了：真实简历因此从一页变两页，而且第一页只填到 78%。短栏的空白
    改由"每栏左侧色条 + 表格版式整行外框"来界定。
    """
    short = {"blocks": [{"title": "后端开发工程师", "content": "服务端方向。", "fields": {}, "display_fields": []}]}
    tall = {"blocks": [{"title": "个人简介", "content": "四年服务端经验，关注稳定性与可维护性。" * 12, "fields": {}, "display_fields": []}]}
    assert pair_height({"target": short, "profile": tall}, "plain", "target", "profile", PAGE_BUDGET_PX["plain"]) is not None
    assert pair_height({"target": short, "profile": tall}, "grid", "target", "profile", PAGE_BUDGET_PX["grid"]) is not None


@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_export_escapes_user_content(slug):
    content = sample_content()
    content["sections"][3]["blocks"][0]["content"] = "正文<script>alert(1)</script>与**加粗**。"
    html = render_resume_html(content, "安全简历", 1, slug)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<strong>加粗</strong>" in html


@pytest.mark.parametrize("slug", NEW_TEMPLATES)
def test_new_templates_paginate_long_content_and_mark_continuation(slug):
    html = render_resume_html(sample_content(long=True), "长简历", 1, slug)
    assert html.count('class="page') >= 2, f"模板 {slug} 未对长内容分页"
    assert "（续）" in html, f"模板 {slug} 跨页栏目缺少（续）标记"
    assert "297mm" in html and "data-page" not in html  # 导出走 section.page，不携带 SPA 的 data-page 属性


@pytest.mark.parametrize("slug", ["ink", "classic", "azure", "lumen"])
def test_fragmented_entry_renders_its_title_once(slug):
    """续段只带正文：重复渲染标题会让同一个条目在页面上看起来出现了两次。"""
    html = render_resume_html(sample_content(long=True), "续段", 1, slug)
    assert html.count("<h3>电商中台重构</h3>") == 1, f"模板 {slug} 的续段重复了条目标题"


def test_unknown_slug_falls_back_to_classic():
    html = render_resume_html(sample_content(), "回退简历", 1, "不存在的模板")
    assert BUILTIN_TEMPLATES["classic"]["sidebar_bg"] in html
    assert 'class="page"' in html


# ---------------------------------------------------------------- 前端同步

def test_api_exposes_palette_for_every_template(builtin_client):
    """SPA 画布的主题完全来自 API 下发的 tokens/serif/layout，注册表必须完整下发。"""
    rows = {item["template_key"]: item for item in builtin_client.get("/api/templates").json()}
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        row = rows[slug]
        assert row["layout"] == descriptor["layout"]
        assert row["serif"] is bool(descriptor.get("serif"))
        assert row["tokens"] == {key: descriptor[key] for key in COLOUR_TOKENS}


def test_spa_canvas_is_variable_driven():
    css = WEB_STYLES.read_text(encoding="utf-8")
    # 画布与横幅直接消费 API 色板变量；classic 色板作为 CSS 回退值保留。
    assert ".resume-sidebar{background:var(--t-sidebar-bg)" in css
    assert ".resume-banner{padding:8mm 11mm;flex:none;background:var(--t-sidebar-bg)" in css
    assert ".resume-stage{--t-sidebar-bg:#163b43" in css
    assert ".resume-paper.serif,.resume-paper.serif *" in css
    # 单栏布局只留一列；页头行固定为 auto，否则 align-content:stretch 会把富余高度
    # 分给页头，短内容页会出现一条无意义的空白带。
    assert ".resume-paper.plain{grid-template-columns:1fr;grid-template-rows:auto 1fr}" in css
    assert ".resume-paper.timeline{grid-template-rows:auto 1fr}" in css
    # 新布局（grid/line/timeline）的画布规则必须存在，且与导出渲染共用同一套 token。
    assert ".resume-paper.grid .resume-section{border:1px solid var(--t-rule);overflow:hidden}" in css
    assert ".resume-paper.grid .template-section-title{background:var(--t-sidebar-bg)" in css
    assert ".resume-paper.line .line-head{text-align:center" in css
    assert ".resume-paper .entry-period{margin-left:auto;color:var(--t-accent)" in css
    assert ".resume-paper.plain .line-head" in css, "plain 布局缺少紧凑页头样式"
    assert ".resume-paper.timeline .line-head" in css, "timeline 布局缺少紧凑页头样式"
    assert ".resume-paper.timeline .resume-block{display:grid;grid-template-columns:20mm 4mm 1fr}" in css
    assert ".resume-paper.timeline .t-time{grid-column:1;color:var(--t-accent)" in css
    # 栏目 = 左侧色条 + 标题条：主栏栏目有框，表格版式与侧栏各有自己的容器形态。
    assert ".main-sections>.resume-section,.pair>.resume-section{border-left:2.4pt solid var(--t-accent)" in css
    assert ".resume-section .template-section-title{margin:0 0 1.5mm;padding:1.2mm 2.4mm 1mm;background:var(--t-tint)" in css
    assert ".resume-paper.grid .template-section-title{background:var(--t-sidebar-bg);border-bottom:0" in css
    assert ".sidebar-section{border-left:2pt solid var(--t-on-dark-accent)" in css
    # 不允许出现逐模板的硬编码主题/缩略图类——新增模板不应再改前端样式。
    for slug in BUILTIN_TEMPLATES:
        assert f"theme-{slug}" not in css, f"styles.css 仍残留 {slug} 的 theme-* 类"
        assert f"thumb-{slug}" not in css, f"styles.css 仍残留 {slug} 的 thumb-* 类"


# ---------------------------------------------------- 预览与导出的排版常数一致
# 预览画布（web/src/styles.css）与导出样式表（render_resume_html 内嵌 CSS）必须共用
# 同一套排版常数：分页估算是按导出 CSS 实测标定的，预览一旦自行变松/变紧，两端的
# 断点就会错位（预览与导出页数不一致）。这里逐项比对两边真正影响分页的几个数值。

def export_css() -> str:
    html = render_resume_html(sample_content(), "样式", 1, "classic")
    return re.search(r"<style>(.*?)</style>", html, re.S).group(1)


SHARED_RHYTHM = [
    ("正文行高", r"^\s*\.block p \{[^}]*line-height:(?P<v>[\d.]+)",
     r"\.resume-paper \.block-copy\{font-size:[\d.]+pt;line-height:(?P<v>[\d.]+)"),
    ("元信息字号", r"^\s*\.block-meta \{[^}]*font-size:(?P<v>[\d.]+)pt",
     r"\.resume-paper \.block-meta\{font-size:(?P<v>[\d.]+)pt"),
    ("栏目间距", r"^\.main \.section \{ margin-top:(?P<v>[\d.]+)mm",
     r"\.main-sections\{display:grid;gap:(?P<v>[\d.]+)mm"),
    ("条目间距", r"^\.block \{ margin:0 0 (?P<v>[\d.]+)mm",
     r"\.main-sections \.resume-block\{margin-bottom:(?P<v>[\d.]+)mm"),
    ("侧栏栏目间距", r"^\.sidebar \.section \{ margin-top:(?P<v>[\d.]+)mm",
     r"\.sidebar-content\{display:grid;align-content:start;gap:(?P<v>[\d.]+)mm"),
    ("侧栏条目间距", r"^\.sidebar \.block \{ margin-bottom:(?P<v>[\d.]+)mm",
     r"\.sidebar-section \.resume-block\{margin-bottom:(?P<v>[\d.]+)mm"),
    ("时间轴时间栏宽度", r"^\.main-timeline \.block \{ display:grid; grid-template-columns:(?P<v>[\d.]+)mm",
     r"\.resume-paper\.timeline \.resume-block\{display:grid;grid-template-columns:(?P<v>[\d.]+)mm"),
    ("时间轴轴线位置", r"^\.main-timeline \.section::before \{ content:''; position:absolute; left:(?P<v>[\d.]+)mm",
     r"\.resume-paper\.timeline \.resume-section::before\{content:'';position:absolute;left:(?P<v>[\d.]+)mm"),
    # —— 排版刻度：层级不只在"谁更大"，还在两端口径一致。预览曾漏声明条目标题字号，
    # 让它继承浏览器默认 16px，于是预览里条目标题比栏目标题还大，栏目结构在画布上消失。
    ("栏目标题字号", r"^\.section h2 \{[^}]*font-size:(?P<v>[\d.]+)pt",
     r"\.resume-section \.template-section-title b\{font-size:(?P<v>[\d.]+)pt"),
    ("条目标题字号", r"^\s*\.block h3 \{[^}]*font-size:(?P<v>[\d.]+)pt",
     r"\.resume-paper \.block-head>b\{color:var\(--t-title\);font-size:(?P<v>[\d.]+)pt"),
    ("正文字号", r"^\s*\.block p \{[^}]*font-size:(?P<v>[\d.]+)pt",
     r"\.resume-paper \.block-copy\{font-size:(?P<v>[\d.]+)pt"),
    ("侧栏栏目标题字号", r"^\.sidebar \.section h2 \{[^}]*font-size:(?P<v>[\d.]+)pt",
     r"\.sidebar-section \.template-section-title b\{color:var\(--t-sidebar-heading\);font-size:(?P<v>[\d.]+)pt"),
    ("侧栏条目标题字号", r"^\.sidebar \.block h3 \{[^}]*font-size:(?P<v>[\d.]+)pt",
     r"\.resume-paper \.sidebar-section \.block-head>b,\.resume-paper \.sidebar-section \.inline-title\{color:var\(--t-sidebar-fg\);font-size:(?P<v>[\d.]+)pt"),
    ("侧栏正文字号", r"^\.sidebar \.block p \{[^}]*font-size:(?P<v>[\d.]+)pt",
     r"\.resume-paper \.sidebar-section \.block-copy[^{]*\{color:var\(--t-sidebar-muted\);font-size:(?P<v>[\d.]+)pt"),
]


@pytest.mark.parametrize("label,export_re,spa_re", SHARED_RHYTHM, ids=[item[0] for item in SHARED_RHYTHM])
def test_preview_matches_export_rhythm(label, export_re, spa_re):
    export = re.search(export_re, export_css(), re.MULTILINE)
    spa = re.search(spa_re, WEB_STYLES.read_text(encoding="utf-8"))
    assert export, f"{label}：导出样式表未匹配到"
    assert spa, f"{label}：预览样式表未匹配到"
    assert export.group("v") == spa.group("v"), f"{label} 不一致：导出 {export.group('v')} vs 预览 {spa.group('v')}"


# ---------------------------------------------------------------- API 全链路

@pytest.fixture
def builtin_client(monkeypatch):
    """镜像 ensure_builtin_templates 的真实启动路径：先建库，再触发启动钩子。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    WorkbenchBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        user = User(display_name="Test user")
        db.add(user)
        db.flush()
        db.add(Workspace(owner_id=user.id, name="Test workspace"))
        db.commit()
    monkeypatch.setattr("app.workbench_database.SessionLocal", Session)
    sync_global_catalogues()

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_startup_creates_every_builtin_template(builtin_client):
    rows = builtin_client.get("/api/templates").json()
    by_slug = {item["template_key"]: item for item in rows}
    assert set(by_slug) == set(BUILTIN_TEMPLATES)
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        row = by_slug[slug]
        assert row["display_name"] == descriptor["name"] and row["description"] == descriptor["description"]
        assert row["layout"] == descriptor["layout"]
        assert row["status"] == "available"


def test_startup_retires_templates_dropped_from_the_registry(builtin_client):
    """退役模板保留迁移记录，但不再出现在可选模板目录。"""
    from app.workbench_database import SessionLocal

    retired_slug, successor = next(iter(RETIRED_TEMPLATES.items()))
    # 模拟早先版本建的库：注册表里已经没有这个 slug，但数据库行还在。
    with SessionLocal() as db:
        template = Template(
            template_key=retired_slug,
            display_name="历史模板",
            description="早先版本创建",
            renderer_key=retired_slug,
            status="available",
        )
        db.add(template)
        db.commit()

    sync_global_catalogues()

    listed = {item["template_key"] for item in builtin_client.get("/api/templates").json()}
    assert retired_slug not in listed
    with SessionLocal() as db:
        row = db.scalar(select(Template).where(Template.template_key == retired_slug))
        assert row is not None and row.status == "retired", f"{retired_slug} 的模板行应当被停用而非删除"

    assert descriptor_for(retired_slug) is BUILTIN_TEMPLATES[successor]


def test_retired_slug_is_not_selectable(client):
    """退役模板不能继续作为新简历的选择项。"""
    rows = {item["template_key"]: item for item in client.get("/api/templates").json()}
    assert "focus" not in rows
    assert set(rows) == set(BUILTIN_TEMPLATES)


def test_startup_syncs_stale_builtin_metadata(builtin_client):
    """早先版本创建的模板行会被启动钩子同步回注册表文案（版本行保持不动）。"""
    from app.workbench_database import SessionLocal

    with SessionLocal() as db:
        row = db.scalar(select(Template).where(Template.template_key == "classic"))
        row.description = "历史遗留的过期描述"
        db.commit()

    sync_global_catalogues()

    rows = {item["template_key"]: item for item in builtin_client.get("/api/templates").json()}
    assert rows["classic"]["description"] == BUILTIN_TEMPLATES["classic"]["description"]


@pytest.mark.parametrize("slug", NEW_TEMPLATES)
def test_new_template_end_to_end_flow(builtin_client, slug):
    templates = {item["template_key"]: item for item in builtin_client.get("/api/templates").json()}
    template_id = templates[slug]["id"]
    layout = BUILTIN_TEMPLATES[slug]["layout"]

    profile = builtin_client.post("/api/requirement-profiles", json={"name": "兼容性岗位"}).json()
    linked_id = builtin_client.post(
        "/api/linked-resumes",
        json={"profile_id": profile["id"], "template_id": template_id},
    ).json()["id"]
    linked = builtin_client.get(f"/api/linked-resumes/{linked_id}").json()
    assert linked["template"]["template_key"] == slug and linked["template"]["layout"] == layout

    facts = {}
    fact_fields = {
        "basics": {"name": "陈晓", "bio": "事实"},
        "experience": {"experience_kind": "project", "work_summary": "事实"},
        "skill": {"usage_context": "事实"},
    }
    for category, title in (("basics", "陈晓"), ("experience", "中台重构"), ("skill", "Python")):
        facts[category] = builtin_client.post(
            "/api/facts",
            json={
                "category_code": category,
                "title": title,
                "fields": fact_fields[category],
            },
        ).json()["id"]
    builtin_client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"basics": [facts["basics"]], "experience": [facts["experience"]], "skills": [facts["skill"]]}})

    resume_id = builtin_client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    resume = builtin_client.get(f"/api/resumes/{resume_id}").json()
    assert resume["template"]["template_key"] == slug and resume["template"]["layout"] == layout
    assert resume["template"]["tokens"] == {key: BUILTIN_TEMPLATES[slug][key] for key in COLOUR_TOKENS}

    saved = builtin_client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "兼容性验证"})
    assert saved.status_code == 200, saved.text

    export = builtin_client.post(f"/api/resumes/{resume_id}/versions/2/export?force=true")
    assert export.status_code == 200, export.text
    body = export.text
    assert "@page" in body and "size: A4" in body
    descriptor = BUILTIN_TEMPLATES[slug]
    for token in COLOUR_TOKENS:
        assert descriptor[token] in body, f"导出 HTML 缺少模板 {slug} 的 {token}"
    page_class = {"sidebar": '<section class="page">', "plain": "page-plain", "banner": "page-banner-page",
                  "grid": "page-grid", "line": "page-line", "timeline": "page-timeline", "rail": "page-rail"}[layout]
    assert page_class in body
    if layout == "sidebar":
        assert "<aside class=\"sidebar\">" in body
