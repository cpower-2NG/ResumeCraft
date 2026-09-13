from __future__ import annotations

import hashlib
import html
import json
import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .workbench_models import (
    AchievementFactDetail, EducationFactDetail, ExperienceFactDetail, FactCustomField,
    FactEvidence, FactRecord, LinkFactDetail, PersonalFactDetail, RequirementProfile,
    ResumeFactReference, SkillFactDetail,
)

CORE_SECTIONS = [
    ("basics", "基本信息"), ("target", "求职目标"), ("profile", "个人简介"),
    ("education", "教育经历"), ("experience", "项目与实践"),
    ("skills", "技能"), ("awards", "成果"), ("links", "链接与作品集"),
]

SECTION_HEADINGS = [(title, key) for key, title in CORE_SECTIONS]

# Built-in code-rendered templates. ``layout`` decides the page skeleton
# (sidebar = 左侧栏双栏, plain = 单栏通排, banner = 顶部横幅单栏); the colour
# tokens are injected into the exported CSS. ``serif`` switches the paper to a
# serif family. Adding a template to this registry (plus a ResumeTemplate /
# TemplateVersion row, created automatically on startup) extends the library.
BUILTIN_TEMPLATES = {
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
}

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def render_markdown(text: str) -> str:
    """Escape, then apply the controlled subset: bold, italic, links, unordered lists."""
    escaped = html.escape(str(text or ""), quote=False)
    escaped = MARKDOWN_LINK_RE.sub(lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    lines = escaped.split("\n")
    rendered: list[str] = []
    list_items: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("- "):
            list_items.append(f"<li>{stripped[2:]}</li>")
            continue
        if list_items:
            rendered.append("<ul>" + "".join(list_items) + "</ul>")
            list_items = []
        rendered.append(line)
    if list_items:
        rendered.append("<ul>" + "".join(list_items) + "</ul>")
    return "".join(rendered).replace("\n", "<br>")

FACT_SCHEMAS = {
    "basics": [("name", "姓名", "text", True), ("phone", "电话", "text", False), ("email", "邮箱", "email", False), ("city", "所在地", "text", False), ("desired_city", "目标城市", "text", False), ("birth_date", "出生日期", "text", False), ("age", "年龄", "text", False), ("hometown", "籍贯", "text", False), ("status", "身份状态", "text", False), ("graduation", "毕业时间", "text", False), ("availability", "到岗安排", "textarea", False), ("bio", "个人简介", "textarea", False)],
    "education": [("school", "学校", "text", True), ("major", "专业", "text", False), ("degree", "学历", "text", False), ("start_date", "入学时间", "text", False), ("end_date", "毕业时间", "text", False), ("period", "在读期间", "text", False), ("gpa", "GPA", "text", False), ("ranking", "专业排名", "text", False), ("achievement", "成绩与成果", "textarea", False), ("courses", "相关课程", "textarea", False)],
    "experience": [("kind", "经历类型", "text", False), ("period", "时间", "text", False), ("organization", "组织/公司", "text", False), ("role", "角色", "text", False), ("team_size", "团队规模", "text", False), ("context", "背景", "textarea", False), ("work", "具体工作", "textarea", False), ("tools", "工具与技术", "textarea", False), ("outcome", "结果", "textarea", False), ("challenge", "挑战", "textarea", False), ("solution", "解决方案", "textarea", False), ("public_note", "公开说明", "textarea", False)],
    "skills": [("skill_category", "技能分类", "text", False), ("proficiency", "熟练程度", "text", False), ("context", "使用场景", "textarea", False)],
    "awards": [("period", "时间", "text", False), ("issuer", "颁发方", "text", False), ("result", "结果", "text", False), ("note", "说明", "textarea", False)],
    "links": [("link_type", "链接类型", "text", False), ("url", "地址", "url", True), ("label", "显示名称", "text", False), ("note", "说明", "textarea", False)],
}
DETAIL_MODELS = {"basics": PersonalFactDetail, "education": EducationFactDetail, "experience": ExperienceFactDetail, "skills": SkillFactDetail, "awards": AchievementFactDetail, "links": LinkFactDetail}


def json_value(value: str, default):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=lambda item: item.isoformat() if hasattr(item, "isoformat") else str(item))


def content_hash(content: dict) -> str:
    return hashlib.sha256(dump(content).encode("utf-8")).hexdigest()


def identity_key(profile: RequirementProfile) -> str:
    requirements = json_value(profile.core_requirements, [])
    normalized = sorted({str(item).strip().lower() for item in requirements if str(item).strip()})
    fields = [profile.role_direction, " ".join(normalized), profile.resume_strategy]
    return "|".join(re.sub(r"\s+", " ", (value or "").strip()).lower() for value in fields)


def _model_values(detail) -> dict:
    if not detail:
        return {}
    return {column.name: getattr(detail, column.name) for column in detail.__table__.columns if column.name != "fact_id"}


def fact_details(db: Session, fact: FactRecord) -> dict:
    legacy = json_value(fact.content, {})
    model = DETAIL_MODELS.get(fact.category)
    detail = db.get(model, fact.id) if model else None
    values = dict(legacy)
    values.update(_model_values(detail))
    if fact.category == "skills" and "skill_category" not in values and "category" in values:
        values["skill_category"] = values["category"]
    return {key: value for key, value in values.items() if value not in (None, "")}


def replace_fact_details(db: Session, fact: FactRecord, values: dict) -> None:
    model = DETAIL_MODELS.get(fact.category)
    if not model:
        return
    detail = db.get(model, fact.id)
    if not detail:
        detail = model(fact_id=fact.id)
        db.add(detail)
    for key, *_ in FACT_SCHEMAS[fact.category]:
        setattr(detail, key, str(values.get(key, "") or ""))


def custom_fields(db: Session, fact_id: int) -> list[dict]:
    return [{"key": item.field_key, "label": item.label, "value": item.value, "displayable": item.displayable, "sort_order": item.sort_order} for item in db.query(FactCustomField).filter(FactCustomField.fact_id == fact_id).order_by(FactCustomField.sort_order).all()]


def replace_custom_fields(db: Session, fact_id: int, values: list[dict]) -> None:
    db.query(FactCustomField).filter(FactCustomField.fact_id == fact_id).delete()
    for index, item in enumerate(values):
        key = str(item.get("key") or item.get("field_key") or "").strip()
        if not key:
            continue
        db.add(FactCustomField(fact_id=fact_id, field_key=key, label=str(item.get("label") or key), value=str(item.get("value") or ""), displayable=bool(item.get("displayable", True)), sort_order=int(item.get("sort_order", index))))


def fact_to_block(db: Session, fact: FactRecord, section_id: str) -> dict:
    details = fact_details(db, fact)
    extra = [item for item in custom_fields(db, fact.id) if item.get("value") not in (None, "")]
    fields = dict(details)
    field_labels = {}
    for item in extra:
        fields[item["key"]] = item["value"]
        field_labels[item["key"]] = item["label"] or item["key"]
    if section_id == "profile":
        display_fields = ["bio"] if details.get("bio") else ["summary"]
        plain = details.get("bio") or details.get("summary") or ""
    elif section_id == "basics":
        display_fields = [key for key in ("phone", "email", "city", "desired_city", "hometown", "status", "graduation", "availability") if details.get(key)]
        plain = ""
    elif section_id == "education":
        display_fields = [key for key in ("period", "major", "degree", "gpa", "ranking") if details.get(key)]
        plain = "\n".join(str(details[key]) for key in ("achievement", "courses") if details.get(key))
    elif section_id == "experience":
        display_fields = [key for key in ("period", "organization", "role", "team_size", "tools") if details.get(key)]
        plain = "\n".join(str(details[key]) for key in ("context", "work", "outcome", "challenge", "solution", "public_note") if details.get(key))
    elif section_id == "skills":
        display_fields = [key for key in ("skill_category", "proficiency") if details.get(key)]
        plain = str(details.get("context") or "")
    elif section_id == "awards":
        display_fields = [key for key in ("period", "issuer", "result") if details.get(key)]
        plain = str(details.get("note") or "")
    else:
        display_fields = [key for key in ("link_type", "label", "url") if details.get(key)]
        plain = str(details.get("note") or "")
    if not plain and details.get("summary"):
        display_fields = ["summary"]
        plain = str(details["summary"])
    display_fields.extend(item["key"] for item in extra if item.get("displayable") and item["key"] not in display_fields)
    if section_id == "profile":
        fields.pop("bio", None)
    title = str(details.get("name") or fact.title) if section_id == "basics" else fact.title
    return {"id": f"fact-{fact.id}", "type": "fact", "title": title, "content": plain, "fields": fields, "field_labels": field_labels, "display_fields": display_fields, "source_refs": [fact.id], "origin": "fact"}


def allowed_categories(section_id: str) -> list[str]:
    return ["basics"] if section_id in {"basics", "profile"} else ([] if section_id == "target" else [section_id])


def build_resume_content(db: Session, profile: RequirementProfile, selection: dict) -> dict:
    facts = {item.id: item for item in db.query(FactRecord).filter(FactRecord.workspace_id == profile.workspace_id, FactRecord.status == "active").all()}
    sections = []
    for section_id, title in CORE_SECTIONS:
        selected_ids = selection.get(section_id, [])
        blocks = [fact_to_block(db, facts[fact_id], section_id) for fact_id in selected_ids if fact_id in facts and facts[fact_id].category in allowed_categories(section_id)]
        if section_id == "target":
            target_fields = {
                "role_direction": profile.role_direction,
                "core_requirements": "、".join(json_value(profile.core_requirements, [])),
            }
            blocks = [{
                "id": "profile-target",
                "type": "profile",
                "title": profile.role_direction or profile.name or "求职目标",
                "content": profile.resume_strategy or "请填写与目标岗位匹配的简历强调方向。",
                "fields": target_fields,
                "field_labels": {"role_direction": "岗位方向", "core_requirements": "核心要求"},
                "display_fields": [key for key, value in target_fields.items() if value],
                "source_refs": [],
                "origin": "profile",
            }]
        sections.append({"id": section_id, "type": section_id, "title": title, "visibility": True, "blocks": blocks})
    return {"sections": sections}


def source_manifest(content: dict) -> list[dict]:
    return [{"fact_id": fact_id, "section_id": section["id"], "block_id": block["id"]} for section in content.get("sections", []) for block in section.get("blocks", []) for fact_id in block.get("source_refs", []) if isinstance(fact_id, int)]


def sync_references(db: Session, identity_id: int, content: dict) -> None:
    db.execute(delete(ResumeFactReference).where(ResumeFactReference.resume_identity_id == identity_id))
    for item in source_manifest(content):
        db.add(ResumeFactReference(resume_identity_id=identity_id, **item))


def serialize_fact(db: Session, item: FactRecord) -> dict:
    details = fact_details(db, item)
    return {"id": item.id, "category": item.category, "title": item.title, "content": json_value(item.content, {}), "details": details, "custom_fields": custom_fields(db, item.id), "display_fields": list(details), "tags": json_value(item.tags, []), "status": item.status, "source_note": item.source_note, "created_at": item.created_at, "updated_at": item.updated_at}


def serialize_profile(item: RequirementProfile) -> dict:
    return {"id": item.id, "name": item.name, "role_direction": item.role_direction, "core_requirements": json_value(item.core_requirements, []), "general_requirements": item.general_requirements, "responsibilities": item.responsibilities, "resume_strategy": item.resume_strategy, "raw_jd": item.raw_jd, "source_note": item.source_note, "identity_key": item.identity_key, "status": item.status, "updated_at": item.updated_at}


def serialize_version(version) -> dict:
    return {"id": version.id, "version_number": version.version_number, "content": json_value(version.content, {}), "reason": version.reason, "change_summary": version.change_summary, "created_at": version.created_at}


def evidence_count(db: Session, fact_id: int) -> int:
    return db.query(FactEvidence).filter(FactEvidence.fact_id == fact_id).count()


MAIN_PAGE_BUDGET = 2400
SIDE_PAGE_BUDGET = 1500
BANNER_PAGE_BUDGET = 2200
SIDE_SECTIONS = ("basics", "skills", "awards")


def section_fragment_limit(section_id: str) -> int:
    return 520 if section_id in SIDE_SECTIONS else 900


def section_item_weight(section_id: str, content: str, field_count: int) -> int:
    base = 70 if section_id in SIDE_SECTIONS else 90
    return base + len(content) + field_count * (10 if section_id in SIDE_SECTIONS else 20)


def render_resume_html(content: dict, title: str, version_number: int, template_slug: str = "classic") -> str:
    """Render a self-contained, print-ready HTML snapshot from a saved version.

    Blocks are fragmented and packed with the same weights as the SPA preview
    (see ``web/src/App.tsx``) so page breaks match between preview and export.
    Each page repeats a section heading at most once; a heading that continues
    from an earlier page is suffixed with “（续）”.
    """
    descriptor = BUILTIN_TEMPLATES.get(template_slug) or BUILTIN_TEMPLATES["classic"]
    sections = {item.get("id"): item for item in content.get("sections", [])}
    field_labels = {
        "phone": "电话", "email": "邮箱", "city": "所在地", "desired_city": "目标城市", "hometown": "籍贯",
        "status": "身份状态", "graduation": "毕业时间", "availability": "到岗安排", "bio": "个人简介",
        "period": "时间", "major": "专业", "degree": "学历", "gpa": "GPA", "ranking": "专业排名",
        "organization": "组织/公司", "role": "角色", "team_size": "团队规模", "tools": "工具与技术",
        "skill_category": "技能分类", "proficiency": "熟练程度", "issuer": "颁发方", "result": "结果",
        "link_type": "链接类型", "url": "地址", "label": "显示名称",
    }

    def esc(value) -> str:
        return html.escape(str(value or ""), quote=True)

    def block_text(block: dict) -> str:
        return render_markdown(block.get("content", ""))

    def block_fields(block: dict) -> str:
        fields = block.get("fields") or {}
        displayed = block.get("display_fields") or list(fields)
        labels = {**field_labels, **(block.get("field_labels") or {})}
        return "".join(f'<span class="meta"><b>{esc(labels.get(key, key))}</b> {esc(fields.get(key))}</span>' for key in displayed if fields.get(key))

    def block_html(block: dict, heading: str = "") -> str:
        content_text = block_text(block)
        if (block.get("fields") or {}).get("url"):
            url = str(block["fields"]["url"])
            label = (block.get("fields") or {}).get("label") or url
            content_text = f'<a href="{esc(url)}">{esc(label)}</a>' + (f'<br>{content_text}' if content_text else "")
        block_title = "" if block.get("title") and str(block.get("title")) == heading else f'<h3>{esc(block.get("title"))}</h3>'
        return f'<article class="block">{block_title}<div class="block-meta">{block_fields(block)}</div><p>{content_text}</p></article>'

    def stream_pages(section_ids: list[str], budget: int) -> list[list[tuple[dict, str]]]:
        """Fragment blocks, pack them into pages, and mark heading continuations."""
        items: list[tuple[str, dict, int]] = []
        for section_id in section_ids:
            section = sections.get(section_id, {})
            limit = section_fragment_limit(section_id)
            for block in section.get("blocks", []):
                text_value = str(block.get("content", "") or "")
                chunks = [text_value[index:index + limit] for index in range(0, len(text_value), limit)] or [""]
                for index, chunk in enumerate(chunks):
                    item = dict(block, content=chunk, fields=block.get("fields") if index == 0 else {}, display_fields=block.get("display_fields") if index == 0 else [])
                    weight = section_item_weight(section_id, chunk, len(item.get("fields") or {}))
                    items.append((section_id, item, weight))
        pages: list[list[tuple[str, dict, int]]] = []
        current: list[tuple[str, dict, int]] = []
        size = 0
        for item in items:
            weight = item[2]
            if current and size + weight > budget:
                pages.append(current)
                current, size = [], 0
            current.append(item)
            size += weight
        if current or not pages:
            pages.append(current)
        seen: set[str] = set()
        for page in pages:
            local: set[str] = set()
            for index, (section_id, _, _) in enumerate(page):
                page[index] = (section_id, page[index][1], 1 if section_id in seen else 0)
                local.add(section_id)
            seen.update(local)
        return pages

    def render_page(items: list[tuple[str, dict, int]]) -> str:
        parts: list[str] = []
        current_id: str | None = None
        current_heading = ""
        for section_id, block, continued in items:
            heading = next((section_title for section_title, section_key in SECTION_HEADINGS if section_key == section_id), section_id)
            if section_id != current_id:
                if current_id is not None:
                    parts.append("</section>")
                label = f"{heading}（续）" if continued else heading
                parts.append(f'<section class="section"><h2>{esc(label)}</h2>')
                current_id = section_id
                current_heading = heading
            parts.append(block_html(block, current_heading))
        if current_id is not None:
            parts.append("</section>")
        return "".join(parts)

    plain = descriptor["layout"] == "plain"
    banner = descriptor["layout"] == "banner"
    single_column = plain or banner
    side_ids = [] if single_column else ["basics", "skills", "awards"]
    if plain:
        main_ids = ["basics", "target", "profile", "experience", "education", "skills", "awards", "links"]
    elif banner:
        # The banner strip replaces the basics section on every page.
        main_ids = ["target", "profile", "experience", "education", "skills", "awards", "links"]
    else:
        main_ids = ["target", "profile", "experience", "education", "links"]
    sidebar_pages = [] if single_column else stream_pages(side_ids, SIDE_PAGE_BUDGET)
    main_pages = stream_pages(main_ids, BANNER_PAGE_BUDGET if banner else MAIN_PAGE_BUDGET)
    page_count = max(len(main_pages), 1)

    def sidebar_items(page_index: int) -> list[tuple[str, dict, int]]:
        return sidebar_pages[page_index] if page_index < len(sidebar_pages) else []

    basics = sections.get("basics", {}).get("blocks", [])
    basic_block = basics[0] if basics else {}
    sidebar_head = f'<h1>{esc(basic_block.get("title") if basics else title)}</h1><div class="side-meta">{block_fields(basic_block)}</div><p class="side-copy">{block_text(basic_block)}</p>'
    banner_name = esc(basic_block.get("title") if basics else title)
    banner_head = f'<header class="page-banner"><h1>{banner_name}</h1><div class="banner-meta">{block_fields(basic_block)}</div></header>'
    banner_head_slim = f'<header class="page-banner banner-slim"><h1>{banner_name}</h1></header>'

    chunks: list[str] = []
    for index in range(page_count):
        if banner:
            body = render_page(main_pages[index] if index < len(main_pages) else [])
            head = banner_head if index == 0 else banner_head_slim
            chunks.append(f'<section class="page page-banner-page">{head}<main class="main main-plain">{body}</main></section>')
        elif plain:
            body = render_page(main_pages[index] if index < len(main_pages) else [])
            chunks.append(f'<section class="page page-plain"><main class="main main-plain">{body}</main></section>')
        else:
            sidebar_html = sidebar_head + render_page(sidebar_items(index)) if index == 0 else render_page(sidebar_items(index))
            chunks.append(f'<section class="page"><aside class="sidebar">{sidebar_html}</aside><main class="main">{render_page(main_pages[index] if index < len(main_pages) else [])}</main></section>')
    d = descriptor
    serif_css = '.page,.page *{font-family:Georgia,"Times New Roman","Songti SC",SimSun,serif;}' if d.get("serif") else ""
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{esc(title)} v{version_number}</title>
<style>
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }}
html,body {{ margin:0; padding:0; background:#e9efeb; color:#24342f; font-family:Arial,"Microsoft YaHei",sans-serif; }}
body {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
{serif_css}
.page {{ width:210mm; height:297mm; margin:16px auto; display:grid; grid-template-columns:58mm 1fr; background:#fff; break-after:page; page-break-after:always; box-shadow:0 8px 25px #18302922; overflow:hidden; }}
.page-plain {{ grid-template-columns:1fr; }}
.page-banner-page {{ display:flex; flex-direction:column; }}
.page-banner {{ background:{d['sidebar_bg']}; color:{d['sidebar_fg']}; padding:11mm 12mm; flex:none; }}
.page-banner h1 {{ font-size:20pt; line-height:1.15; margin:0 0 3mm; letter-spacing:.5px; }}
.banner-meta {{ display:flex; flex-wrap:wrap; gap:1mm 4mm; color:{d['sidebar_muted']}; font-size:8pt; line-height:1.45; }}
.banner-meta .meta {{ display:block; }}
.banner-slim {{ padding:3.5mm 12mm; display:flex; align-items:baseline; }}
.banner-slim h1 {{ font-size:10pt; margin:0; letter-spacing:1px; }}
.page:last-child {{ break-after:auto; page-break-after:auto; }}
.sidebar {{ background:{d['sidebar_bg']}; color:{d['sidebar_fg']}; padding:14mm 7mm; overflow:hidden; }}
.sidebar h1 {{ font-family:Georgia,"Microsoft YaHei",serif; font-size:23pt; line-height:1.1; margin:0 0 5mm; }}
    .side-meta {{ display:grid; gap:1.5mm; color:{d['sidebar_muted']}; font-size:8pt; line-height:1.45; }}
    .side-meta .meta {{ display:block; }}
    .side-copy {{ white-space:pre-wrap; color:{d['sidebar_muted']}; font-size:9pt; line-height:1.6; }}
.sidebar .section {{ margin-top:9mm; }}
.sidebar .section h2 {{ border:0; color:{d['sidebar_heading']}; font-size:8pt; letter-spacing:1.4px; padding:0; margin:0 0 3mm; }}
.sidebar .block {{ margin-bottom:4mm; }}
.sidebar .block h3 {{ color:{d['sidebar_fg']}; font-size:8.5pt; margin:0 0 1mm; }}
.sidebar .block p {{ color:{d['sidebar_muted']}; font-size:8pt; line-height:1.45; margin:0; }}
.main {{ padding:14mm 12mm; overflow:hidden; }}
.main-plain {{ padding:13mm 14mm; }}
.page-banner-page .main {{ flex:1; padding-top:8mm; }}
.main > .section:first-child {{ margin-top:0; }}
.section {{ margin-top:7mm; break-inside:avoid; }}
.section h2 {{ border-bottom:1px solid {d['rule']}; color:{d['heading']}; font-size:12pt; margin:0 0 3mm; padding-bottom:2mm; }}
.block {{ margin:0 0 5mm; break-inside:avoid; }}
    .block h3 {{ color:{d['title']}; font-size:10.5pt; line-height:1.35; margin:0 0 1.5mm; }}
    .block-meta {{ display:flex; flex-wrap:wrap; gap:1mm 3mm; color:{d['meta']}; font-size:7.8pt; line-height:1.4; margin:0 0 1mm; }}
    .meta b {{ color:{d['meta_label']}; font-weight:600; }}
    .block p {{ color:{d['copy']}; font-size:9pt; line-height:1.6; margin:0; white-space:normal; }}
    .block a {{ color:{d['accent']}; }}
    .block ul {{ margin:1mm 0 0; padding-left:5mm; }}
    .block li {{ color:{d['copy']}; font-size:9pt; line-height:1.6; }}
    .block strong {{ color:{d['title']}; }}
@media print {{ html,body {{ background:#fff; }} .page {{ margin:0; box-shadow:none; }} }}
</style></head><body>{"".join(chunks)}</body></html>'''
