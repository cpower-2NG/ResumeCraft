from __future__ import annotations

import hashlib
import html
import json
import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .templates import BUILTIN_TEMPLATES, descriptor_for  # registry lives in app/templates.py; re-exported for callers.
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
# 栏目 -> 标题，供分页估算判断条目是否还需要渲染自己的标题行。
SECTION_TITLES = {key: title for key, title in CORE_SECTIONS}

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def render_markdown(text: str) -> str:
    """Escape, then apply the controlled subset: bold, italic, links, unordered lists.

    Lines are rejoined with <br> so the author's line breaks survive: the split
    above is only there to group "- " runs into <ul>. Joining with "" instead
    glued every line together ("9/153具身智能系统概论…"), which both mis-rendered
    the export and disagreed with the SPA preview, whose mdLite keeps the breaks.
    """
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
    return "<br>".join(rendered)

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
        plain = curated_education_plain(details)
    elif section_id == "experience":
        display_fields = [key for key in ("period", "organization", "role", "team_size", "tools") if details.get(key)]
        plain = curated_experience_plain(details)
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
    # units_per_line 每行容纳的字宽单位数（全角记 2）；meta 元信息行高；
    # meta_units 每行元信息字宽单位数；
    # title 条目标题行成本（标题与栏目标题同名时不渲染，需从 base 里扣掉）；
    # pair_units_per_line / pair_meta_units 是并排（半宽）时的同一口径。
    # 每行容量按**字宽单位**实测（全角记 2，见 text_units）：中文正文与带拉丁词的
    # 正文用同一套常数都算得准（按字数标定时，拉丁密集的探针会量出偏大的每行容量，
    # 中文正文因此被少算行数、顶出 A4 底边）。取值一律向下取整，宁可多留白也不裁字。
    # 全表由 scripts/calibrate_layout.py + web/scripts/measure_calib.mjs 在收紧后的
    # 导出 CSS 上实测回填（9pt 正文、行距 1.4、栏目距 3.2mm、条目距 2mm）。
    "sidebar": {"header": 48, "header_first": 35, "title": 21, "base": 37, "extra": 0, "content_line": 17, "units_per_line": 75, "meta": 15, "meta_units": 53, "pair_units_per_line": 37, "pair_meta_units": 42},
    "side":    {"header": 26, "header_first": 26, "title": 21, "base": 34, "extra": 0, "content_line": 15, "units_per_line": 28, "meta": 15, "meta_units": 15, "pair_units_per_line": 28, "pair_meta_units": 15},
    "plain":   {"header": 48, "header_first": 35, "title": 21, "base": 34, "extra": 0, "content_line": 17, "units_per_line": 112, "meta": 15, "meta_units": 71, "pair_units_per_line": 54, "pair_meta_units": 42},
    "banner":  {"header": 48, "header_first": 35, "title": 21, "base": 34, "extra": 0, "content_line": 17, "units_per_line": 112, "meta": 15, "meta_units": 71, "pair_units_per_line": 54, "pair_meta_units": 42},
    "grid":    {"header": 46, "header_first": 36, "title": 21, "base": 34, "extra": 0, "content_line": 17, "units_per_line": 112, "meta": 15, "meta_units": 71, "pair_units_per_line": 56, "pair_meta_units": 42},
    "line":    {"header": 42, "header_first": 29, "title": 21, "base": 40, "extra": 0, "content_line": 17, "units_per_line": 112, "meta": 15, "meta_units": 71, "pair_units_per_line": 54, "pair_meta_units": 42},
    "timeline": {"header": 48, "header_first": 35, "title": 24, "base": 37, "extra": 0, "content_line": 17, "units_per_line": 98, "meta": 15, "meta_units": 71, "pair_units_per_line": 54, "pair_meta_units": 42},
    # 标签栏版式：左侧栏目标签列（24mm）+ 右侧内容；栏目标题绝对定位不占行高，
    # header 只计栏目间距，header_first 为 0。
    "rail":    {"header": 13, "header_first": 0, "title": 21, "base": 34, "extra": 0, "content_line": 17, "units_per_line": 100, "meta": 15, "meta_units": 71, "pair_units_per_line": 54, "pair_meta_units": 42},
}
# 双栏收尾：短栏目两两并排（一行两个模块）**只作为例外**，整宽通排才是默认版式。
#
# 早先只按"并排确实省版面"决定配对，结果是密集内容下每一行都是两栏：12 套模板里
# 单栏/横幅/表格/线式四种版式全变成同一张两列表格，版式之间没有区别，主经历栏目
# （项目与实践）也被压成半宽。现在按布局给"每页最多并排几行"的额度：
# - 侧栏布局一页已经是两列（58mm 侧栏 + 主栏），主栏再并排就成三列，额度 0；
# - 时间轴的左时间栏是它的识别特征，额度 0；
# - 单栏/横幅/线式只在页首把求职目标与个人简介并排一行（简历头部的经典做法），额度 1；
# - 表格表单版式本身就是表格语汇，额度 2。
# 额度之外，配对仍要求两栏相邻、并排确实省版面、且不超过半栏高度上限。
PAIR_BUDGET_BY_LAYOUT = {"sidebar": 0, "side": 0, "plain": 0, "banner": 0, "grid": 3, "line": 0, "timeline": 0, "rail": 0}
# 并排上限 = 页预算 × PAIR_MAX_SHARE，再按半栏宽度等比收紧（PAIR_REF_CHARS 为最宽的
# 半栏口径）：半栏越窄，能并排的单元就该越矮。这个上限决定"哪些栏目够短、值得并排"，
# 是配对的**必要性**判据；每页并排几行由上面的额度决定，是**节奏**判据。两者要分开：
# 收紧上限会把本来省版面的配对推掉（真实简历因此多出一页），只会让版面变松。
PAIR_MAX_SHARE = 0.4
PAIR_REF_CHARS = 33
PAIR_MIN_SAVING = 20
# 两栏高度要相当才并排：短栏至少要达到高栏的一半。否则并排后短栏底下空出一大块
# （求职目标 + 项目与实践 就是这种：一行的栏目配上一整段主经历），而且会把主经历
# 压成半宽。用相对比例而不是绝对像素：像素阈值会连带推掉高度相当的好配对，真实
# 简历因此多出一页（试过 72px，已回退）。
PAIR_MIN_BALANCE = 0.35


def pair_budget_for(layout_id: str) -> int:
    """该版式每页允许并排的行数（0 = 整宽通排）。"""
    return PAIR_BUDGET_BY_LAYOUT.get(layout_id, 0)


def pair_height_cap(layout_id: str, budget: int) -> int:
    """当前布局允许的并排单元高度上限（半栏越窄上限越低）。"""
    style = LAYOUT_METRICS[layout_id]
    return min(style["pair_units_per_line"] / PAIR_REF_CHARS, 1.0) * budget * PAIR_MAX_SHARE
# 每页可用高度（px）= A4 高 − 页内首个栏目的页头 − 正文上下内边距，实测得出。
# 取首页（内容页头最高）口径，后续页的细页头只会更宽松，因此不会溢出。
# 这里按布局直接查表：此前用一串条件挑预算，plain 没有分支而落到了 sidebar 的
# 预算上，凭空多出近百像素，导出正文因此越过 A4 底边被裁掉。
PAGE_BUDGET_PX = {
    "sidebar": 1047, "side": 1045, "plain": 980, "banner": 948,
    "grid": 1008, "line": 1016, "timeline": 980, "rail": 1087,
}
# —— 紧凑档（auto-compact）——
# 内容估算高度超过一页、但不超过一页的 8% 时，与其把最后一两个条目整段推到几乎
# 空白的第二页，不如整页换紧凑刻度重排（行距/间距收紧，见导出 CSS 的 .page.compact
# 与预览样式表的同名规则）。紧凑 CSS 的实测收缩比 ≈ 0.91 ≤ 1/TRIGGER（≈ 0.926），
# 触发紧凑档的内容装回一页后不会越过 A4 底边。BUDGET_FACTOR 是重排时的估算预算
# 放大系数（≥ TRIGGER 即可，给打包留余量）。决策在两端（app/services.py 与
# web/src/lib/resume.ts）用同一算法镜像，收缩比用 web/scripts/measure_parts.mjs 复测。
COMPACT_TRIGGER = 1.08
COMPACT_BUDGET_FACTOR = 1.15
# —— 求职意向横带 ——
# 求职目标不再是独立栏目（栏目标题条 + 一行字太费版面），改为页头下的一条横带。
# 高度 = 底座 + 正文行数 × 行高，与紧凑档无关（横带随 compact 一起略收紧，按不收紧
# 估算偏安全）。INTENT_BAND_BASE_PX 由 web/scripts/measure_parts.mjs 实测回填。
INTENT_BAND_BASE_PX = 40
INTENT_BAND_LINE_PX = 18
# 技能分组行间距 / 成果表格装饰行高（px），web/scripts/measure_parts.mjs 实测回填。
GROUP_GAP_PX = 8
AWARDS_HEADER_PX = 25
AWARDS_ROW_PX = 27
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
SIDEBAR_NAME_PX = 51
SIDEBAR_FIELD_PX = 19
SIDEBAR_BIO_LINE_PX = 18
SIDEBAR_HEAD_BASE_PX = 20


def section_fragment_limit(in_sidebar: bool) -> int:
    """正文切片上限：侧栏版心只有约 44mm，切片要更短。"""
    return 520 if in_sidebar else 900


def sidebar_head_height(basic_block: dict, style: dict) -> int:
    """侧栏页头（姓名 + 联系方式 + 简介）的估算高度。"""
    rows = 0
    for value in meta_values(basic_block):
        rows += max(1, -(-text_units(value) // style["meta_units"]))
    bio_lines = content_line_count(basic_block.get("content"), style["units_per_line"])
    return SIDEBAR_HEAD_BASE_PX + SIDEBAR_NAME_PX + rows * SIDEBAR_FIELD_PX + bio_lines * SIDEBAR_BIO_LINE_PX


def text_units(text: str) -> int:
    """文本的"字宽单位"数：全角字符记 2，其余记 1。

    估算按字宽而不是字数折行，因为中文字宽约为拉丁字母的两倍。早先按字数折行时，
    用拉丁字母较多的文本标定出的每行字数（~69）对纯中文正文偏乐观，估算少算近三成
    行数，正文被顶出 A4 底边裁掉；改用纯中文标定又会把带拉丁词的真实简历估高一截
    （非末页只剩七成满）。按字宽计数后两种文本用同一套常数都算得准。
    """
    units = 0
    for char in text:
        code = ord(char)
        wide = (
            0x1100 <= code <= 0x115F or 0x2E80 <= code <= 0x303E or 0x3041 <= code <= 0x33FF
            or 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF or 0xA000 <= code <= 0xA4CF
            or 0xAC00 <= code <= 0xD7A3 or 0xF900 <= code <= 0xFAFF or 0xFE30 <= code <= 0xFE6F
            or 0xFF00 <= code <= 0xFF60 or 0xFFE0 <= code <= 0xFFE6 or 0x20000 <= code <= 0x3FFFD
        )
        units += 2 if wide else 1
    return units


def content_line_count(content: str, units_per_line: int) -> int:
    """正文行数：按 \\n 分段后逐段折行（markdown 子集的 <br> 会真实换行）。

    末尾的换行要先去掉：render_markdown 会把它变成一个行尾的 <br>，而行尾 <br>
    不产生新的行盒，按“多一行”计价会让每条内容都凭空高一整行（真实数据里的正文
    大多以换行结尾），页数因此被高估、页面被过早切断。
    """
    text = str(content or "").rstrip("\n")
    if not text:
        return 0
    return sum(max(1, -(-text_units(seg) // units_per_line)) for seg in text.split("\n"))


def section_item_weight(content: str, meta_lines: int, style: dict, has_title: bool = True) -> int:
    """条目高度(px) = 固定成本 + 正文行数 × 行高 + 元信息行数 × 行高 + 布局装饰。

    base 含条目标题行；标题为空（正文续段）或与栏目标题同名时不会渲染 <h3>，
    此时把标题行成本扣掉——求职目标/个人简介 这类单条目栏目正属于后者。

    此前按“字段个数×固定值”计价，长字段值（到岗安排、核心要求等）折行后的高度
    被低估，导致导出内容溢出 A4 底边。
    """
    weight = style["base"] + style["extra"] + content_line_count(content, style["units_per_line"]) * style["content_line"] + meta_lines * style["meta"]
    return weight - (0 if has_title else style["title"])


def block_has_title(block: dict, section_id: str) -> bool:
    """该条目是否渲染自己的标题行（与栏目标题同名时由栏目承载，不再重复渲染）。"""
    title = str(block.get("title") or "")
    return bool(title) and title != SECTION_TITLES.get(section_id, section_id)


def meta_values(block: dict, exclude: tuple = ()) -> list[str]:
    """元信息行实际渲染的值序列：去标签、去重，period 由调用方按布局决定是否排除。

    此前渲染成"标签 值"对（组织公司 实验室小组 · 熟练程度 能用），标签是数据库
    字段名直译，套在"实验室小组/课程项目"上语义不通，信息密度也低。现在整行就是
    "值 · 值 · 值"（参考简历的做法）；完全相同的值（所在地/目标城市都是深圳）只出现一次。
    """
    fields = block.get("fields") or {}
    displayed = block.get("display_fields") or list(fields)
    values: list[str] = []
    for key in displayed:
        if key in exclude:
            continue
        value = str(fields.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def meta_field_lines(block: dict, side: bool, units_per_line: int) -> int:
    values = meta_values(block, ("period",))
    if not values:
        return 0
    if side:
        return sum(max(1, -(-text_units(value) // units_per_line)) for value in values)
    return max(1, -(-text_units(" · ".join(values)) // units_per_line))


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


# —— 结构化字段的兜底回收（hydration）——
# 渲染器完全依赖块上的 fields（时间右对齐、元信息行、时间轴左时间列）。历史数据
# 迁移或外部写入会把字段压平进正文（"……过拟合。 · 竞赛 · 实验室小组"），这样的
# 块渲染出来就是一堆没有时间的正文。导出与预览前先按同一套规则把尾巴解析回字段：
# 时间形状的段回收为 period，成果栏目里"含奖级词"的段回收为 result，其余段成为
# 无标签的 meta 值。已带 fields 的块一律不动，绝不改写作者写下的内容。
PERIOD_VALUE_RE = re.compile(r"^\d{4}(?:\.\d{1,2})?(?:\s*[-–—~至]\s*(?:\d{4}(?:\.\d{1,2})?|至今|应届))?\s*$")
AWARD_RESULT_RE = re.compile(r"(奖|第\s*\d+\s*名|名次|冠军|亚军|季军|金|银|铜|入围|优胜|一等|二等|三等|Top\s*\d+)")
META_TAIL_SEP = " · "


def _is_meta_segment(segment: str) -> bool:
    text = segment.strip()
    return bool(text) and len(text) <= 16 and not re.search(r"[。！？；;，]", text)


def _classify_award_segments(segments: list[str]) -> dict[str, str]:
    """成果栏目的尾巴段回收为 issuer/result：含奖级词的是 result，否则 issuer。"""
    recovered: dict[str, str] = {}
    issuer = next((seg for seg in segments if not AWARD_RESULT_RE.search(seg)), None)
    result = next((seg for seg in segments if AWARD_RESULT_RE.search(seg)), None)
    if issuer:
        recovered["issuer"] = issuer
    if result:
        recovered["result"] = result
    return recovered


def hydrate_block(block: dict, section_id: str = "") -> dict:
    """从压平的正文尾部回收结构化字段；块已带 fields 时原样返回。"""
    if block.get("fields"):
        return block
    content = str(block.get("content") or "")
    if META_TAIL_SEP not in content:
        return block
    lines = content.split("\n")
    segments = lines[-1].split(META_TAIL_SEP)
    if len(segments) < 2:
        return block
    tail: list[str] = []
    while len(segments) > 1 and _is_meta_segment(segments[-1]):
        tail.insert(0, segments.pop().strip())
    remaining = META_TAIL_SEP.join(segments).strip()
    # 整行都是短段（成果的一行一条、或尾巴里带时间）时，剩下的第一段也属于尾巴；
    # 否则尾巴必须跟在完整句子后面，避免把"负责 A · B · C 三条产品线"这类正文误拆。
    if remaining and _is_meta_segment(remaining) and (section_id == "awards" or any(PERIOD_VALUE_RE.match(seg) for seg in tail)):
        tail.insert(0, remaining.strip())
        remaining = ""
    if len(tail) < 2 or (remaining and not re.search(r"[。！？；…]$", remaining)):
        return block
    recovered_fields: dict[str, str] = {}
    period = next((seg for seg in tail if PERIOD_VALUE_RE.match(seg)), None)
    if period:
        recovered_fields["period"] = period
    if section_id == "awards":
        for key, value in _classify_award_segments([seg for seg in tail if seg != period]).items():
            recovered_fields[key] = value
        extras = []
    else:
        extras = [seg for seg in tail if seg != period]
    for index, value in enumerate(extras, start=1):
        recovered_fields[f"extra_{index}"] = value
    if not recovered_fields:
        return block
    hydrated = dict(block)
    hydrated["fields"] = recovered_fields
    hydrated["field_labels"] = {}
    displayed = list(block.get("display_fields") or [])
    hydrated["display_fields"] = displayed + [key for key in recovered_fields if key not in displayed]
    body = [line for line in lines[:-1] if line.strip()]
    if remaining:
        body.append(remaining)
    hydrated["content"] = "\n".join(body)
    return hydrated


def hydrate_content(content: dict) -> dict:
    """对整份简历内容做字段兜底回收；返回新字典，不改动入参。"""
    return {"sections": [
        dict(section, blocks=[hydrate_block(block, str(section.get("id") or "")) for block in section.get("blocks", [])])
        for section in content.get("sections", [])
    ]}


# —— 导出前体检（lint）——
# 联系方式缺失、条目没有时间、测试/占位数据、零信息句，这些此前都会无声地排上纸面。
# lint_resume 给出问题清单：导出 HTML 里以"仅屏幕可见"的告警条呈现（打印不可见），
# 工作台画布上方同样展示。它只提示，不改写内容。
LINT_GARBAGE_TOKENS = ("阿斯顿发斯蒂芬", "test123", "asdfgh", "占位数据", "待补充", "待填写", "lorem ipsum")
LINT_ZERO_INFO_RE = re.compile(r"^(?:完成|输出)(?:了)?[^，。；;]{0,10}[。.]?$")


def _lint_scan_text(block: dict) -> str:
    fields = block.get("fields") or {}
    displayed = block.get("display_fields") or list(fields)
    values = " ".join(str(fields.get(key) or "") for key in displayed)
    return f"{block.get('title') or ''} {values} {block.get('content') or ''}"


def lint_resume(content: dict) -> list[dict]:
    sections = {item.get("id"): item for item in hydrate_content(content).get("sections", [])}
    issues: list[dict] = []

    def add(level: str, section_id: str, block_id: str, message: str):
        issues.append({"level": level, "section_id": section_id, "block_id": block_id, "message": message})

    basics_blocks = sections.get("basics", {}).get("blocks", [])
    basic_fields = (basics_blocks[0].get("fields") or {}) if basics_blocks else {}
    if not str(basic_fields.get("phone") or "").strip():
        add("error", "basics", basics_blocks[0]["id"] if basics_blocks else "", "缺少电话号码，HR 无法联系你")
    if not str(basic_fields.get("email") or "").strip():
        add("error", "basics", basics_blocks[0]["id"] if basics_blocks else "", "缺少邮箱地址，HR 无法联系你")
    for sid in ("experience", "education", "awards"):
        for block in sections.get(sid, {}).get("blocks", []):
            title = str(block.get("title") or SECTION_TITLES.get(sid, sid))
            fields = block.get("fields") or {}
            if not str(fields.get("period") or "").strip():
                add("warn", sid, str(block.get("id") or ""), f"「{title}」没有时间，经验的新旧无从判断")
            text = _lint_scan_text(block)
            lowered = text.lower()
            for token in LINT_GARBAGE_TOKENS:
                if token in lowered:
                    add("warn", sid, str(block.get("id") or ""), f"「{title}」疑似测试或占位数据（{token}），请核对后修改")
                    break
            for line in str(block.get("content") or "").split("\n"):
                candidate = line.strip().lstrip("-· ")
                if 0 < len(candidate) <= 12 and LINT_ZERO_INFO_RE.match(candidate):
                    add("warn", sid, str(block.get("id") or ""), f"「{title}」存在零信息句“{candidate}”，建议写具体动作或量化结果")
                    break
    return issues


# —— 组稿正文策展（bullet 化 + 去重）——
# 经历条目此前把 context/work/outcome/challenge/solution 全部顺序平铺，一段经历五六行
# 且互相重复。导出与预览共用同一套规则：背景在有"具体工作"时省略、挑战属于内部叙述
# 不上纸面，其余按 work → solution → outcome 组织成 markdown 列表；结果行里的量化
# 指标（百分比、名次、奖级）加粗。已有 ** 的结果行按作者写的渲染，不再叠加。
BOLD_METRIC_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*[%％]|第\s*\d+\s*名|省[一二三]等奖|国[一二三]等奖|\d+\s*(?:倍|名|人|项|份|台|万\+?))")


def bold_metrics(text: str) -> str:
    if "**" in text:
        return text
    return BOLD_METRIC_RE.sub(lambda match: f"**{match.group(0).strip()}**", text)


def curated_experience_plain(details: dict) -> str:
    context = str(details.get("context") or "").strip()
    parts: list[str] = []
    if context and not details.get("work"):
        parts.append(context)
    for key in ("work", "solution", "outcome"):
        value = str(details.get(key) or "").strip()
        if value:
            parts.append(bold_metrics(value) if key == "outcome" else value)
    return "\n".join(f"- {part}" for part in parts)


def curated_education_plain(details: dict) -> str:
    achievement = str(details.get("achievement") or "").strip()
    courses = str(details.get("courses") or "").strip()
    lines = [achievement] if achievement else []
    if courses:
        lines.append(f"核心课程：{courses}")
    return "\n".join(lines)


# —— 技能分组与成果表格（渲染与权重共用）——
# 技能逐条渲染时每条要 3-4 行（名称 + 分类 + 程度 + 场景）；按分类合并成
# "分类：技能（程度，场景）、技能…" 后一类一行，是参考简历的密度来源。成果逐条
# 渲染是两行一条，三列表格一行一条。两种紧凑形态都要求该栏目全部块都带必需字段，
# 否则退回逐条块渲染。
def skill_groups(blocks: list[dict]) -> list[tuple[str, str]]:
    """[(分类, "技能（程度，场景）、技能…")]；有块缺 skill_category 时返回 []。"""
    if not blocks:
        return []
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for block in blocks:
        fields = block.get("fields") or {}
        category = str(fields.get("skill_category") or "").strip()
        if not category:
            return []
        if category not in grouped:
            grouped[category] = []
            order.append(category)
        proficiency = str(fields.get("proficiency") or "").strip()
        context = str(block.get("content") or "").strip()
        note = "，".join(part for part in (proficiency, context) if part)
        label = str(block.get("title") or "").strip()
        grouped[category].append(f"{label}（{note}）" if note else label)
    return [(category, META_TAIL_SEP.join(items).replace(META_TAIL_SEP, "、")) for category, items in ((key, grouped[key]) for key in order)]


def awards_table_rows(blocks: list[dict]) -> list[tuple[str, str, str]]:
    """[(时间, 奖项, 成绩（颁奖单位）)]；有块缺 period/result 时返回 []。"""
    rows: list[tuple[str, str, str]] = []
    for block in blocks:
        fields = block.get("fields") or {}
        period = str(fields.get("period") or "").strip()
        result = str(fields.get("result") or "").strip()
        if not period or not result:
            return []
        issuer = str(fields.get("issuer") or "").strip()
        grade = f"{result}（{issuer}）" if issuer else result
        rows.append((period, str(block.get("title") or ""), grade))
    return rows



def _page_style(layout_id: str, in_sidebar: bool) -> dict:
    """侧栏列（约 44mm 版心）与主栏列的度量口径完全不同，按列取用。"""
    return LAYOUT_METRICS["side" if in_sidebar else layout_id]


def block_renders_content(block: dict, section_id: str) -> bool:
    """该条目渲染出来是否看得见东西（标题、正文、或任一展示字段有值）。

    简历内容里常有不参与本次投递的栏目（个人简介没写、链接没填），此前它们照样
    排出栏目标题——纸面上留下一条只有标题的空条，时间轴版式还多出一个悬空圆点。
    编排前先剔除这些栏目，而不是渲染完再想办法藏起来。
    """
    if str(block.get("content") or "").strip():
        return True
    if block_has_title(block, section_id):
        return True
    fields = block.get("fields") or {}
    displayed = block.get("display_fields") or list(fields)
    return any(fields.get(key) for key in displayed)


def section_has_content(sections: dict, section_id: str) -> bool:
    return any(block_renders_content(block, section_id) for block in (sections.get(section_id, {}).get("blocks") or []))


def section_visible(sections: dict, section_id: str) -> bool:
    """栏目是否显示（简历内容里带 visibility，工作副本可以关掉某一栏）。

    导出端此前只按"有没有内容"筛栏目，没读 visibility，于是隐藏栏目只在画布里消失、
    导出的纸面上照样出现。预览与导出必须用同一套判断。
    """
    return bool(sections.get(section_id, {}).get("visibility", True))


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
    # 技能按分类合并成一行一类；成果（非侧栏）排成三列表格。两种紧凑形态各自
    # 的权重 = 真实行数 × 行高 + 固定装饰，与渲染器同构（见 render_resume_html）。
    if sid == "skills":
        groups = skill_groups(blocks)
        if groups:
            for category, line in groups:
                text = f"**{category}**：{line}"
                out.append({"kind": "flow", "sid": sid, "item": {"id": f"{sid}--group-{category}", "title": "", "content": text, "fields": {}, "display_fields": [], "source_refs": [], "origin": "skill-group"},
                            "weight": content_line_count(text, style["units_per_line"]) * style["content_line"] + GROUP_GAP_PX})
            return out
    if sid == "awards" and not in_sidebar:
        rows = awards_table_rows(blocks)
        if rows:
            out.append({"kind": "flow", "sid": sid, "item": {"id": f"{sid}--table", "title": "", "content": "", "fields": {}, "display_fields": [], "source_refs": [], "origin": "awards-table", "table_rows": rows},
                        "weight": AWARDS_HEADER_PX + len(rows) * AWARDS_ROW_PX})
            return out
    for block in blocks:
        text_value = str(block.get("content", "") or "")
        chunks = [text_value[index:index + limit] for index in range(0, len(text_value), limit)] or [""]
        for index, chunk in enumerate(chunks):
            # 续段只带正文：重复标题与元信息会让同一个条目看起来出现两次。
            item = dict(block, title=block.get("title") if index == 0 else "",
                        content=chunk, fields=block.get("fields") if index == 0 else {},
                        display_fields=block.get("display_fields") if index == 0 else [])
            meta_lines = meta_field_lines(item, in_sidebar, style["meta_units"])
            out.append({"kind": "flow", "sid": sid, "item": item,
                        "weight": section_item_weight(chunk, meta_lines, style, block_has_title(item, sid))})
    return out


def column_height(sections: dict, sid: str, layout_id: str, in_sidebar: bool,
                  units_per_line: int, meta_units: int) -> int:
    """整栏估算高度：栏目标题行 + 各条目（固定成本 + 正文行 + 元信息行）。"""
    style = _page_style(layout_id, in_sidebar)
    blocks = sections.get(sid, {}).get("blocks", [])
    total = style["header"]
    if not blocks:
        return total + style["base"]
    if sid == "skills":
        groups = skill_groups(blocks)
        if groups:
            for category, line in groups:
                text = f"**{category}**：{line}"
                total += content_line_count(text, units_per_line) * style["content_line"] + GROUP_GAP_PX
            return total
    if sid == "awards" and not in_sidebar:
        rows = awards_table_rows(blocks)
        if rows:
            return total + AWARDS_HEADER_PX + len(rows) * AWARDS_ROW_PX
    for block in blocks:
        total += style["base"] + style["extra"] + content_line_count(block.get("content"), units_per_line) * style["content_line"] + meta_field_lines(block, False, meta_units) * style["meta"]
        if not block_has_title(block, sid):
            total -= style["title"]
    return total


def pair_height(sections: dict, layout_id: str, sid: str, sid2: str, budget: int) -> int | None:
    """相邻两栏并排的估算高度；不值得配对时返回 None（保持整宽通排）。

    并排高度取两栏较大者；只有并排明显矮于顺排（PAIR_MIN_SAVING）才配对，否则
    半宽折行会让正文变高、配对反而更费版面。两栏高度不齐时不做额外限制：限制高度差
    会把本来省版面的配对推掉，真实简历因此多出一页。短栏底下的空白靠"每栏左侧色条
    + 表格版式整行外框"来界定，读起来是这一栏还没结束，而不是排版坏了。
    """
    style = LAYOUT_METRICS[layout_id]
    stacked = column_height(sections, sid, layout_id, False, style["units_per_line"], style["meta_units"]) + \
        column_height(sections, sid2, layout_id, False, style["units_per_line"], style["meta_units"])
    height_a = column_height(sections, sid, layout_id, False, style["pair_units_per_line"], style["pair_meta_units"])
    height_b = column_height(sections, sid2, layout_id, False, style["pair_units_per_line"], style["pair_meta_units"])
    paired, shorter = max(height_a, height_b), min(height_a, height_b)
    if paired > pair_height_cap(layout_id, budget) or stacked - paired < PAIR_MIN_SAVING:
        return None
    if shorter < paired * PAIR_MIN_BALANCE:
        return None
    return paired


def paginate(sections: dict, section_ids: list[str], layout_id: str, budget: int,
             in_sidebar: bool = False, first_page_head: int = 0, stats: dict | None = None) -> list[list[dict]]:
    """把栏目切成页面单元并分页。

    单元有两种：
    - ``flow``：某个栏目的一个条目（栏目标题行按页计一次，超长正文按
      section_fragment_limit 切片成多个条目）；
    - ``pair``：**相邻**两个短栏目并排成一行两个模块（仅该布局给了并排额度时）。

    配对以栏目顺序为准，只并排相邻栏目，因此不会打乱简历的栏目次序；并且只在
    真正省下纵向空间时成立。pair 是原子单元，放不下当前页剩余空间、或本页的并排
    额度用完时，会在打包阶段退化回两个 flow 单元，避免为等一整对而空出大半页。

    ``in_sidebar`` 决定用哪一列的口径计价。``first_page_head`` 是首页额外的固定
    占用（侧栏页头），只从第一页扣。
    """
    def blocks_of(sid: str) -> list[dict]:
        return sections.get(sid, {}).get("blocks", [])

    pair_budget = pair_budget_for(layout_id)

    units: list[dict] = []
    index = 0
    while index < len(section_ids):
        sid = section_ids[index]
        if pair_budget and index + 1 < len(section_ids):
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
    total_size = first_page_head
    current_id: str | None = None
    pairs_on_page = 0
    cursor = 0

    def page_budget() -> int:
        """当前页的可用高度：首页要额外让出固定的页头占用。"""
        return budget - (first_page_head if not pages else 0)

    while cursor < len(units):
        unit = units[cursor]
        if unit["kind"] == "pair":
            # 每页的并排额度用完就整宽通排：并排是"让短栏目别独占一行"的例外手段，
            # 不是默认版式。额度用完后相邻的短栏目仍会在下一页配对。
            if (pairs_on_page < pair_budget and (not current or size + unit["weight"] <= page_budget())):
                current.append(unit)
                size += unit["weight"]
                total_size += unit["weight"]
                pairs_on_page += 1
                cursor += 1
                continue
            # 放不下当前页剩余的这一点空间（或额度用完）：退化成两个整宽栏目接着排，
            # 把本页填满，只把真正放不下的条目推到下一页。否则会为等一整对而空出大半页。
            units[cursor:cursor + 1] = fragment_flow(sections, unit["sid"], unit["blocks"], layout_id, in_sidebar) + \
                fragment_flow(sections, unit["sid2"], unit["blocks2"], layout_id, in_sidebar)
            continue
        sid = unit["sid"]
        style = _page_style(layout_id, in_sidebar)
        header = style["header"] if sid != current_id else 0
        if current and size + unit["weight"] + header > page_budget():
            pages.append(current)
            current, size, current_id = [], 0, None
            pairs_on_page = 0
            header = style["header_first"]
        if header:
            size += header
            total_size += header
            current_id = sid
        unit["continued"] = 0
        current.append(unit)
        size += unit["weight"]
        total_size += unit["weight"]
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
    if stats is not None:
        # 全部内容的估算总高（各页 size 之和，size 已含页头与首页固定占用）。
        # 收页时 size 被清零，所以在循环里逐页累计。
        stats["total"] = total_size
    return pages

def render_resume_html(content: dict, title: str, version_number: int, template_slug: str = "classic", lint_issues: list[dict] | None = None) -> str:
    """Render a self-contained, print-ready HTML snapshot from a saved version.

    Blocks are hydrated (field recovery), fragmented and packed with the same
    weights as the SPA preview (see ``web/src/lib/resume.ts``) so page breaks
    match between preview and export. Each page repeats a section heading at
    most once; a heading that continues from an earlier page is suffixed with
    “（续）”.
    """
    content = hydrate_content(content)
    descriptor = descriptor_for(template_slug)
    sections = {item.get("id"): item for item in content.get("sections", [])}
    field_labels = FIELD_LABELS

    def esc(value) -> str:
        return html.escape(str(value or ""), quote=True)

    def block_text(block: dict) -> str:
        return render_markdown(block.get("content", ""))

    def block_fields(block: dict, exclude: tuple = ()) -> str:
        """元信息行：值 · 值 · 值，无标签、重复值只出现一次。标签只留在编辑器里。"""
        return "".join(f'<span class="meta">{esc(value)}</span>' for value in meta_values(block, exclude))

    def block_period(block: dict) -> str:
        """条目的时间字段值；仅当时间属于展示字段时才返回（用于线式/时间轴布局）。"""
        fields = block.get("fields") or {}
        displayed = block.get("display_fields") or list(fields)
        value = str(fields.get("period") or "")
        return value if value and "period" in displayed else ""

    def entry_title(block: dict, heading: str) -> str:
        """条目标题行里的标题；与栏目标题同名（或续段补空）时不再重复渲染。"""
        title = str(block.get("title") or "")
        return f'<h3>{esc(title)}</h3>' if title and title != heading else ""

    def awards_table_html(block: dict) -> str:
        rows = block.get("table_rows") or []
        body_rows = "".join(
            f'<tr><td class="awards-time">{esc(period)}</td><td>{esc(award)}</td><td>{esc(grade)}</td></tr>'
            for period, award, grade in rows
        )
        return ('<table class="awards-table"><thead><tr><th>时间</th><th>奖项 / 赛事</th>'
                f'<th>成绩（颁奖单位）</th></tr></thead><tbody>{body_rows}</tbody></table>')

    def block_html(block: dict, heading: str = "") -> str:
        """条目：时间右对齐到标题行行尾（时间轴布局除外，其时间在左栏）。"""
        if block.get("origin") == "awards-table":
            return f'<article class="block">{awards_table_html(block)}</article>'
        content_text = block_text(block)
        if (block.get("fields") or {}).get("url"):
            url = str(block["fields"]["url"])
            label = (block.get("fields") or {}).get("label") or url
            content_text = f'<a href="{esc(url)}">{esc(label)}</a>' + (f'<br>{content_text}' if content_text else "")
        block_title = entry_title(block, heading)
        period = block_period(block)
        row = ""
        if block_title or period:
            row = f'<div class="entry-row">{block_title}' + (f'<span class="entry-period">{esc(period)}</span>' if period else "") + "</div>"
        return f'<article class="block">{row}<div class="block-meta">{block_fields(block, ("period",))}</div><p>{content_text}</p></article>'

    def timeline_block_html(block: dict, heading: str = "") -> str:
        """时间轴：左侧时间栏 + 中线圆点，正文收在右侧时间轴体内。"""
        if block.get("origin") == "awards-table":
            return f'<article class="block"><span class="t-time"></span><div class="t-body">{awards_table_html(block)}</div></article>'
        content_text = block_text(block)
        if (block.get("fields") or {}).get("url"):
            url = str(block["fields"]["url"])
            label = (block.get("fields") or {}).get("label") or url
            content_text = f'<a href="{esc(url)}">{esc(label)}</a>' + (f'<br>{content_text}' if content_text else "")
        body = f'{entry_title(block, heading)}<div class="block-meta">{block_fields(block, ("period",))}</div><p>{content_text}</p>'
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
                parts.append(timeline_block_html(block, current_heading))
            else:
                parts.append(block_html(block, current_heading))
        if current_id is not None:
            parts.append("</section>")
        return "".join(parts)

    def section_body(sid: str, blocks: list[dict], heading: str) -> str:
        """一个栏目的正文：技能按分类分组、成果排表格，与 fragment_flow 的单元形态一致
        （并排列与整宽通排必须用同一套渲染，否则并排的实际高度会超出它的估算权重）。"""
        if sid == "skills":
            groups = skill_groups(blocks)
            if groups:
                items = [{"id": f"{sid}--group-{category}", "title": "", "content": f"**{category}**：{line}", "fields": {}, "display_fields": [], "source_refs": [], "origin": "skill-group"} for category, line in groups]
                return "".join(block_html(item, heading) for item in items)
        if sid == "awards":
            rows = awards_table_rows(blocks)
            if rows:
                return block_html({"id": f"{sid}--table", "title": "", "content": "", "fields": {}, "display_fields": [], "source_refs": [], "origin": "awards-table", "table_rows": rows}, heading)
        return "".join(block_html(block, heading) for block in blocks)

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
                    return f'<section class="section"><h2>{esc(heading_of(sid))}</h2>{section_body(sid, blocks, heading_of(sid))}</section>'
                parts.append(f'<div class="pair">{col(unit["sid"], unit["blocks"])}{col(unit["sid2"], unit["blocks2"])}</div>')
            else:
                flow.append(unit)
        flush_flow()
        return "".join(parts)

    layout_id = descriptor["layout"]
    plain = layout_id == "plain"
    banner = layout_id == "banner"
    grid = layout_id == "grid"
    line = layout_id == "line"
    timeline = layout_id == "timeline"
    rail = layout_id == "rail"
    # 页头布局：姓名与联系方式由页头呈现，正文不再重复基本信息栏目。
    # 求职目标也不再是栏目：它变成页头下方的一条意向横带（全部版式统一）。
    head_layout = layout_id != "sidebar"
    if head_layout:
        main_ids = ["profile", "experience", "education", "skills", "awards", "links"]
    else:
        # 侧栏布局：技能与成果只出现在侧栏，主栏承载其余栏目。
        main_ids = ["profile", "experience", "education", "links"]
    # 没有内容的栏目直接不参与编排：内容里缺这个栏目、或它一条条目都没有时，
    # 排出来只有一条空标题（时间轴还会多一个悬空圆点）。被关掉的栏目同样不排。
    # SPA 画布用同一判断（sectionVisible + 内容判断）。
    def renderable(sid: str) -> bool:
        return section_visible(sections, sid) and section_has_content(sections, sid)

    main_ids = [sid for sid in main_ids if renderable(sid)]
    # 侧栏布局：基本信息由侧栏页头（姓名 + 联系方式 + 简介）呈现，不再重复成栏目；
    # 技能与成果在侧栏，主栏承载其余栏目。侧栏首页还要放页头，先按同一套度量扣掉
    # 它的高度，否则侧栏首页会把内容裁在 A4 底边之外。
    basics = sections.get("basics", {}).get("blocks", [])
    basic_block = basics[0] if basics else {}
    side_ids = [] if head_layout else [sid for sid in SIDE_SECTION_IDS if renderable(sid)]
    # 求职意向横带：出现在第一页（页头下方/主栏最前），高度从首页预算里扣除。
    # 占位文案（"请填写与目标岗位匹配的简历强调方向。"）不排上纸面。
    PLACEHOLDER_STRATEGY = "请填写与目标岗位匹配的简历强调方向。"
    target_blocks = sections.get("target", {}).get("blocks", [])
    band_block = target_blocks[0] if target_blocks and renderable("target") else None
    band_html = ""
    band_height = 0
    if band_block:
        band_title = str(band_block.get("title") or "").strip()
        band_copy = str(band_block.get("content") or "").strip()
        if band_copy == PLACEHOLDER_STRATEGY:
            band_copy = ""
        primary = band_title if band_title and band_title != SECTION_TITLES.get("target", "求职目标") else band_copy
        # 辅助文案只在确实不同于主文案时才排：条目标题与正文都写成岗位方向的情况真实
        # 存在（工作副本里正文被填成同一个词），否则横带会把同一个词打印两遍。
        # 与 SPA 画布 lib/resume.ts 的 targetBand 同一判断。
        secondary = band_copy if primary == band_title and band_title and band_copy and band_copy != primary else ""
        if primary:
            band_units = text_units(f"{primary}{secondary}")
            band_height = INTENT_BAND_BASE_PX + -(-band_units // LAYOUT_METRICS[layout_id]["units_per_line"]) * INTENT_BAND_LINE_PX
            band_html = (f'<div class="intent-band"><b>求职意向</b><span>{esc(primary)}</span>'
                         + (f"<em>{esc(secondary)}</em>" if secondary else "") + "</div>")
    sidebar_pages = [] if not side_ids else paginate(
        sections, side_ids, layout_id, SIDE_PAGE_BUDGET, in_sidebar=True,
        first_page_head=sidebar_head_height(basic_block, LAYOUT_METRICS["side"]),
    )
    budget = PAGE_BUDGET_PX[layout_id]
    main_stats: dict = {}
    main_pages = paginate(sections, main_ids, layout_id, budget, first_page_head=band_height, stats=main_stats)
    # 紧凑档：全部内容比一页多不出 COMPACT_TRIGGER-1（8%）时，与其让最后一两条挤到近乎
    # 空白的第二页，不如整页换紧凑刻度重排（.page.compact，行距与间距收紧）。重排预算按
    # COMPACT_BUDGET_FACTOR 放大 15%，紧凑 CSS 的真实收缩 ≥ 1/1.15，因此不会越过 A4 底边。
    compact = False
    if len(main_pages) > 1 and main_ids:
        if main_stats.get("total", 0) <= budget * COMPACT_TRIGGER:
            tighter = paginate(sections, main_ids, layout_id, int(budget * COMPACT_BUDGET_FACTOR), first_page_head=band_height)
            if len(tighter) == 1:
                main_pages, compact = tighter, True
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
    rail_head = f'<header class="rail-head"><h1>{head_name}</h1><div class="rail-meta">{head_fields}</div></header>'
    rail_head_slim = f'<header class="rail-head rail-head-slim"><h1>{head_name}</h1></header>'

    page_class = "page compact" if compact else "page"
    chunks: list[str] = []
    for index in range(page_count):
        body = render_units(main_pages[index] if index < len(main_pages) else [])
        band = band_html if index == 0 else ""
        if banner:
            head = banner_head if index == 0 else banner_head_slim
            chunks.append(f'<section class="{page_class} page-banner-page">{head}<main class="main main-plain">{band}{body}</main></section>')
        elif rail:
            head = rail_head if index == 0 else rail_head_slim
            chunks.append(f'<section class="{page_class} page-rail">{head}<main class="main main-plain main-rail">{band}{body}</main></section>')
        elif grid:
            head = grid_head if index == 0 else grid_head_slim
            chunks.append(f'<section class="{page_class} page-grid">{head}<main class="main main-plain main-grid">{band}{body}</main></section>')
        elif line:
            head = line_head if index == 0 else line_head_slim
            chunks.append(f'<section class="{page_class} page-line">{head}<main class="main main-plain main-line">{band}{body}</main></section>')
        elif timeline:
            # 时间轴与 plain 共用紧凑页头（姓名 + 联系方式），正文沿用时间轴节点。
            head = line_head if index == 0 else line_head_slim
            chunks.append(f'<section class="{page_class} page-timeline">{head}<main class="main main-plain main-timeline">{band}{body}</main></section>')
        elif plain:
            head = line_head if index == 0 else line_head_slim
            chunks.append(f'<section class="{page_class} page-plain">{head}<main class="main main-plain">{band}{body}</main></section>')
        else:
            sidebar_html = sidebar_head + render_units(sidebar_items(index)) if index == 0 else render_units(sidebar_items(index))
            chunks.append(f'<section class="{page_class}"><aside class="sidebar">{sidebar_html}</aside><main class="main">{band}{body}</main></section>')
    lint_banner = ""
    if lint_issues:
        rows = "".join(
            f'<li class="lint-{esc(item.get("level") or "warn")}"><b>{esc("必须处理" if item.get("level") == "error" else "建议处理")}</b>{esc(item.get("message") or "")}</li>'
            for item in lint_issues
        )
        lint_banner = f'<aside class="export-lint"><b>导出体检（打印时不会出现在简历上）</b><ul>{rows}</ul></aside>'
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
.page-plain {{ grid-template-columns:1fr; grid-template-rows:auto 1fr; }}
.page-banner-page {{ display:flex; flex-direction:column; }}
.page-banner {{ background:{d['sidebar_bg']}; color:{d['sidebar_fg']}; padding:8mm 11mm; flex:none; }}
.page-banner h1 {{ font-size:20pt; line-height:1.15; margin:0 0 2.2mm; letter-spacing:.5px; }}
.banner-meta {{ display:flex; flex-wrap:wrap; gap:.8mm 3.8mm; color:{d['sidebar_muted']}; font-size:8pt; line-height:1.4; }}
.banner-meta .meta {{ display:block; }}
.banner-slim {{ padding:3.5mm 11mm; display:flex; align-items:baseline; }}
.banner-slim h1 {{ font-size:10pt; margin:0; letter-spacing:1px; }}
.page:last-child {{ break-after:auto; page-break-after:auto; }}
.sidebar {{ background:{d['sidebar_bg']}; color:{d['sidebar_fg']}; padding:10mm 6.5mm; overflow:hidden; }}
.sidebar h1 {{ font-family:Georgia,"Microsoft YaHei",serif; font-size:22pt; line-height:1.1; margin:0 0 3mm; }}
    .side-meta {{ display:grid; gap:1mm; color:{d['sidebar_muted']}; font-size:8pt; line-height:1.3; }}
    .side-meta .meta {{ display:block; }}
    .side-copy {{ white-space:pre-wrap; color:{d['sidebar_muted']}; font-size:9pt; line-height:1.4; }}
.sidebar .section {{ margin-top:3.6mm; border-left:2pt solid {d['on_dark_accent']}; padding-left:2.4mm; }}
.sidebar .section h2 {{ border:0; border-bottom:1px solid rgba(255,255,255,.22); background:none; color:{d['sidebar_heading']}; font-size:8pt; font-weight:700; letter-spacing:.4px; padding:0 0 1mm; margin:0 0 1.6mm; }}
.sidebar .block {{ margin-bottom:1.8mm; }}
.sidebar .block h3 {{ color:{d['sidebar_fg']}; font-size:8.5pt; margin:0 0 1mm; }}
.sidebar .block p {{ color:{d['sidebar_muted']}; font-size:8pt; line-height:1.38; margin:0; }}
/* 深色面上的一切文字都走深色面角色：时间、链接用派生强调色，字段值用 sidebar_muted。
   复用白纸 token（accent/meta）会让侧栏的条目时间和字段值变成深色底上的深色字。 */
.sidebar .entry-period {{ color:{d['on_dark_accent']}; }}
.sidebar .block a {{ color:{d['on_dark_accent']}; }}
.sidebar .block strong {{ color:{d['sidebar_fg']}; }}
.sidebar .block-meta {{ color:{d['sidebar_muted']}; }}
.main {{ padding:10mm 11mm; overflow:hidden; }}
.main-plain {{ padding:9mm 12mm; }}
.page-banner-page .main {{ flex:1; padding-top:7mm; }}
.main > .section:first-child {{ margin-top:0; }}
.main > .pair:first-child {{ margin-top:0; }}
.main > .intent-band:first-child {{ margin-top:0; }}
/* 求职意向横带：一条横带替代"栏目标题条 + 一行字"的独立栏目，页头下第一眼可见。 */
.intent-band {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:1mm 3mm; margin:0 0 2.2mm; padding:1.5mm 2.6mm; background:{d['tint']}; border-left:2.4pt solid {d['accent']}; }}
.intent-band b {{ flex:none; color:{d['heading']}; font-size:10.5pt; letter-spacing:.4px; }}
.intent-band span {{ color:{d['title']}; font-size:9.5pt; font-weight:650; }}
.intent-band em {{ color:{d['meta']}; font-size:8.5pt; font-style:normal; }}
/* 元信息行 = 值 · 值 · 值：标签只在编辑器里出现，纸面上同色淡点分隔。 */
.block-meta .meta+.meta::before, .banner-meta .meta+.meta::before, .line-meta .meta+.meta::before,
.grid-meta .meta+.meta::before, .rail-meta .meta+.meta::before {{ content:'·'; opacity:.45; margin-right:1.2mm; }}
/* 栏目 = 左侧色条 + 标题条。标题条用强调色的淡化底，把"栏目"和"条目"分成两层：
   此前栏目标题只是一行粗体字加一条发丝线，和条目标题几乎同色同号，读者看不出
   栏目从哪开始，短栏目并排时两栏的小字就连成一片。
   只给主栏加框：表格版式自带边框与实底表头，侧栏有自己的深色面框。 */
.section {{ break-inside:avoid; }}
.main .section {{ margin-top:3.2mm; border-left:2.4pt solid {d['accent']}; padding-left:3mm; }}
.pair {{ margin-top:3.2mm; display:grid; grid-template-columns:1fr 1fr; gap:0 7mm; break-inside:avoid; align-items:stretch; }}
.pair .section {{ margin-top:0; }}
.section h2 {{ background:{d['tint']}; color:{d['heading']}; font-size:11pt; font-weight:700; letter-spacing:.2px; margin:0 0 1.5mm; padding:1.2mm 2.4mm 1mm; border-bottom:1px solid {d['rule']}; }}
.block {{ margin:0 0 2mm; break-inside:avoid; }}
    .block h3 {{ color:{d['title']}; font-size:10.5pt; line-height:1.3; margin:0 0 .9mm; }}
    .block-meta {{ display:flex; flex-wrap:wrap; gap:.6mm 3.4mm; color:{d['meta_label']}; font-size:7.8pt; line-height:1.35; margin:0 0 .5mm; }}
    /* 正文 bullet：悬挂缩进的"·"，参考简历的条目形态；量化指标由组稿加粗。 */
    .block ul {{ margin:.8mm 0 0; padding-left:3.2mm; list-style:none; }}
    .block li {{ color:{d['copy']}; font-size:9pt; line-height:1.4; padding-left:2.8mm; }}
    .block li::before {{ content:'·'; display:inline-block; width:2.8mm; margin-left:-2.8mm; font-weight:700; }}
    .block p {{ color:{d['copy']}; font-size:9pt; line-height:1.4; margin:0; white-space:normal; }}
    .block a {{ color:{d['accent']}; }}
    .block strong {{ color:{d['title']}; }}
/* —— 成果三列表格：一行一项（时间 | 奖项/赛事 | 成绩（颁奖单位））—— */
.awards-table {{ width:100%; border-collapse:collapse; margin:0; }}
.awards-table th {{ background:{d['tint']}; color:{d['heading']}; font-size:8.5pt; font-weight:700; text-align:left; padding:1.2mm 2mm; border-bottom:1px solid {d['rule']}; }}
.awards-table td {{ color:{d['copy']}; font-size:9pt; line-height:1.4; padding:1.1mm 2mm; border-bottom:1px solid {d['rule']}; }}
.awards-table tr:last-child td {{ border-bottom:0; }}
.awards-table .awards-time {{ width:24mm; color:{d['meta']}; }}
/* —— 表格表单版式（grid）：表头 + 带边框栏目，栏目标题为实底表头行 —— */
.page-grid {{ display:flex; flex-direction:column; }}
.grid-head {{ flex:none; border:1px solid {d['rule']}; padding:3.4mm 5mm 3mm; text-align:center; }}
.grid-head h1 {{ font-size:16pt; letter-spacing:2px; margin:0 0 2.2mm; color:{d['title']}; }}
.grid-meta {{ display:flex; flex-wrap:wrap; justify-content:center; gap:.8mm 3.8mm; color:{d['meta']}; font-size:8pt; line-height:1.4; }}
.grid-meta .meta {{ display:block; }}
.grid-head.grid-head-slim {{ padding:2.2mm 5mm; border-bottom:1px solid {d['rule']}; }}
.grid-head.grid-head-slim h1 {{ font-size:9.5pt; margin:0; letter-spacing:1px; }}
.main-grid {{ flex:1; padding:3.5mm 9mm 6mm; }}
.main-grid .intent-band {{ border:1px solid {d['rule']}; border-left:2.4pt solid {d['accent']}; }}
.main-grid .pair {{ margin-top:2.4mm; border:1px solid {d['rule']}; overflow:hidden; }}
.main-grid .pair .section {{ margin-top:0; border:0; }}
/* 并排的两栏共用一行外框、中间一条竖线分隔：两栏等高本来就是表格行的正确形态，
   短栏空出来的部分是"表格里的空单元格"，而不是一张八成空的卡片。 */
.main-grid .pair > .section + .section {{ border-left:1px solid {d['rule']}; }}
.main-grid .section {{ border:1px solid {d['rule']}; margin-top:2.4mm; overflow:hidden; }}
.main-grid .section h2 {{ background:{d['sidebar_bg']}; color:{d['sidebar_fg']}; border:0; padding:1.6mm 3mm; margin:0; font-size:10pt; letter-spacing:1.2px; }}
.main-grid .block {{ margin:0 3mm 1.8mm; }}
.main-grid .section .block:first-of-type {{ margin-top:1.6mm; }}
.main-grid .block:last-of-type {{ margin-bottom:1.6mm; }}
.main-grid .awards-table {{ margin:0 3mm 1.8mm; width:calc(100% - 6mm); }}
.main-grid .awards-table tr:last-child td {{ border-bottom:0; }}
/* —— 经典线式版式（line）：居中页头，栏目居中标题，条目时间右对齐 —— */
.page-line {{ display:flex; flex-direction:column; }}
.line-head {{ flex:none; text-align:center; padding:2.4mm 8mm 3.2mm; border-bottom:2px solid {d['sidebar_bg']}; }}
.line-head h1 {{ font-size:17pt; letter-spacing:1.5px; margin:0 0 1.8mm; color:{d['title']}; }}
.line-meta {{ display:flex; flex-wrap:wrap; justify-content:center; gap:.8mm 3.8mm; color:{d['meta']}; font-size:8pt; line-height:1.4; }}
.line-meta .meta {{ display:block; }}
.line-head.line-head-slim {{ padding:2.2mm 8mm; border-bottom:1px solid {d['rule']}; }}
.line-head.line-head-slim h1 {{ font-size:9.5pt; margin:0; letter-spacing:1px; }}
.main-line {{ flex:1; padding:3.5mm 11mm 6mm; }}
/* 线式版式保留"居中标题 + 条目标题左对齐"的档案风：标题条不铺底，改用一条通栏
   细线把栏目封口，标题本身居中——这是它区别于其他版式的识别特征。 */
.main-line .section h2 {{ text-align:center; background:none; border-bottom:1px solid {d['rule']}; padding:0 0 1.5mm; letter-spacing:1.8px; }}
/* 条目标题行：标题居左、时间右对齐同一行（所有非时间轴布局共用）。 */
.entry-row {{ display:flex; justify-content:space-between; align-items:baseline; gap:3mm; margin:0 0 .6mm; }}
.entry-row h3 {{ margin:0; }}
.entry-period {{ color:{d['accent']}; font-weight:600; font-size:8.5pt; white-space:nowrap; }}
.main-line .block:not(:last-child) {{ border-bottom:1px solid {d['rule']}; padding-bottom:1.8mm; }}
/* —— 标签栏版式（rail）：左侧栏目标签列 + 右侧内容，中文校招的经典形态 —— */
.page-rail {{ display:flex; flex-direction:column; }}
.rail-head {{ flex:none; display:flex; justify-content:space-between; align-items:flex-end; gap:6mm; padding:6.5mm 10mm 3.2mm; border-bottom:2px solid {d['sidebar_bg']}; }}
.rail-head h1 {{ font-size:18pt; letter-spacing:1.5px; margin:0; color:{d['title']}; }}
.rail-meta {{ display:flex; flex-direction:column; align-items:flex-end; gap:.7mm; color:{d['meta']}; font-size:8pt; line-height:1.4; text-align:right; }}
.rail-head.rail-head-slim {{ padding:2.2mm 10mm; align-items:baseline; border-bottom:1px solid {d['rule']}; }}
.rail-head.rail-head-slim h1 {{ font-size:9.5pt; letter-spacing:1px; }}
.main-rail {{ flex:1; padding:3.5mm 10mm 6mm; }}
/* 标签列用绝对定位的栏目标题实现：它不占内容行高，正文从 24mm 处起排；
   标签列没有底色与边框，是最轻的栏目分界。 */
.main-rail .section {{ border-left:0; padding:0 0 0 28mm; position:relative; }}
.main-rail .section h2 {{ position:absolute; left:0; top:.8mm; width:24mm; background:none; border-bottom:0; padding:0; margin:0; color:{d['heading']}; font-size:10.5pt; letter-spacing:1.5px; }}
/* —— 时间轴版式（timeline）：一条贯通栏目内所有条目的时间线，时间右对齐贴在轴上 —— */
.page-timeline {{ grid-template-columns:1fr; grid-template-rows:auto 1fr; }}
.main-timeline {{ padding:9mm 12mm; }}
/* 时间线画在栏目上而不是逐条目上：逐条目画线时每换一个栏目就重新起一条，
   且栏目标题不在轴上，读起来像一串断开的列表而不是时间轴。栏目自己带轴线后
   （轴位于时间栏右缘），标题挂在轴的右侧，条目圆点压在轴上形成连续脉络。
   轴线位置必须等于"时间栏宽度 + 轴栏一半"：20mm + 4mm/2 = 22mm。 */
.main-timeline .section {{ border-left:0; padding-left:0; position:relative; }}
.main-timeline .section::before {{ content:''; position:absolute; left:22mm; top:0; bottom:0; width:1px; background:{d['rule']}; }}
.main-timeline .section h2 {{ margin-left:22mm; position:relative; }}
.main-timeline .block {{ display:grid; grid-template-columns:20mm 4mm 1fr; }}
.main-timeline .t-time {{ grid-column:1; color:{d['accent']}; font-size:7.6pt; font-weight:600; line-height:1.35; text-align:right; padding-top:.3mm; overflow-wrap:anywhere; }}
.main-timeline .block::after {{ content:''; grid-column:2; grid-row:1; width:2mm; height:2mm; border-radius:50%; background:{d['accent']}; justify-self:center; margin-top:1.4mm; box-shadow:0 0 0 .7mm #fff; }}
.main-timeline .t-body {{ grid-column:3; min-width:0; }}
.main-timeline .t-body h3 {{ margin:0 0 1.3mm; }}
.main-timeline .t-body ul {{ margin:.8mm 0 0; padding-left:3.2mm; list-style:none; }}
.main-timeline .t-body li {{ padding-left:2.8mm; }}
.main-timeline .t-body li::before {{ content:'·'; display:inline-block; width:2.8mm; margin-left:-2.8mm; font-weight:700; }}
/* —— 紧凑档（.page.compact）：内容只比一页多出不到 10% 时整页收紧。
   实测收缩比（同内容 normal/compact 主栏高度之比）必须 ≤ 1/COMPACT_TRIGGER ≈ 0.909，
   才能保证触发紧凑档的内容装回一页不裁字；当前刻度实测 ≈ 0.85 —— */
.page.compact .main .section, .page.compact .pair {{ margin-top:1.8mm; }}
.page.compact .section h2 {{ padding:.7mm 2mm .6mm; margin-bottom:1mm; }}
.page.compact .block {{ margin:0 0 1.2mm; }}
.page.compact .block h3 {{ margin:0 0 .6mm; }}
.page.compact .entry-row {{ margin:0 0 .4mm; }}
.page.compact .block p, .page.compact .block li {{ line-height:1.25; }}
.page.compact .block-meta {{ margin:0 0 .3mm; gap:.4mm 3mm; }}
.page.compact .sidebar .section {{ margin-top:2.2mm; }}
.page.compact .sidebar .block {{ margin-bottom:1.2mm; }}
.page.compact .intent-band {{ padding:1mm 2mm; margin-bottom:1.5mm; }}
.page.compact .main-plain, .page.compact .main {{ padding-top:7mm; }}
/* —— 导出体检：仅屏幕可见，打印/PDF 不出现 —— */
.export-lint {{ margin:10px auto 0; max-width:860px; background:#fff8f0; border:1px solid #e2b8a6; color:#794633; padding:10px 14px; font-size:12px; line-height:1.6; }}
.export-lint > b {{ display:block; margin-bottom:4px; }}
.export-lint ul {{ margin:0; padding-left:18px; }}
.export-lint li {{ margin:2px 0; }}
.export-lint .lint-error b {{ color:#a34838; margin-right:6px; }}
.export-lint .lint-warn b {{ color:#7a5a1e; margin-right:6px; }}
@media print {{ html,body {{ background:#fff; }} .page {{ margin:0; box-shadow:none; }} .export-lint {{ display:none; }} }}
</style></head><body>{lint_banner}{"".join(chunks)}</body></html>'''
