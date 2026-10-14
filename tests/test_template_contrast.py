"""模板配色与文字可读性门槛。

这一组测试守住的是"交付物上真的能看清"这件事，而不是调色板看着好不好看：

- 白纸角色（heading/title/meta/meta_label/copy/accent）在 #ffffff 上必须达到 AA；
- 深色面角色（sidebar_fg/sidebar_muted/sidebar_heading/on_dark_accent）在
  ``sidebar_bg`` 上必须达到 AA，且只对真正会在深色底上排字的版式（侧栏/横幅/
  表格表头）要求——plain/line/timeline 的 ``sidebar_bg`` 只是装饰线，不是文字底；
- 导出样式表里，画在深色面上的文字规则不得引用白纸角色。历史上侧栏条目的时间
  与字段值正是这样被 `accent`/`meta` 涂成了深色底上的深色字；
- 退役模板必须解析到同版式的承接模板，否则已有简历换配色时会连带改变分页骨架。
"""
from __future__ import annotations

import re

import pytest

from app.services import render_resume_html
from app.templates import (BUILTIN_TEMPLATES, DARK_TOKENS, HAS_DARK_BAND, MIN_CONTRAST,
                           PAPER_TEXT_TOKENS, RETIRED_TEMPLATES, contrast, descriptor_for,
                           resolve_slug)

PAPER = "#ffffff"
TEXT_DARK_TOKENS = tuple(token for token in DARK_TOKENS if token != "sidebar_bg")

# 深色文字面的选择器片段：侧栏、横幅页头、表格实底表头行。
DARK_SELECTOR_RE = re.compile(r"\.sidebar\b|\.page-banner\b|\.main-grid \.section h2\b")


def export_css(slug: str = "classic") -> str:
    html = render_resume_html({"sections": []}, "样式", 1, slug)
    return re.search(r"<style>(.*?)</style>", html, re.S).group(1)


@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_paper_roles_clear_aa_on_white(slug):
    descriptor = BUILTIN_TEMPLATES[slug]
    for token in PAPER_TEXT_TOKENS:
        value = contrast(descriptor[token], PAPER)
        assert value >= MIN_CONTRAST, f"{slug} 的 {token} 在白纸上只有 {value:.2f}:1"


@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_section_title_clears_aa_on_its_title_bar(slug):
    """栏目标题坐在 tint 标题条上，这一对才是读者真正看到的组合。"""
    descriptor = BUILTIN_TEMPLATES[slug]
    value = contrast(descriptor["heading"], descriptor["tint"])
    assert value >= MIN_CONTRAST, f"{slug} 的栏目标题在标题条底色上只有 {value:.2f}:1"
    # 标题条是浅色底：它必须比白纸暗一点（否则看不见），但远不到正文级对比。
    assert contrast(descriptor["tint"], PAPER) < 1.4, f"{slug} 的标题条底色太深，会盖住正文"


@pytest.mark.parametrize("slug", sorted(BUILTIN_TEMPLATES))
def test_dark_roles_clear_aa_on_sidebar_bg(slug):
    descriptor = BUILTIN_TEMPLATES[slug]
    if descriptor["layout"] not in HAS_DARK_BAND:
        pytest.skip(f"{slug} 的版式没有深色文字面")
    for token in TEXT_DARK_TOKENS:
        value = contrast(descriptor[token], descriptor["sidebar_bg"])
        assert value >= MIN_CONTRAST, f"{slug} 的 {token} 在 sidebar_bg 上只有 {value:.2f}:1"


def test_on_dark_accent_is_derived_from_accent():
    """没有手工覆盖时，深色面强调色必须由 accent 派生，而不是留给人工维护。"""
    for slug, descriptor in BUILTIN_TEMPLATES.items():
        if descriptor["layout"] not in HAS_DARK_BAND:
            continue
        assert descriptor["on_dark_accent"] != descriptor["accent"] or contrast(descriptor["accent"], descriptor["sidebar_bg"]) >= MIN_CONTRAST, (
            f"{slug} 的深色面强调色既不达标也没有被派生"
        )


def test_export_dark_surfaces_do_not_use_paper_roles():
    """导出 CSS 中，深色文字面的规则只能引用深色面角色。"""
    css = export_css()
    paper_values = {BUILTIN_TEMPLATES["classic"][token] for token in PAPER_TEXT_TOKENS}
    offenders = []
    for block in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        selector, body = block[0].strip(), block[1]
        if not DARK_SELECTOR_RE.search(selector):
            continue
        for match in re.finditer(r"(?:^|;)\s*color:\s*(#[0-9a-f]{6})", body, re.IGNORECASE):
            if match.group(1).lower() in {value.lower() for value in paper_values}:
                offenders.append(f"{selector} -> {match.group(1)}")
    assert not offenders, "深色文字面引用了白纸角色（白纸强调色/辅助色在深色底上读不出来）：\n" + "\n".join(offenders)


def test_export_paints_dark_surface_text_with_dark_roles():
    """侧栏的时间、链接、字段值必须显式使用深色面角色，而不是靠继承碰运气。"""
    css = export_css()
    descriptor = BUILTIN_TEMPLATES["classic"]
    for selector in (".sidebar .entry-period", ".sidebar .block a", ".sidebar .block-meta"):
        rule = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
        assert rule, f"缺少深色面规则 {selector}"
        assert descriptor["sidebar_muted"] in rule.group(1) or descriptor["on_dark_accent"] in rule.group(1), (
            f"{selector} 没有使用深色面角色"
        )


@pytest.mark.parametrize("slug", sorted(RETIRED_TEMPLATES))
def test_retired_templates_resolve_to_a_kept_same_layout_template(slug):
    successor = RETIRED_TEMPLATES[slug]
    assert successor in BUILTIN_TEMPLATES, f"{slug} 的承接模板 {successor} 不在注册表里"
    assert resolve_slug(slug) == successor
    descriptor = descriptor_for(slug)
    assert descriptor is BUILTIN_TEMPLATES[successor]
    assert descriptor["layout"] == BUILTIN_TEMPLATES[successor]["layout"]
    # 退役模板仍可导出：解析到承接模板后不会退化成 classic 之外的骨架。
    html = render_resume_html({"sections": []}, "退役模板", 1, slug)
    assert BUILTIN_TEMPLATES[successor]["sidebar_bg"] in html


def test_registry_covers_every_layout_with_room_to_choose():
    layouts = {descriptor["layout"] for descriptor in BUILTIN_TEMPLATES.values()}
    assert layouts == {"sidebar", "plain", "banner", "grid", "line", "timeline", "rail"}
    assert 10 <= len(BUILTIN_TEMPLATES) <= 14, "模板库按精简目标维持在 10-14 套"
