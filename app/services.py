from __future__ import annotations

import hashlib
import html
import json
import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .templates import BUILTIN_TEMPLATES  # registry lives in app/templates.py; re-exported for callers.
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


# 侧栏布局里由侧栏承载的栏目。基本信息不在此列——它已经由侧栏页头（姓名 +
# 联系方式 + 简介）呈现，重复成栏目会让同一段内容在侧栏出现两次。
SIDE_SECTION_IDS = ("skills", "awards")

# —— 分页权重模型（单位：px，96dpi 下的 A4 = 1123px 高）——
# 权重即估算的渲染高度，预算即版心可用高度。全部数值由
# `python scripts/calibrate_layout.py && node web/scripts/measure_calib.mjs` 从
# 真实导出 CSS 的浏览器布局中实测得出，并按“安全一侧”取整：行高与固定成本向上取，
# 每行字符数向下取。这样估算高度不会低于实际渲染高度——低估会让导出正文越过 A4
# 底边被 overflow:hidden 裁掉（此前的正文丢失就是这样来的）。
# 两端（app/services.py 与 web/src/lib/resume.ts）必须保持同一张表与同一预算。
#
# 衬线模板（academic/quill/regent）不需要单独一列：实测 Georgia/Times 对中文会落到
# SimSun，中文字宽不变，每行字符数与同布局的非衬线模板一致。
LAYOUT_METRICS = {
    # header 栏目标题行成本（页内非首个栏目，含栏目上边距）；header_first 页内首个
    # 栏目（上边距归零）；base 条目固定成本；extra 布局装饰；content_line 正文行高；
    # chars_per_line 每行容纳字符数；meta 元信息行高；meta_chars 每行元信息字符数；
    # pair_chars_per_line / pair_meta_chars 是并排（半宽）时的同一口径。
    "sidebar":  {"header": 57, "header_first": 37, "base": 46, "extra": 0, "content_line": 20, "chars_per_line": 46, "meta": 15, "meta_chars": 34, "pair_chars_per_line": 21, "pair_meta_chars": 22},
    "side":     {"header": 24, "header_first": 24, "base": 39, "extra": 0, "content_line": 16, "chars_per_line": 17, "meta": 15, "meta_chars": 14, "pair_chars_per_line": 17, "pair_meta_chars": 14},
    "plain":    {"header": 57, "header_first": 37, "base": 42, "extra": 0, "content_line": 20, "chars_per_line": 68, "meta": 15, "meta_chars": 70, "pair_chars_per_line": 31, "pair_meta_chars": 34},
    "banner":   {"header": 57, "header_first": 37, "base": 42, "extra": 0, "content_line": 20, "chars_per_line": 68, "meta": 15, "meta_chars": 70, "pair_chars_per_line": 31, "pair_meta_chars": 34},
    "grid":     {"header": 57, "header_first": 42, "base": 39, "extra": 0, "content_line": 20, "chars_per_line": 68, "meta": 15, "meta_chars": 70, "pair_chars_per_line": 33, "pair_meta_chars": 34},
    "line":     {"header": 55, "header_first": 35, "base": 54, "extra": 0, "content_line": 20, "chars_per_line": 68, "meta": 15, "meta_chars": 70, "pair_chars_per_line": 32, "pair_meta_chars": 34},
    "timeline": {"header": 57, "header_first": 37, "base": 44, "extra": 0, "content_line": 20, "chars_per_line": 58, "meta": 15, "meta_chars": 70, "pair_chars_per_line": 31, "pair_meta_chars": 34},
}
# 双栏收尾：短栏目两两并排（一行两个模块）。时间轴保持单列，左时间栏是它的
# 识别特征。配对只发生在**相邻**的两个栏目之间，以保持简历的栏目顺序；并且必须
# 真正省下纵向空间才配对——半宽折行会让正文变高，落差悬殊的栏目并排反而更费版面。
# PAIR_MAX_SHARE 把并排限制在“短栏目收尾”场景：并排单元至多占一页的约四成，
# 更长的栏目（项目与实践等主栏内容）保持整宽通排，既好读也不会被压成窄栏。
PAIRING_BY_LAYOUT = {"sidebar": True, "plain": True, "banner": True, "grid": True, "line": True, "timeline": False}
PAIR_MAX_SHARE = 0.4
PAIR_MIN_SAVING = 20
# 每页可用高度（px）= A4 高 − 页内首个栏目的页头 − 正文上下内边距，实测得出。
# 取首页（内容页头最高）口径，后续页的细页头只会更宽松，因此不会溢出。
# 这里按布局直接查表：此前用一串条件挑预算，plain 没有分支而落到了 sidebar 的
# 预算上，凭空多出近百像素，导出正文因此越过 A4 底边被裁掉。
PAGE_BUDGET_PX = {
    "sidebar": 1024, "side": 1032, "plain": 948, "banner": 906,
    "grid": 982, "line": 986, "timeline": 941,
}
MAIN_PAGE_BUDGET = PAGE_BUDGET_PX["sidebar"]
SIDE_PAGE_BUDGET = PAGE_BUDGET_PX["side"]
BANNER_PAGE_BUDGET = PAGE_BUDGET_PX["banner"]
GRID_PAGE_BUDGET = PAGE_BUDGET_PX["grid"]
LINE_PAGE_BUDGET = PAGE_BUDGET_PX["line"]
TIMELINE_PAGE_BUDGET = PAGE_BUDGET_PX["timeline"]
PLAIN_PAGE_BUDGET = PAGE_BUDGET_PX["plain"]
# 侧栏首页除了栏目，还要放侧栏页头（姓名 + 联系方式 + 简介），这部分高度必须从第一
# 页的侧栏预算里扣掉，否则侧栏首页会溢出 A4 底边被裁掉。页头高度按同一套度量推算
# （姓名行 + 每个联系字段一行 + 简介行数），字段多或简介长的简历也能算准。
SIDEBAR_NAME_PX = 50
SIDEBAR_FIELD_PX = 21
SIDEBAR_BIO_LINE_PX = 19
SIDEBAR_HEAD_BASE_PX = 24


def section_fragment_limit(in_sidebar: bool) -> int:
    """正文切片上限：侧栏版心只有约 44mm，切片要更短。"""
    return 520 if in_sidebar else 900


def sidebar_head_height(basic_block: dict, style: dict) -> int:
    """侧栏页头（姓名 + 联系方式 + 简介）的估算高度。"""
    fields = basic_block.get("fields") or {}
    displayed = basic_block.get("display_fields") or list(fields)
    rows = 0
    for key in displayed:
        value = fields.get(key)
        if not value:
            continue
        rows += max(1, -(-(len(str(FIELD_LABELS.get(key, ""))) + len(str(value))) // style["meta_chars"]))
    bio_lines = content_line_count(basic_block.get("content"), style["chars_per_line"])
    return SIDEBAR_HEAD_BASE_PX + SIDEBAR_NAME_PX + rows * SIDEBAR_FIELD_PX + bio_lines * SIDEBAR_BIO_LINE_PX


def content_line_count(content: str, chars_per_line: int) -> int:
    """正文行数：按 \\n 分段后逐段折行（markdown 子集的 <br> 会真实换行）。"""
    text = str(content or "")
    if not text:
        return 0
    return sum(max(1, -(-len(seg) // chars_per_line)) for seg in text.split("\n"))


def section_item_weight(content: str, meta_lines: int, style: dict) -> int:
    """条目高度(px) = 固定成本 + 正文行数 × 行高 + 元信息行数 × 行高 + 布局装饰。

    此前按“字段个数×固定值”计价，长字段值（到岗安排、核心要求等）折行后的高度
    被低估，导致导出内容溢出 A4 底边。
    """
    return style["base"] + style["extra"] + content_line_count(content, style["chars_per_line"]) * style["content_line"] + meta_lines * style["meta"]


def meta_field_lines(block: dict, side: bool, chars_per_line: int) -> int:
    fields = block.get("fields") or {}
    displayed = block.get("display_fields") or list(fields)
    if side:
        return sum(max(1, -(-(len(str(FIELD_LABELS.get(key, "")) + str(fields.get(key, "")))) // chars_per_line)) for key in displayed if fields.get(key))
    total = sum(len(str(FIELD_LABELS.get(key, "")) + str(fields.get(key, ""))) for key in displayed if fields.get(key))
    return max(1, -(-total // chars_per_line)) if displayed else 0


FIELD_LABELS = {
    "phone": "电话", "email": "邮箱", "city": "所在地", "desired_city": "目标城市", "hometown": "籍贯",
    "status": "身份状态", "graduation": "毕业时间", "availability": "到岗安排", "bio": "个人简介",
    "period": "时间", "major": "专业", "degree": "学历", "gpa": "GPA", "ranking": "专业排名",
    "organization": "组织/公司", "role": "角色", "team_size": "团队规模", "tools": "工具与技术",
    "skill_category": "技能分类", "proficiency": "熟练程度", "issuer": "颁发方", "result": "结果",
    "link_type": "链接类型", "url": "地址", "label": "显示名称", "role_direction": "岗位方向",
    "core_requirements": "核心要求", "summary": "简介", "name": "姓名", "birth_date": "出生日期",
    "age": "年龄", "start_date": "入学时间", "end_date": "毕业时间",
}



def _page_style(layout_id: str, in_sidebar: bool) -> dict:
    """侧栏列（约 44mm 版心）与主栏列的度量口径完全不同，按列取用。"""
    return LAYOUT_METRICS["side" if in_sidebar else layout_id]


def fragment_flow(sections: dict, sid: str, blocks: list[dict], layout_id: str, in_sidebar: bool) -> list[dict]:
    """把一个栏目的条目切成 flow 单元（超长正文按 section_fragment_limit 切片）。"""
    style = _page_style(layout_id, in_sidebar)
    limit = section_fragment_limit(in_sidebar)
    out = []
    if not blocks:
        # 空栏目保留标题行（选择/添加来源的点击入口）。
        empty = {"id": f"{sid}--empty", "title": "", "content": "", "fields": {}, "display_fields": [], "source_refs": [], "origin": "empty"}
        out.append({"kind": "flow", "sid": sid, "item": empty, "weight": style["base"]})
        return out
    for block in blocks:
        text_value = str(block.get("content", "") or "")
        chunks = [text_value[index:index + limit] for index in range(0, len(text_value), limit)] or [""]
        for index, chunk in enumerate(chunks):
            item = dict(block, content=chunk, fields=block.get("fields") if index == 0 else {}, display_fields=block.get("display_fields") if index == 0 else [])
            meta_lines = meta_field_lines(item, in_sidebar, style["meta_chars"])
            out.append({"kind": "flow", "sid": sid, "item": item, "weight": section_item_weight(chunk, meta_lines, style)})
    return out


def column_height(sections: dict, sid: str, layout_id: str, in_sidebar: bool,
                  chars_per_line: int, meta_chars: int) -> int:
    """整栏估算高度：栏目标题行 + 各条目（固定成本 + 正文行 + 元信息行）。"""
    style = _page_style(layout_id, in_sidebar)
    blocks = sections.get(sid, {}).get("blocks", [])
    total = style["header"]
    if not blocks:
        return total + style["base"]
    for block in blocks:
        total += style["base"] + style["extra"] + content_line_count(block.get("content"), chars_per_line) * style["content_line"] + meta_field_lines(block, False, meta_chars) * style["meta"]
    return total


def pair_height(sections: dict, layout_id: str, sid: str, sid2: str, budget: int) -> int | None:
    """相邻两栏并排的估算高度；不值得配对时返回 None（保持整宽通排）。

    并排高度取两栏较大者；只有并排明显矮于顺排（PAIR_MIN_SAVING）才配对，否则
    半宽折行会让正文变高、配对反而更费版面。
    """
    style = LAYOUT_METRICS[layout_id]
    stacked = column_height(sections, sid, layout_id, False, style["chars_per_line"], style["meta_chars"]) + \
        column_height(sections, sid2, layout_id, False, style["chars_per_line"], style["meta_chars"])
    paired = max(
        column_height(sections, sid, layout_id, False, style["pair_chars_per_line"], style["pair_meta_chars"]),
        column_height(sections, sid2, layout_id, False, style["pair_chars_per_line"], style["pair_meta_chars"]),
    )
    if paired > budget * PAIR_MAX_SHARE or stacked - paired < PAIR_MIN_SAVING:
        return None
    return paired


def paginate(sections: dict, section_ids: list[str], layout_id: str, budget: int,
             in_sidebar: bool = False, pairable: bool = False,
             first_page_head: int = 0) -> list[list[dict]]:
    """把栏目切成页面单元并分页。

    单元有两种：
    - ``flow``：某个栏目的一个条目（栏目标题行按页计一次，超长正文按
      section_fragment_limit 切片成多个条目）；
    - ``pair``：**相邻**两个短栏目并排成一行两个模块（仅该布局允许配对时）。

    配对以栏目顺序为准，只并排相邻栏目，因此不会打乱简历的栏目次序；并且只在
    真正省下纵向空间时成立。pair 是原子单元，放不下当前页剩余空间时会在打包阶段
    退化回两个 flow 单元，避免为等一整对而空出大半页、形成只有一两行的尾页。

    ``in_sidebar`` 决定用哪一列的口径计价。``first_page_head`` 是首页额外的固定
    占用（侧栏页头），只从第一页扣。
    """
    def blocks_of(sid: str) -> list[dict]:
        return sections.get(sid, {}).get("blocks", [])

    units: list[dict] = []
    index = 0
    while index < len(section_ids):
        sid = section_ids[index]
        if pairable and index + 1 < len(section_ids):
            sid2 = section_ids[index + 1]
            weight = pair_height(sections, layout_id, sid, sid2, budget)
            if weight is not None:
                units.append({"kind": "pair", "sid": sid, "blocks": blocks_of(sid), "sid2": sid2, "blocks2": blocks_of(sid2), "weight": weight})
                index += 2
                continue
        units.extend(fragment_flow(sections, sid, blocks_of(sid), layout_id, in_sidebar))
        index += 1

    pages: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    current_id: str | None = None
    cursor = 0

    def page_budget() -> int:
        """当前页的可用高度：首页要额外让出固定的页头占用。"""
        return budget - (first_page_head if not pages else 0)

    while cursor < len(units):
        unit = units[cursor]
        if unit["kind"] == "pair":
            if not current or size + unit["weight"] <= page_budget():
                current.append(unit)
                size += unit["weight"]
                cursor += 1
                continue
            # 放不下当前页剩余的这一点空间：退化成两个整宽栏目接着排，把本页填满，
            # 只把真正放不下的条目推到下一页。否则会为等一整对而空出大半页。
            units[cursor:cursor + 1] = fragment_flow(sections, unit["sid"], unit["blocks"], layout_id, in_sidebar) + \
                fragment_flow(sections, unit["sid2"], unit["blocks2"], layout_id, in_sidebar)
            continue
        sid = unit["sid"]
        style = _page_style(layout_id, in_sidebar)
        header = style["header"] if sid != current_id else 0
        if current and size + unit["weight"] + header > page_budget():
            pages.append(current)
            current, size, current_id = [], 0, None
            header = style["header_first"]
        if header:
            size += header
            current_id = sid
        unit["continued"] = 0
        current.append(unit)
        size += unit["weight"]
        cursor += 1
    if current or not pages:
        pages.append(current)
    seen: set[str] = set()
    for page in pages:
        local: set[str] = set()
        for unit in page:
            if unit["kind"] == "flow":
                unit["continued"] = 1 if unit["sid"] in seen else 0
                local.add(unit["sid"])
        seen.update(local)
    return pages

def render_resume_html(content: dict, title: str, version_number: int, template_slug: str = "classic") -> str:
    """Render a self-contained, print-ready HTML snapshot from a saved version.

    Blocks are fragmented and packed with the same weights as the SPA preview
    (see ``web/src/lib/resume.ts``) so page breaks match between preview and
    export. Each page repeats a section heading at most once; a heading that
    continues from an earlier page is suffixed with “（续）”.
    """
    descriptor = BUILTIN_TEMPLATES.get(template_slug) or BUILTIN_TEMPLATES["classic"]
    sections = {item.get("id"): item for item in content.get("sections", [])}
    field_labels = FIELD_LABELS

    def esc(value) -> str:
        return html.escape(str(value or ""), quote=True)

    def block_text(block: dict) -> str:
        return render_markdown(block.get("content", ""))

    def block_fields(block: dict, exclude: tuple = ()) -> str:
        fields = block.get("fields") or {}
        displayed = block.get("display_fields") or list(fields)
        labels = {**field_labels, **(block.get("field_labels") or {})}
        return "".join(f'<span class="meta"><b>{esc(labels.get(key, key))}</b> {esc(fields.get(key))}</span>' for key in displayed if fields.get(key) and key not in exclude)

    def block_period(block: dict) -> str:
        """条目的时间字段值；仅当时间属于展示字段时才返回（用于线式/时间轴布局）。"""
        fields = block.get("fields") or {}
        displayed = block.get("display_fields") or list(fields)
        value = str(fields.get("period") or "")
        return value if value and "period" in displayed else ""

    def block_html(block: dict, heading: str = "") -> str:
        """条目：时间右对齐到标题行行尾（时间轴布局除外，其时间在左栏）。"""
        content_text = block_text(block)
        if (block.get("fields") or {}).get("url"):
            url = str(block["fields"]["url"])
            label = (block.get("fields") or {}).get("label") or url
            content_text = f'<a href="{esc(url)}">{esc(label)}</a>' + (f'<br>{content_text}' if content_text else "")
        block_title = "" if block.get("title") and str(block.get("title")) == heading else f'<h3>{esc(block.get("title"))}</h3>'
        period = block_period(block)
        row = ""
        if block_title or period:
            row = f'<div class="entry-row">{block_title}' + (f'<span class="entry-period">{esc(period)}</span>' if period else "") + "</div>"
        return f'<article class="block">{row}<div class="block-meta">{block_fields(block, ("period",))}</div><p>{content_text}</p></article>'

    def timeline_block_html(block: dict) -> str:
        """时间轴：左侧时间栏 + 中线圆点，正文收在右侧时间轴体内。"""
        content_text = block_text(block)
        if (block.get("fields") or {}).get("url"):
            url = str(block["fields"]["url"])
            label = (block.get("fields") or {}).get("label") or url
            content_text = f'<a href="{esc(url)}">{esc(label)}</a>' + (f'<br>{content_text}' if content_text else "")
        body = f'<h3>{esc(block.get("title"))}</h3><div class="block-meta">{block_fields(block, ("period",))}</div><p>{content_text}</p>'
        return f'<article class="block"><span class="t-time">{esc(block_period(block))}</span><div class="t-body">{body}</div></article>'

    def render_flow(items: list[dict]) -> str:
        parts: list[str] = []
        current_id: str | None = None
        current_heading = ""
        for unit in items:
            section_id = unit["sid"]
            block = unit["item"]
            heading = next((section_title for section_title, section_key in SECTION_HEADINGS if section_key == section_id), section_id)
            if section_id != current_id:
                if current_id is not None:
                    parts.append("</section>")
                label = f"{heading}（续）" if unit["continued"] else heading
                parts.append(f'<section class="section"><h2>{esc(label)}</h2>')
                current_id = section_id
                current_heading = heading
            if layout_id == "timeline":
                parts.append(timeline_block_html(block))
            else:
                parts.append(block_html(block, current_heading))
        if current_id is not None:
            parts.append("</section>")
        return "".join(parts)

    def render_units(page_units: list[dict]) -> str:
        parts: list[str] = []
        flow: list[dict] = []

        def flush_flow():
            nonlocal flow
            if flow:
                parts.append(render_flow(flow))
                flow = []

        def heading_of(section_id: str) -> str:
            return next((section_title for section_title, section_key in SECTION_HEADINGS if section_key == section_id), section_id)

        for unit in page_units:
            if unit["kind"] == "pair":
                flush_flow()
                def col(sid: str, blocks: list[dict]) -> str:
                    head = heading_of(sid)
                    inner = "".join(block_html(block, head) for block in blocks)
                    return f'<section class="section"><h2>{esc(head)}</h2>{inner}</section>'
                parts.append(f'<div class="pair">{col(unit["sid"], unit["blocks"])}{col(unit["sid2"], unit["blocks2"])}</div>')
            else:
                flow.append(unit)
        flush_flow()
        return "".join(parts)

    plain = descriptor["layout"] == "plain"
    banner = descriptor["layout"] == "banner"
    grid = descriptor["layout"] == "grid"
    line = descriptor["layout"] == "line"
    timeline = descriptor["layout"] == "timeline"
    layout_id = descriptor["layout"]
    # 页头布局：姓名与联系方式由页头呈现，正文不再重复基本信息栏目。
    # 侧栏布局的基本信息在侧栏；其余五种布局都有页头。
    head_layout = layout_id != "sidebar"
    if head_layout:
        main_ids = ["target", "profile", "experience", "education", "skills", "awards", "links"]
    else:
        # 侧栏布局：技能与成果只出现在侧栏，主栏保持五个栏目。
        main_ids = ["target", "profile", "experience", "education", "links"]
    # 侧栏布局：基本信息由侧栏页头（姓名 + 联系方式 + 简介）呈现，不再重复成栏目；
    # 技能与成果在侧栏，主栏承载其余五栏。侧栏首页还要放页头，先按同一套度量扣掉
    # 它的高度，否则侧栏首页会把内容裁在 A4 底边之外。
    basics = sections.get("basics", {}).get("blocks", [])
    basic_block = basics[0] if basics else {}
    side_ids = [] if head_layout else list(SIDE_SECTION_IDS)
    sidebar_pages = [] if not side_ids else paginate(
        sections, side_ids, layout_id, SIDE_PAGE_BUDGET, in_sidebar=True,
        first_page_head=sidebar_head_height(basic_block, LAYOUT_METRICS["side"]),
    )
    budget = PAGE_BUDGET_PX[layout_id]
    main_pages = paginate(sections, main_ids, layout_id, budget, pairable=PAIRING_BY_LAYOUT.get(layout_id, False))
    page_count = max(len(main_pages), 1)

    def sidebar_items(page_index: int) -> list[tuple[str, dict, int]]:
        return sidebar_pages[page_index] if page_index < len(sidebar_pages) else []

    sidebar_head = f'<h1>{esc(basic_block.get("title") if basics else title)}</h1><div class="side-meta">{block_fields(basic_block)}</div><p class="side-copy">{block_text(basic_block)}</p>'
    head_name = esc(basic_block.get("title") if basics else title)
    head_fields = block_fields(basic_block)
    banner_head = f'<header class="page-banner"><h1>{head_name}</h1><div class="banner-meta">{head_fields}</div></header>'
    banner_head_slim = f'<header class="page-banner banner-slim"><h1>{head_name}</h1></header>'
    grid_head = f'<header class="grid-head"><h1>{head_name}</h1><div class="grid-meta">{head_fields}</div></header>'
    grid_head_slim = f'<header class="grid-head grid-head-slim"><h1>{head_name}</h1></header>'
    line_head = f'<header class="line-head"><h1>{head_name}</h1><div class="line-meta">{head_fields}</div></header>'
    line_head_slim = f'<header class="line-head line-head-slim"><h1>{head_name}</h1></header>'

    chunks: list[str] = []
    for index in range(page_count):
        body = render_units(main_pages[index] if index < len(main_pages) else [])
        if banner:
            head = banner_head if index == 0 else banner_head_slim
            chunks.append(f'<section class="page page-banner-page">{head}<main class="main main-plain">{body}</main></section>')
        elif grid:
            head = grid_head if index == 0 else grid_head_slim
            chunks.append(f'<section class="page page-grid">{head}<main class="main main-plain main-grid">{body}</main></section>')
        elif line:
            head = line_head if index == 0 else line_head_slim
            chunks.append(f'<section class="page page-line">{head}<main class="main main-plain main-line">{body}</main></section>')
        elif timeline:
            # 时间轴与 plain 共用紧凑页头（姓名 + 联系方式），正文沿用时间轴节点。
            head = line_head if index == 0 else line_head_slim
            chunks.append(f'<section class="page page-timeline">{head}<main class="main main-plain main-timeline">{body}</main></section>')
        elif plain:
            head = line_head if index == 0 else line_head_slim
            chunks.append(f'<section class="page page-plain">{head}<main class="main main-plain">{body}</main></section>')
        else:
            sidebar_html = sidebar_head + render_units(sidebar_items(index)) if index == 0 else render_units(sidebar_items(index))
            chunks.append(f'<section class="page"><aside class="sidebar">{sidebar_html}</aside><main class="main">{body}</main></section>')
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
.sidebar {{ background:{d['sidebar_bg']}; color:{d['sidebar_fg']}; padding:12mm 7mm; overflow:hidden; }}
.sidebar h1 {{ font-family:Georgia,"Microsoft YaHei",serif; font-size:23pt; line-height:1.1; margin:0 0 4mm; }}
    .side-meta {{ display:grid; gap:1.2mm; color:{d['sidebar_muted']}; font-size:8pt; line-height:1.35; }}
    .side-meta .meta {{ display:block; }}
    .side-copy {{ white-space:pre-wrap; color:{d['sidebar_muted']}; font-size:9pt; line-height:1.5; }}
.sidebar .section {{ margin-top:6.5mm; }}
.sidebar .section h2 {{ border:0; color:{d['sidebar_heading']}; font-size:8pt; letter-spacing:1.4px; padding:0; margin:0 0 2.5mm; }}
.sidebar .block {{ margin-bottom:3mm; }}
.sidebar .block h3 {{ color:{d['sidebar_fg']}; font-size:8.5pt; margin:0 0 1mm; }}
.sidebar .block p {{ color:{d['sidebar_muted']}; font-size:8pt; line-height:1.45; margin:0; }}
.main {{ padding:13mm 12mm; overflow:hidden; }}
.main-plain {{ padding:12mm 14mm; }}
.page-banner-page .main {{ flex:1; padding-top:8mm; }}
.main > .section:first-child {{ margin-top:0; }}
.main > .pair:first-child {{ margin-top:0; }}
.section {{ margin-top:5.5mm; break-inside:avoid; }}
.pair {{ margin-top:5.5mm; display:grid; grid-template-columns:1fr 1fr; gap:0 6mm; break-inside:avoid; align-items:start; }}
.pair .section {{ margin-top:0; }}
.pair + .pair {{ margin-top:4mm; }}
.section h2 {{ border-bottom:1px solid {d['rule']}; color:{d['heading']}; font-size:12pt; margin:0 0 2.2mm; padding-bottom:1.6mm; }}
.block {{ margin:0 0 4mm; break-inside:avoid; }}
    .block h3 {{ color:{d['title']}; font-size:10.5pt; line-height:1.35; margin:0 0 1.5mm; }}
    .block-meta {{ display:flex; flex-wrap:wrap; gap:1mm 3mm; color:{d['meta']}; font-size:7.8pt; line-height:1.4; margin:0 0 1mm; }}
    .meta b {{ color:{d['meta_label']}; font-weight:600; }}
    /* 彩色底（侧栏/横幅）上的 meta 标签跟随底色用浅色，与 SPA 预览的继承行为一致。 */
    .sidebar .meta b {{ color:{d['sidebar_muted']}; }}
    .banner-meta .meta b {{ color:{d['sidebar_muted']}; }}
    .block p {{ color:{d['copy']}; font-size:9pt; line-height:1.6; margin:0; white-space:normal; }}
    .block a {{ color:{d['accent']}; }}
    .block ul {{ margin:1mm 0 0; padding-left:5mm; }}
    .block li {{ color:{d['copy']}; font-size:9pt; line-height:1.6; }}
    .block strong {{ color:{d['title']}; }}
/* —— 表格表单版式（grid）：表头 + 带边框栏目，栏目标题为实底表头行 —— */
.page-grid {{ display:flex; flex-direction:column; }}
.grid-head {{ flex:none; border:1px solid {d['rule']}; padding:4.5mm 5mm 4mm; text-align:center; }}
.grid-head h1 {{ font-size:16pt; letter-spacing:2px; margin:0 0 2.5mm; color:{d['title']}; }}
.grid-meta {{ display:flex; flex-wrap:wrap; justify-content:center; gap:1mm 4mm; color:{d['meta']}; font-size:8pt; line-height:1.45; }}
.grid-meta .meta {{ display:block; }}
.grid-meta .meta b {{ color:{d['meta_label']}; font-weight:600; }}
.grid-head.grid-head-slim {{ padding:2.2mm 5mm; border-bottom:1px solid {d['rule']}; }}
.grid-head.grid-head-slim h1 {{ font-size:9.5pt; margin:0; letter-spacing:1px; }}
.main-grid {{ flex:1; padding:5mm 10mm 9mm; }}
.main-grid .pair {{ margin-top:4mm; }}
.main-grid .pair + .pair {{ margin-top:4mm; }}
.main-grid .pair .section {{ margin-top:0; }}
.main-grid .section {{ border:1px solid {d['rule']}; margin-top:4mm; overflow:hidden; }}
.main-grid .section h2 {{ background:{d['sidebar_bg']}; color:{d['sidebar_fg']}; border:0; padding:1.8mm 3mm; margin:0; font-size:10pt; letter-spacing:1.2px; }}
.main-grid .block {{ margin:0 3mm 3mm; }}
.main-grid .section .block:first-of-type {{ margin-top:2.4mm; }}
.main-grid .block:last-of-type {{ margin-bottom:2.6mm; }}
/* —— 经典线式版式（line）：居中页头，栏目居中标题，条目时间右对齐 —— */
.page-line {{ display:flex; flex-direction:column; }}
.line-head {{ flex:none; text-align:center; padding:3mm 8mm 4.5mm; border-bottom:2px solid {d['sidebar_bg']}; }}
.line-head h1 {{ font-size:17pt; letter-spacing:1.5px; margin:0 0 2mm; color:{d['title']}; }}
.line-meta {{ display:flex; flex-wrap:wrap; justify-content:center; gap:1mm 4mm; color:{d['meta']}; font-size:8pt; line-height:1.45; }}
.line-meta .meta {{ display:block; }}
.line-meta .meta b {{ color:{d['meta_label']}; font-weight:600; }}
.line-head.line-head-slim {{ padding:2.2mm 8mm; border-bottom:1px solid {d['rule']}; }}
.line-head.line-head-slim h1 {{ font-size:9.5pt; margin:0; letter-spacing:1px; }}
.main-line {{ flex:1; padding:5mm 12mm 9mm; }}
.main-line .section h2 {{ text-align:center; letter-spacing:2.5px; font-size:10.5pt; }}
/* 条目标题行：标题居左、时间右对齐同一行（所有非时间轴布局共用）。 */
.entry-row {{ display:flex; justify-content:space-between; align-items:baseline; gap:3mm; margin:0 0 1mm; }}
.entry-row h3 {{ margin:0; }}
.entry-period {{ color:{d['accent']}; font-weight:600; font-size:8.5pt; white-space:nowrap; }}
.main-line .block:not(:last-child) {{ border-bottom:1px solid {d['rule']}; padding-bottom:2.8mm; }}
/* —— 时间轴版式（timeline）：左侧时间栏 + 中线圆点 —— */
.page-timeline {{ grid-template-columns:1fr; }}
.main-timeline {{ padding:13mm 14mm; }}
.main-timeline .block {{ display:grid; grid-template-columns:18mm 3mm 1fr; }}
.main-timeline .t-time {{ grid-column:1; color:{d['accent']}; font-size:7.6pt; font-weight:600; line-height:1.45; padding-top:.4mm; overflow-wrap:anywhere; }}
.main-timeline .block::before {{ content:''; grid-column:2; grid-row:1; width:1px; justify-self:center; background:{d['rule']}; }}
.main-timeline .block::after {{ content:''; grid-column:2; grid-row:1; width:2mm; height:2mm; border-radius:50%; background:{d['accent']}; justify-self:center; margin-top:1.2mm; box-shadow:0 0 0 .7mm #fff; }}
.main-timeline .t-body {{ grid-column:3; min-width:0; }}
.main-timeline .t-body h3 {{ margin:0 0 1.5mm; }}
@media print {{ html,body {{ background:#fff; }} .page {{ margin:0; box-shadow:none; }} }}
</style></head><body>{"".join(chunks)}</body></html>'''
