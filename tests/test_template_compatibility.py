"""内置模板兼容性测试。

BUILTIN_TEMPLATES 注册表中的每个模板都必须同时满足四层契约：
- 描述符完整：布局合法、色板齐全、slug 可安全用于 CSS 类名与数据库唯一键；
- 导出可用：render_resume_html 产出自包含、正确分页、无渲染残留的 A4 HTML；
- 前端同步：SPA 预览样式（theme-*/thumb-* 类）覆盖注册表中的每个 slug；
- 接口可用：启动建库 -> /api/templates -> 选择模板 -> 转正式 -> 导出全链路畅通。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app, ensure_builtin_templates
from app.services import BUILTIN_TEMPLATES, render_resume_html
from app.workbench_database import WorkbenchBase, get_db
from app.workbench_models import User, Workspace

WEB_STYLES = Path(__file__).resolve().parents[1] / "web" / "src" / "styles.css"

REQUIRED_TOKENS = {"name", "description", "layout", "sidebar_bg", "sidebar_fg", "sidebar_muted", "sidebar_heading", "heading", "title", "meta", "meta_label", "copy", "accent", "rule"}
COLOUR_TOKENS = {"sidebar_bg", "sidebar_fg", "sidebar_muted", "sidebar_heading", "heading", "title", "meta", "meta_label", "copy", "accent", "rule"}
LAYOUTS = {"sidebar", "plain", "banner"}
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_RE = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)

# 覆盖三种布局的新模板，作为端到端回归的代表样本。
NEW_TEMPLATES = ["pine", "merlot", "ink", "brass", "marine", "haze", "violet", "celadon", "vermilion"]


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
    # 三种布局都必须有模板覆盖，保证分页与导出路径始终被使用。
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
    else:
        assert 'class="page page-banner-page"' in html and 'class="page-banner"' in html
        assert "<aside class=\"sidebar\">" not in html

    # 正文块完整渲染；横幅布局用横幅头部取代基本信息栏目。
    assert "电商中台重构" in html and "技能" in html
    if descriptor["layout"] == "banner":
        assert 'class="page-banner"' in html and "陈晓" in html
    else:
        assert "基本信息" in html


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

# classic 与 azure 分别是侧栏/横幅的基础主题：styles.css 的基础纸张与横幅样式即其覆盖。
BASE_THEME_SLUGS = {"classic", "azure"}


def test_spa_css_covers_every_registered_template():
    css = WEB_STYLES.read_text(encoding="utf-8")
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        assert f"thumb-{slug}" in css, f"styles.css 缺少 {slug} 的 thumb-* 缩略图样式，模板弹窗会显示空白缩略图"
        if slug not in BASE_THEME_SLUGS:
            assert f"theme-{slug}" in css, f"styles.css 缺少 {slug} 的 theme-* 预览样式，画布会回退到经典配色"
        if descriptor["layout"] == "sidebar":
            assert re.search(rf"\.resume-sidebar\{{[^}}]*background:{descriptor['sidebar_bg']}", css), f"模板 {slug} 的侧栏底色未同步到预览"
        if descriptor["layout"] == "banner":
            assert re.search(rf"\.resume-banner\{{[^}}]*background:{descriptor['sidebar_bg']}", css), f"模板 {slug} 的横幅底色未同步到预览"


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

    saved = builtin_client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "兼容性验证"})
    assert saved.status_code == 200, saved.text

    export = builtin_client.post(f"/api/resumes/{resume_id}/versions/2/export")
    assert export.status_code == 200, export.text
    body = export.text
    assert "@page" in body and "size: A4" in body
    descriptor = BUILTIN_TEMPLATES[slug]
    for token in COLOUR_TOKENS:
        assert descriptor[token] in body, f"导出 HTML 缺少模板 {slug} 的 {token}"
    if layout == "sidebar":
        assert "<aside class=\"sidebar\">" in body
    elif layout == "plain":
        assert "page-plain" in body
    else:
        assert "page-banner-page" in body
