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

from app.main import app, ensure_builtin_templates
from app.services import render_resume_html
from app.templates import BUILTIN_TEMPLATES, COLOUR_TOKENS
from app.workbench_database import WorkbenchBase, get_db
from app.workbench_models import ResumeTemplate, User, Workspace

WEB_STYLES = Path(__file__).resolve().parents[1] / "web" / "src" / "styles.css"

REQUIRED_TOKENS = {"name", "description", "layout", "sidebar_bg", "sidebar_fg", "sidebar_muted", "sidebar_heading", "heading", "title", "meta", "meta_label", "copy", "accent", "rule"}
COLOUR_TOKENS = {"sidebar_bg", "sidebar_fg", "sidebar_muted", "sidebar_heading", "heading", "title", "meta", "meta_label", "copy", "accent", "rule"}
LAYOUTS = {"sidebar", "plain", "banner", "grid", "line", "timeline"}
# 基本信息栏目被页头取代的布局（姓名/联系方式直接呈现为页头）。
HEADER_LAYOUTS = {"banner", "grid", "line", "plain", "timeline"}
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_RE = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)

# 覆盖六种布局的新模板，作为端到端回归的代表样本。
NEW_TEMPLATES = ["pine", "merlot", "ink", "brass", "marine", "haze", "violet", "celadon", "vermilion", "cobalt", "forest", "regent", "umber", "onyx", "atlas", "flint", "quill", "indigo", "lumen", "meridian"]


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
    else:  # timeline
        assert 'class="page page-timeline"' in html and "main-timeline" in html
        assert "<aside class=\"sidebar\">" not in html
        assert 'class="page page-plain"' not in html

    # 正文块完整渲染；页头布局用页头取代基本信息栏目。
    assert "电商中台重构" in html and "技能" in html
    if descriptor["layout"] in HEADER_LAYOUTS:
        assert "陈晓" in html
    else:
        assert "基本信息" in html

    # 双栏收尾：除时间轴外，短栏目两两并排（样本四个尾栏目高度均衡，必成对）。
    if descriptor["layout"] == "timeline":
        assert 'class="pair"' not in html
    else:
        assert 'class="pair"' in html, f"模板 {slug} 的双栏收尾未生效"


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


def test_unknown_slug_falls_back_to_classic():
    html = render_resume_html(sample_content(), "回退简历", 1, "不存在的模板")
    assert BUILTIN_TEMPLATES["classic"]["sidebar_bg"] in html
    assert 'class="page"' in html


# ---------------------------------------------------------------- 前端同步

def test_api_exposes_palette_for_every_template(builtin_client):
    """SPA 画布的主题完全来自 API 下发的 tokens/serif/layout，注册表必须完整下发。"""
    rows = {item["slug"]: item for item in builtin_client.get("/api/templates").json()}
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        row = rows[slug]
        assert row["layout"] == descriptor["layout"]
        assert row["serif"] is bool(descriptor.get("serif"))
        assert row["tokens"] == {key: descriptor[key] for key in COLOUR_TOKENS}


def test_spa_canvas_is_variable_driven():
    css = WEB_STYLES.read_text(encoding="utf-8")
    # 画布与横幅直接消费 API 色板变量；classic 色板作为 CSS 回退值保留。
    assert ".resume-sidebar{background:var(--t-sidebar-bg)" in css
    assert ".resume-banner{padding:9mm 11mm;flex:none;background:var(--t-sidebar-bg)" in css
    assert ".resume-stage{--t-sidebar-bg:#163b43" in css
    assert ".resume-paper.serif,.resume-paper.serif *" in css
    assert ".resume-paper.plain{grid-template-columns:1fr}" in css
    # 新布局（grid/line/timeline）的画布规则必须存在，且与导出渲染共用同一套 token。
    assert ".resume-paper.grid .resume-section{border:1px solid var(--t-rule);overflow:hidden}" in css
    assert ".resume-paper.grid .template-section-title{background:var(--t-sidebar-bg)" in css
    assert ".resume-paper.line .line-head{text-align:center" in css
    assert ".resume-paper .entry-period{margin-left:auto;color:var(--t-accent)" in css
    assert ".resume-paper.plain .line-head" in css, "plain 布局缺少紧凑页头样式"
    assert ".resume-paper.timeline .line-head" in css, "timeline 布局缺少紧凑页头样式"
    assert ".resume-paper.timeline .resume-block{display:grid;grid-template-columns:18mm 3mm 1fr}" in css
    assert ".resume-paper.timeline .t-time{grid-column:1;color:var(--t-accent)" in css
    # 不允许出现逐模板的硬编码主题/缩略图类——新增模板不应再改前端样式。
    for slug in BUILTIN_TEMPLATES:
        assert f"theme-{slug}" not in css, f"styles.css 仍残留 {slug} 的 theme-* 类"
        assert f"thumb-{slug}" not in css, f"styles.css 仍残留 {slug} 的 thumb-* 类"


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
    ensure_builtin_templates()

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
    by_slug = {item["slug"]: item for item in rows}
    assert set(by_slug) == set(BUILTIN_TEMPLATES)
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        row = by_slug[slug]
        assert row["name"] == descriptor["name"] and row["description"] == descriptor["description"]
        assert row["layout"] == descriptor["layout"]
        assert row["version"] == 1 and row["template_version_id"]


def test_startup_syncs_stale_builtin_metadata(builtin_client):
    """早先版本创建的模板行会被启动钩子同步回注册表文案（版本行保持不动）。"""
    from app.workbench_database import SessionLocal

    with SessionLocal() as db:
        row = db.scalar(select(ResumeTemplate).where(ResumeTemplate.slug == "classic"))
        row.description = "历史遗留的过期描述"
        db.commit()

    ensure_builtin_templates()

    rows = {item["slug"]: item for item in builtin_client.get("/api/templates").json()}
    assert rows["classic"]["description"] == BUILTIN_TEMPLATES["classic"]["description"]


@pytest.mark.parametrize("slug", NEW_TEMPLATES)
def test_new_template_end_to_end_flow(builtin_client, slug):
    templates = {item["slug"]: item for item in builtin_client.get("/api/templates").json()}
    version_id = templates[slug]["template_version_id"]
    layout = BUILTIN_TEMPLATES[slug]["layout"]

    profile = builtin_client.post("/api/requirement-profiles", json={"name": "兼容性岗位"}).json()
    linked_id = builtin_client.post(f"/api/linked-resumes?profile_id={profile['id']}&template_version_id={version_id}").json()["id"]
    linked = builtin_client.get(f"/api/linked-resumes/{linked_id}").json()
    assert linked["template"]["slug"] == slug and linked["template"]["layout"] == layout

    facts = {}
    for category, title in (("basics", "陈晓"), ("experience", "中台重构"), ("skills", "Python")):
        facts[category] = builtin_client.post("/api/facts", json={"category": category, "title": title, "details": {"summary": "事实"}}).json()["id"]
    builtin_client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"basics": [facts["basics"]], "experience": [facts["experience"]], "skills": [facts["skills"]]}})

    resume_id = builtin_client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    resume = builtin_client.get(f"/api/resumes/{resume_id}").json()
    assert resume["template"]["slug"] == slug and resume["template"]["layout"] == layout
    assert resume["template"]["tokens"] == {key: BUILTIN_TEMPLATES[slug][key] for key in COLOUR_TOKENS}

    saved = builtin_client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "兼容性验证"})
    assert saved.status_code == 200, saved.text

    export = builtin_client.post(f"/api/resumes/{resume_id}/versions/2/export")
    assert export.status_code == 200, export.text
    body = export.text
    assert "@page" in body and "size: A4" in body
    descriptor = BUILTIN_TEMPLATES[slug]
    for token in COLOUR_TOKENS:
        assert descriptor[token] in body, f"导出 HTML 缺少模板 {slug} 的 {token}"
    page_class = {"sidebar": '<section class="page">', "plain": "page-plain", "banner": "page-banner-page",
                  "grid": "page-grid", "line": "page-line", "timeline": "page-timeline"}[layout]
    assert page_class in body
    if layout == "sidebar":
        assert "<aside class=\"sidebar\">" in body
