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
"""

from __future__ import annotations

BUILTIN_TEMPLATES: dict[str, dict] = {
    "classic": {"name": "经典侧栏模板", "description": "深青侧栏 + 双栏正文，适合技术项目型岗位。", "layout": "sidebar", "sidebar_bg": "#163b43", "sidebar_fg": "#f4f7f4", "sidebar_muted": "#cad9d5", "sidebar_heading": "#a7c9c2", "heading": "#17343a", "title": "#263f40", "meta": "#66807b", "meta_label": "#527875", "copy": "#4c605d", "accent": "#236b74", "rule": "#d5e0dc"},
    "focus": {"name": "深蓝聚焦模板", "description": "深蓝侧栏、强标题对比，强调重点条目。", "layout": "sidebar", "sidebar_bg": "#1f2a44", "sidebar_fg": "#eef1f8", "sidebar_muted": "#b8c2dc", "sidebar_heading": "#93a5cd", "heading": "#1c2947", "title": "#24324f", "meta": "#5f6c8c", "meta_label": "#4c5a7d", "copy": "#3d4a66", "accent": "#34549c", "rule": "#d7dcea"},
    "minimal": {"name": "简约无侧栏模板", "description": "单栏通排、浅色分隔线，内容密度优先。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#24342f", "sidebar_muted": "#4c605d", "sidebar_heading": "#1d5c69", "heading": "#1d5c69", "title": "#24342f", "meta": "#667a72", "meta_label": "#52706a", "copy": "#37473f", "accent": "#1d5c69", "rule": "#e1e8e3"},
    "slate": {"name": "石墨侧栏模板", "description": "石墨灰侧栏配琥珀点缀，沉稳克制，适合管理、咨询与行政类岗位。", "layout": "sidebar", "sidebar_bg": "#2e383d", "sidebar_fg": "#f4f4f1", "sidebar_muted": "#c2cbc9", "sidebar_heading": "#d8b571", "heading": "#2c3438", "title": "#333c40", "meta": "#6d7773", "meta_label": "#57615e", "copy": "#4b5451", "accent": "#b0803c", "rule": "#dbe0dd"},
    "azure": {"name": "天青横幅模板", "description": "顶部横幅呈现姓名与联系方式，单栏正文，现代明亮，适合产品、运营与市场类岗位。", "layout": "banner", "sidebar_bg": "#1d5c8f", "sidebar_fg": "#ffffff", "sidebar_muted": "#cfe2f2", "sidebar_heading": "#bcd9f0", "heading": "#1d4c74", "title": "#21374d", "meta": "#5c7186", "meta_label": "#4a5d72", "copy": "#45566a", "accent": "#2273b0", "rule": "#d7e4ef"},
    "academic": {"name": "学术衬线模板", "description": "衬线字体单栏通排，严谨传统，适合科研、高校与研究院所简历。", "layout": "plain", "serif": True, "sidebar_bg": "#ffffff", "sidebar_fg": "#2c2822", "sidebar_muted": "#5f584b", "sidebar_heading": "#4a3b28", "heading": "#4a3b28", "title": "#2e2a22", "meta": "#6f6759", "meta_label": "#5c5446", "copy": "#423c30", "accent": "#7c5a2e", "rule": "#d9d2c3"},
    "pine": {"name": "松屿绿侧栏模板", "description": "深松绿侧栏配苔绿点缀，清新沉稳，适合产品、运营与可持续行业岗位。", "layout": "sidebar", "sidebar_bg": "#24463a", "sidebar_fg": "#f2f6f0", "sidebar_muted": "#c2d4c4", "sidebar_heading": "#9fc4a4", "heading": "#1f3d31", "title": "#273b31", "meta": "#63776c", "meta_label": "#52655a", "copy": "#42544a", "accent": "#2e6b4f", "rule": "#d5e0d6"},
    "merlot": {"name": "勃艮第侧栏模板", "description": "勃艮第酒红侧栏配玫瑰金细节，稳重优雅，适合金融、法务、品牌与高管岗位。", "layout": "sidebar", "sidebar_bg": "#452331", "sidebar_fg": "#f7f2f2", "sidebar_muted": "#d5c1c6", "sidebar_heading": "#cfa0ab", "heading": "#3f2130", "title": "#38242c", "meta": "#6d5d62", "meta_label": "#5c4c51", "copy": "#4b3d42", "accent": "#8c3b52", "rule": "#e0d3d6"},
    "ink": {"name": "玄墨极简模板", "description": "黑白灰单栏通排、发丝分隔线，解析兼容性最好，适合外企投递与跨岗位通用。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#1c1e21", "sidebar_muted": "#5c636b", "sidebar_heading": "#1c1e21", "heading": "#1c1e21", "title": "#212529", "meta": "#6b7280", "meta_label": "#565e6b", "copy": "#3a4149", "accent": "#1f2933", "rule": "#e3e6ea"},
    "brass": {"name": "鎏金横幅模板", "description": "暖褐横幅呈现姓名与联系方式，铜金细节温暖大气，适合市场、教育与商务岗位。", "layout": "banner", "sidebar_bg": "#3a3327", "sidebar_fg": "#f8f5ee", "sidebar_muted": "#d6cbb4", "sidebar_heading": "#d9bd8e", "heading": "#3d3424", "title": "#3a3226", "meta": "#6f6753", "meta_label": "#5d5544", "copy": "#4a4436", "accent": "#96742e", "rule": "#e2dcc9"},
    "marine": {"name": "海军蓝单栏模板", "description": "海军蓝标题与浅蓝灰分隔线的单栏通排，白底深字解析友好，适合金融、咨询与企业管理类岗位。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#1b2a4a", "sidebar_muted": "#56617a", "sidebar_heading": "#1b2a4a", "heading": "#1b2a4a", "title": "#22304f", "meta": "#5f6a85", "meta_label": "#4d5872", "copy": "#3c465e", "accent": "#2c4a8a", "rule": "#dce2ef"},
    "haze": {"name": "雾蓝侧栏模板", "description": "雾霾蓝侧栏配灰蓝细节，低饱和沉稳不抢眼，适合互联网运营、行政与应届生投递。", "layout": "sidebar", "sidebar_bg": "#46617a", "sidebar_fg": "#f3f6f9", "sidebar_muted": "#ccd8e2", "sidebar_heading": "#a9c2d6", "heading": "#31485c", "title": "#3a4f60", "meta": "#64798a", "meta_label": "#53687a", "copy": "#45596a", "accent": "#527391", "rule": "#d8e1e8"},
    "violet": {"name": "紫藤侧栏模板", "description": "深紫罗兰侧栏配薰衣草细节，个性而克制，适合设计、创意与品牌岗位。", "layout": "sidebar", "sidebar_bg": "#3d2e5e", "sidebar_fg": "#f5f2fa", "sidebar_muted": "#cfc6e2", "sidebar_heading": "#b3a3d9", "heading": "#372a52", "title": "#3e3159", "meta": "#6a5f84", "meta_label": "#594f70", "copy": "#4a4162", "accent": "#6d4fc2", "rule": "#ded7ec"},
    "celadon": {"name": "青瓷横幅模板", "description": "青瓷横幅呈现姓名与联系方式，青碧细节清雅明快，适合市场、用户体验与创意机构岗位。", "layout": "banner", "sidebar_bg": "#0e6f6b", "sidebar_fg": "#f2f9f8", "sidebar_muted": "#c5e2df", "sidebar_heading": "#a4d4cf", "heading": "#0d5a56", "title": "#1f4a47", "meta": "#5d7a77", "meta_label": "#4c6966", "copy": "#405956", "accent": "#0d7377", "rule": "#d3e5e3"},
    "vermilion": {"name": "朱砂单栏模板", "description": "朱砂红栏目标题的档案风单栏通排，白纸暖线醒目传统，适合校招、国企与公职类岗位。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#2d2422", "sidebar_muted": "#6d605b", "sidebar_heading": "#a3352c", "heading": "#a3352c", "title": "#332b28", "meta": "#776a64", "meta_label": "#645752", "copy": "#4a413d", "accent": "#b03a2e", "rule": "#ecd9d5"},
    "cobalt": {"name": "钴蓝单栏模板", "description": "钴蓝标题与浅蓝分隔线的极清单栏通排，单一强调色解析最友好，适合互联网、技术与数据类岗位。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#16244d", "sidebar_muted": "#5d6880", "sidebar_heading": "#16337f", "heading": "#16337f", "title": "#1d2436", "meta": "#5d6880", "meta_label": "#4b5670", "copy": "#3b4356", "accent": "#2050c8", "rule": "#dbe2f4"},
    "forest": {"name": "林野绿单栏模板", "description": "森林绿标题的清爽单栏通排，稳重自然，适合制造、医疗健康与可持续行业岗位。", "layout": "plain", "sidebar_bg": "#ffffff", "sidebar_fg": "#1d3a29", "sidebar_muted": "#5f7064", "sidebar_heading": "#1f4f33", "heading": "#1f4f33", "title": "#24352b", "meta": "#5f7064", "meta_label": "#4e5f53", "copy": "#3e4c42", "accent": "#2c7a4e", "rule": "#d9e5da"},
    "regent": {"name": "藏金行政横幅模板", "description": "深藏青横幅配鎏金细节的全衬线版式，沉稳华贵，适合高管、金融与法务类岗位。", "layout": "banner", "serif": True, "sidebar_bg": "#16283f", "sidebar_fg": "#f4f1e6", "sidebar_muted": "#bcc7d6", "sidebar_heading": "#d2b36a", "heading": "#1d3050", "title": "#25344c", "meta": "#5e6b80", "meta_label": "#4c5a72", "copy": "#3c495c", "accent": "#a07f2e", "rule": "#e0e0d2"},
    "umber": {"name": "赭木侧栏模板", "description": "赭木棕侧栏配赤陶点缀，温暖亲和有质感，适合品牌、市场与消费行业岗位。", "layout": "sidebar", "sidebar_bg": "#4c3a2a", "sidebar_fg": "#f8f4ec", "sidebar_muted": "#dbcdba", "sidebar_heading": "#dcae7e", "heading": "#3c2e21", "title": "#463628", "meta": "#716355", "meta_label": "#5e5145", "copy": "#4c4034", "accent": "#b05c33", "rule": "#e8dfd2"},
    "onyx": {"name": "曜黑侧栏模板", "description": "曜石黑侧栏配钴蓝点缀，对比强烈而克制，适合技术、设计与游戏行业岗位。", "layout": "sidebar", "sidebar_bg": "#191b1f", "sidebar_fg": "#f1f3f6", "sidebar_muted": "#b7bec9", "sidebar_heading": "#8fb0e8", "heading": "#1c2026", "title": "#232830", "meta": "#667080", "meta_label": "#545e6d", "copy": "#404854", "accent": "#2e6bdc", "rule": "#dee1e6"},
    # —— 表格表单版式（grid）：传统 Word 表格风，栏目标题为实底表头行，栏目内容带边框 ——
    "atlas": {"name": "雅蓝表格模板", "description": "雅蓝表头的表格表单版式，行列规整如传统 Word 表格，适合国企、银行、校招与公职类岗位。", "layout": "grid", "sidebar_bg": "#33427a", "sidebar_fg": "#f2f4fa", "sidebar_muted": "#c6cde4", "sidebar_heading": "#c6cde4", "heading": "#26325c", "title": "#2a3554", "meta": "#666f8c", "meta_label": "#535c7a", "copy": "#3d455c", "accent": "#3a56a8", "rule": "#d5dae8"},
    "flint": {"name": "灰石表格模板", "description": "灰石表头的表格表单版式，中性稳重、边线清爽，适合行政、制造业与跨行业通用投递。", "layout": "grid", "sidebar_bg": "#46494d", "sidebar_fg": "#f4f4f2", "sidebar_muted": "#c9cbcc", "sidebar_heading": "#d4d6d4", "heading": "#34383c", "title": "#3a3e42", "meta": "#6e7377", "meta_label": "#5a5f63", "copy": "#45494d", "accent": "#5c636b", "rule": "#dcdedc"},
    # —— 经典线式版式（line）：居中姓名 + 联系方式单行，栏目标题居中带横线，条目时间右对齐 ——
    "quill": {"name": "羽墨线式模板", "description": "羽墨衬线经典线式版式，居中姓名配细横线，黑白严谨，适合高校、科研与留学申请。", "layout": "line", "serif": True, "sidebar_bg": "#26231f", "sidebar_fg": "#faf8f4", "sidebar_muted": "#cfc9be", "sidebar_heading": "#cfc9be", "heading": "#2b2722", "title": "#322d26", "meta": "#756e60", "meta_label": "#5f594d", "copy": "#45403a", "accent": "#6b5f46", "rule": "#d9d4c8"},
    "indigo": {"name": "靛青线式模板", "description": "靛青经典线式版式，居中姓名配右对齐时间，干净利落，适合技术、数据与研究类岗位。", "layout": "line", "sidebar_bg": "#24365e", "sidebar_fg": "#eef2fa", "sidebar_muted": "#b9c4dd", "sidebar_heading": "#b9c4dd", "heading": "#22335c", "title": "#2c3a5e", "meta": "#62708d", "meta_label": "#4f5c78", "copy": "#3c4763", "accent": "#3452b0", "rule": "#d6dcf0"},
    # —— 时间轴版式（timeline）：左侧时间线串起条目，圆点标注时间节点 ——
    "lumen": {"name": "晨光时间轴模板", "description": "晨蓝时间轴版式，左侧时间线串起经历，脉络清晰，适合互联网、产品与运营类岗位。", "layout": "timeline", "sidebar_bg": "#2f7fb5", "sidebar_fg": "#f4f9fc", "sidebar_muted": "#cfe3ee", "sidebar_heading": "#cfe3ee", "heading": "#1f4c66", "title": "#24455a", "meta": "#647d8c", "meta_label": "#526b7a", "copy": "#3f5666", "accent": "#2f7fb5", "rule": "#d8e5ec"},
    "meridian": {"name": "赭金时间轴模板", "description": "赭金时间轴版式，暖色圆点标注时间节点，亲和醒目，适合市场、教育与创意类岗位。", "layout": "timeline", "sidebar_bg": "#b5652f", "sidebar_fg": "#fbf6f0", "sidebar_muted": "#eed9c4", "sidebar_heading": "#eed9c4", "heading": "#7a4426", "title": "#6e4026", "meta": "#8a7364", "meta_label": "#73604f", "copy": "#5c4638", "accent": "#b5652f", "rule": "#ecdfd2"},
}

# Colour tokens shared by the export renderer and the SPA canvas (via /api/templates).
COLOUR_TOKENS = ("sidebar_bg", "sidebar_fg", "sidebar_muted", "sidebar_heading", "heading", "title", "meta", "meta_label", "copy", "accent", "rule")


def template_tokens(descriptor: dict) -> dict:
    return {key: descriptor[key] for key in COLOUR_TOKENS}


def template_public_info(descriptor: dict) -> dict:
    """Layout + palette fields the SPA needs to render a template."""
    return {"layout": descriptor["layout"], "serif": bool(descriptor.get("serif")), "tokens": template_tokens(descriptor)}
