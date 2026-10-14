"""Built-in resume template registry — the single source of truth.

Every template is described once here and consumed everywhere:
- ``render_resume_html`` (app/services.py) injects the palette into the A4 export CSS;
- ``/api/templates`` and resume payloads expose layout/serif/tokens so the SPA
  canvas can render the same look from CSS variables instead of hard-coded
  per-template stylesheets.

``layout`` decides the page skeleton (sidebar = 左侧栏双栏, plain = 单栏通排,
banner = 顶部横幅单栏, grid = 表格表单, line = 经典线式, timeline = 时间轴通排);
the colour tokens drive both renderers; ``serif`` switches the paper to a serif
family. Adding an entry here (plus the ResumeTemplate / TemplateVersion row
created automatically on startup) extends the library with no frontend changes.

Two rules keep the palettes honest, and both are enforced by tests:

1. **Surface-scoped roles.** The ``heading/title/meta/meta_label/copy/accent/rule``
   tokens are designed for the white paper. They must never be the foreground of
   text painted on ``sidebar_bg`` (the dark band of 侧栏/横幅/表格表头) — doing so
   is what made sidebar entry dates and field values unreadable. Text on the dark
   band uses ``sidebar_fg`` / ``sidebar_muted`` / ``sidebar_heading`` and the
   derived ``on_dark_accent``.
2. **Derived on-dark accent.** ``on_dark_accent`` is computed from ``accent`` so it
   always clears 4.5:1 against ``sidebar_bg`` while keeping the hue; set it
   explicitly in the entry only when the derived tone reads wrong.
"""

from __future__ import annotations

import colorsys

# Colour roles that paint text on the white paper. ``heading`` is additionally
# checked against the section title bar it sits on (``tint``).
PAPER_TEXT_TOKENS = ("heading", "title", "meta", "meta_label", "copy", "accent")
# Colour roles painted as a surface or a rule on paper, never as text.
PAPER_SURFACE_TOKENS = ("tint", "rule")
# Colour roles designed against the dark band (sidebar / banner / grid header row).
DARK_TOKENS = ("sidebar_bg", "sidebar_fg", "sidebar_muted", "sidebar_heading", "on_dark_accent")
# Colour tokens shared by the export renderer and the SPA canvas (via /api/templates).
COLOUR_TOKENS = PAPER_TEXT_TOKENS + PAPER_SURFACE_TOKENS + DARK_TOKENS
PAPER_TOKENS = PAPER_TEXT_TOKENS + PAPER_SURFACE_TOKENS  # 兼容旧引用

# 栏目标题条的底色：把强调色稀释到接近白纸。它只做背景，不承载正文对比度，
# 因此不参与"前景/背景"门槛，只要求栏目标题在它上面仍然达标。
TINT_WHITE_MIX = 0.9

# WCAG AA for body text. The gate in tests/test_template_contrast.py reads the
# same constant, so palette edits cannot slip below it unnoticed.
MIN_CONTRAST = 4.5

# Layouts that paint text on ``sidebar_bg``: the 侧栏/横幅 band and the 表格实底
# 表头行. Only these need an adapted accent — for plain/line/timeline ``sidebar_bg``
# is a decorative rule, not a text ground, so adapting against it would be wrong.
HAS_DARK_BAND = frozenset({"sidebar", "banner", "grid"})

_TEMPLATE_SOURCE: dict[str, dict] = {
    # —— 侧栏双栏版式（sidebar）：深色侧栏承载基本信息/技能/成果，主栏通排经历 ——
    "classic": {"name": "经典侧栏模板", "description": "深青侧栏 + 双栏正文，技术项目型岗位的通用首选。", "layout": "sidebar", "sidebar_bg": "#163b43", "sidebar_fg": "#f4f7f4", "sidebar_muted": "#cad9d5", "sidebar_heading": "#a7c9c2", "title": "#263f40", "meta": "#5f7873", "meta_label": "#527875", "copy": "#4c605d", "accent": "#236b74", "rule": "#d5e0dc"},
    "onyx": {"name": "曜黑侧栏模板", "description": "曜石黑侧栏配钴蓝点缀，对比强烈而克制，适合技术、设计与游戏行业岗位。", "layout": "sidebar", "sidebar_bg": "#191b1f", "sidebar_fg": "#f1f3f6", "sidebar_muted": "#b7bec9", "sidebar_heading": "#8fb0e8", "title": "#232830", "meta": "#667080", "meta_label": "#545e6d", "copy": "#404854", "accent": "#2e6bdc", "rule": "#dee1e6"},
    "merlot": {"name": "勃艮第侧栏模板", "description": "勃艮第酒红侧栏配玫瑰金细节，稳重优雅，适合金融、法务、品牌与高管岗位。", "layout": "sidebar", "sidebar_bg": "#452331", "sidebar_fg": "#f7f2f2", "sidebar_muted": "#d5c1c6", "sidebar_heading": "#cfa0ab", "title": "#38242c", "meta": "#6d5d62", "meta_label": "#5c4c51", "copy": "#4b3d42", "accent": "#8c3b52", "rule": "#e0d3d6"},
    # —— 单栏通排版式（plain）：白底深字、无侧栏，解析兼容性最好 ——
    "ink": {"name": "玄墨极简模板", "description": "黑白灰单栏通排、发丝分隔线，解析兼容性最好，适合外企投递与跨岗位通用。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#1c1e21", "sidebar_muted": "#5c636b", "sidebar_heading": "#1c1e21", "title": "#212529", "meta": "#6b7280", "meta_label": "#565e6b", "copy": "#3a4149", "accent": "#1f2933", "rule": "#e3e6ea"},
    "forest": {"name": "林野绿单栏模板", "description": "森林绿标题的清爽单栏通排，稳重自然，适合制造、医疗健康与可持续行业岗位。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#1d3a29", "sidebar_muted": "#5f7064", "sidebar_heading": "#1f4f33", "title": "#24352b", "meta": "#5f7064", "meta_label": "#4e5f53", "copy": "#3e4c42", "accent": "#2c7a4e", "rule": "#d9e5da"},
    "vermilion": {"name": "朱砂单栏模板", "description": "朱砂红栏目标题的档案风单栏通排，醒目传统，适合校招、国企与公职类岗位。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#2d2422", "sidebar_muted": "#6d605b", "sidebar_heading": "#a3352c", "title": "#332b28", "meta": "#776a64", "meta_label": "#645752", "copy": "#4a413d", "accent": "#b03a2e", "rule": "#ecd9d5"},
    # —— 顶部横幅版式（banner）：整幅深色页头呈现姓名与联系方式，单栏正文 ——
    "azure": {"name": "天青横幅模板", "description": "顶部横幅呈现姓名与联系方式，单栏正文，现代明亮，适合产品、运营与市场类岗位。", "layout": "banner", "sidebar_bg": "#1d5c8f", "sidebar_fg": "#ffffff", "sidebar_muted": "#cfe2f2", "sidebar_heading": "#bcd9f0", "title": "#21374d", "meta": "#5c7186", "meta_label": "#4a5d72", "copy": "#45566a", "accent": "#2273b0", "rule": "#d7e4ef"},
    "regent": {"name": "藏金行政横幅模板", "description": "深藏青横幅配鎏金细节的全衬线版式，沉稳华贵，适合高管、金融与法务类岗位。", "layout": "banner", "serif": True, "sidebar_bg": "#16283f", "sidebar_fg": "#f4f1e6", "sidebar_muted": "#bcc7d6", "sidebar_heading": "#d2b36a", "title": "#25344c", "meta": "#5e6b80", "meta_label": "#4c5a72", "copy": "#3c495c", "accent": "#8a6b1f", "rule": "#e0e0d2"},
    # —— 表格表单版式（grid）：传统 Word 表格风，栏目标题为实底表头行 ——
    "atlas": {"name": "雅蓝表格模板", "description": "雅蓝表头的表格表单版式，行列规整如传统 Word 表格，适合国企、银行、校招与公职类岗位。", "layout": "grid", "sidebar_bg": "#33427a", "sidebar_fg": "#f2f4fa", "sidebar_muted": "#c6cde4", "sidebar_heading": "#c6cde4", "title": "#2a3554", "meta": "#666f8c", "meta_label": "#535c7a", "copy": "#3d455c", "accent": "#3a56a8", "rule": "#d5dae8"},
    "flint": {"name": "灰石表格模板", "description": "灰石表头的表格表单版式，中性稳重、边线清爽，适合行政、制造业与跨行业通用投递。", "layout": "grid", "sidebar_bg": "#46494d", "sidebar_fg": "#f4f4f2", "sidebar_muted": "#c9cbcc", "sidebar_heading": "#d4d6d4", "title": "#3a3e42", "meta": "#6e7377", "meta_label": "#5a5f63", "copy": "#45494d", "accent": "#5c636b", "rule": "#dcdedc"},
    # —— 经典线式版式（line）：居中姓名 + 联系方式单行，栏目标题居中带横线 ——
    "quill": {"name": "羽墨线式模板", "description": "羽墨衬线经典线式版式，居中姓名配细横线，黑白严谨，适合高校、科研与留学申请。", "layout": "line", "serif": True, "sidebar_bg": "#26231f", "sidebar_fg": "#faf8f4", "sidebar_muted": "#cfc9be", "sidebar_heading": "#cfc9be", "title": "#322d26", "meta": "#756e60", "meta_label": "#5f594d", "copy": "#45403a", "accent": "#6b5f46", "rule": "#d9d4c8"},
    # —— 时间轴版式（timeline）：左侧时间线串起条目，圆点标注时间节点 ——
    "lumen": {"name": "晨光时间轴模板", "description": "晨蓝时间轴版式，左侧时间线串起经历，脉络清晰，适合互联网、产品与运营类岗位。", "layout": "timeline", "sidebar_bg": "#2f7fb5", "sidebar_fg": "#f4f9fc", "sidebar_muted": "#cfe3ee", "sidebar_heading": "#cfe3ee", "title": "#24455a", "meta": "#5d7683", "meta_label": "#526b7a", "copy": "#3f5666", "accent": "#2a6d99", "rule": "#d8e5ec"},
    # —— 标签栏版式（rail）：左侧栏目标签列 + 右侧内容，中文校招的经典形态 ——
    "slate-rail": {"name": "简牍标签栏模板", "description": "左侧栏目标签栏 + 右侧内容的单栏通排，栏目省去标题条、密度最高，适合校招与国企类岗位。", "layout": "rail", "sidebar_bg": "#2b3336", "sidebar_fg": "#f4f7f4", "sidebar_muted": "#cad9d5", "sidebar_heading": "#a7c9c2", "title": "#263f40", "meta": "#5f7873", "meta_label": "#527875", "copy": "#4c605d", "accent": "#236b74", "rule": "#d5e0dc"},
}

# 退役模板 -> 承接模板：已有简历仍按承接模板的配色渲染，不会因为这次精简
# 突然换成另一个色系；承接模板用同一个版式骨架，因此分页结构也不变。
RETIRED_TEMPLATES: dict[str, str] = {
    "focus": "classic",
    "slate": "onyx",
    "violet": "merlot",
    "umber": "merlot",
    "pine": "forest",
    "brass": "regent",
    "celadon": "azure",
    "haze": "classic",
    "minimal": "ink",
    "cobalt": "ink",
    "marine": "ink",
    "academic": "quill",
    "indigo": "quill",
    "meridian": "lumen",
}

# 十二套内置模板：六种版式骨架，侧栏与单栏各多留一套通用配色。
BUILTIN_TEMPLATES: dict[str, dict] = {}


def _rgb(colour: str) -> tuple[int, int, int]:
    value = colour.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(red: float, green: float, blue: float) -> str:
    return "#%02x%02x%02x" % tuple(min(255, max(0, round(channel * 255))) for channel in (red, green, blue))


def _channel_luminance(value: float) -> float:
    value /= 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    red, green, blue = _rgb(colour)
    return 0.2126 * _channel_luminance(red) + 0.7152 * _channel_luminance(green) + 0.0722 * _channel_luminance(blue)


def contrast(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def adapt_to_surface(foreground: str, background: str, target: float = MIN_CONTRAST) -> str:
    """Return ``foreground`` nudged along the HSL lightness axis until it clears ``target``.

    Direction follows the background: lighten a foreground sitting on a darker
    surface, darken one sitting on a lighter surface. Hue and saturation are kept
    so the tone still reads as the same accent.
    """
    if contrast(foreground, background) >= target:
        return foreground
    hue, lightness, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in _rgb(foreground)))
    towards_dark = luminance(background) > luminance(foreground)
    for step in range(1, 101):
        candidate_lightness = lightness - step * 0.01 if towards_dark else lightness + step * 0.01
        if not 0 <= candidate_lightness <= 1:
            break
        candidate = _hex(*colorsys.hls_to_rgb(hue, candidate_lightness, saturation))
        if contrast(candidate, background) >= target:
            return candidate
    return "#000000" if towards_dark else "#ffffff"


def blend_towards(foreground: str, background: str, weight: float) -> str:
    """Mix ``weight`` of ``background`` into ``foreground`` (0 = keep, 1 = background).

    Both colours are handled in 0..1 like :func:`colorsys.hls_to_rgb`, which
    :func:`_hex` expects.
    """
    fg = [channel / 255 for channel in _rgb(foreground)]
    bg = [channel / 255 for channel in _rgb(background)]
    return _hex(*(fg[index] + (bg[index] - fg[index]) * weight for index in range(3)))


def _resolve(descriptor: dict) -> dict:
    resolved = dict(descriptor)
    resolved["tint"] = descriptor.get("tint") or blend_towards(descriptor["accent"], "#ffffff", TINT_WHITE_MIX)
    # 栏目标题与强调色同源：左侧色条、圆点、时间与标题条用同一个色，版面才不会
    # 出现"标题一种蓝、装饰另一种蓝"。标题坐在标题条底色上，因此按那层底色再
    # 校一次对比度（比强调色略深一点），需要区分时在注册表里显式写 heading。
    resolved["heading"] = descriptor.get("heading") or adapt_to_surface(descriptor["accent"], resolved["tint"])
    if descriptor["layout"] in HAS_DARK_BAND:
        resolved["on_dark_accent"] = descriptor.get("on_dark_accent") or adapt_to_surface(descriptor["accent"], descriptor["sidebar_bg"])
    else:
        # 没有深色文字面：强调色只出现在白纸上，无需为深色底再派生一份。
        resolved["on_dark_accent"] = descriptor.get("on_dark_accent") or descriptor["accent"]
    return resolved


BUILTIN_TEMPLATES.update({slug: _resolve(descriptor) for slug, descriptor in _TEMPLATE_SOURCE.items()})


def resolve_slug(slug: str | None) -> str:
    """Map a retired slug onto its successor; unknown slugs fall back to classic."""
    if slug in BUILTIN_TEMPLATES:
        return slug  # type: ignore[return-value]
    if slug and slug in RETIRED_TEMPLATES:
        return RETIRED_TEMPLATES[slug]
    return "classic"


def descriptor_for(slug: str | None) -> dict:
    return BUILTIN_TEMPLATES[resolve_slug(slug)]


def template_tokens(descriptor: dict) -> dict:
    return {key: descriptor[key] for key in COLOUR_TOKENS}


def template_public_info(descriptor: dict) -> dict:
    """Layout + palette fields the SPA needs to render a template."""
    return {"layout": descriptor["layout"], "serif": bool(descriptor.get("serif")), "tokens": template_tokens(descriptor)}
