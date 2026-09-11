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


def render_resume_html(content: dict, title: str, version_number: int) -> str:
    """Render a self-contained, print-ready HTML snapshot from a saved version."""
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
        return esc(block.get("content", "")).replace("\n", "<br>")

    def block_fields(block: dict) -> str:
        fields = block.get("fields") or {}
        displayed = block.get("display_fields") or list(fields)
        labels = {**field_labels, **(block.get("field_labels") or {})}
        return "".join(f'<span class="meta"><b>{esc(labels.get(key, key))}</b> {esc(fields.get(key))}</span>' for key in displayed if fields.get(key))

    def block_html(block: dict) -> str:
        content = block_text(block)
        if (block.get("fields") or {}).get("url"):
            url = str(block["fields"]["url"])
            label = (block.get("fields") or {}).get("label") or url
            content = f'<a href="{esc(url)}">{esc(label)}</a>' + (f'<br>{content}' if content else "")
        return f'<article class="block"><h3>{esc(block.get("title"))}</h3><div class="block-meta">{block_fields(block)}</div><p>{content}</p></article>'

    def section_units(section_id: str, heading: str) -> list[tuple[str, int]]:
        section = sections.get(section_id, {})
        units: list[tuple[str, int]] = []
        for block in section.get("blocks", []):
            text_value = str(block.get("content", "") or "")
            chunks = [text_value[index:index + 900] for index in range(0, len(text_value), 900)] or [""]
            for index, chunk in enumerate(chunks):
                item = dict(block, content=chunk, fields=block.get("fields") if index == 0 else {}, display_fields=block.get("display_fields") if index == 0 else [])
                units.append((f'<section class="section"><h2>{esc(heading)}</h2>{block_html(item)}</section>', 110 + len(chunk)))
        return units

    basics = sections.get("basics", {}).get("blocks", [])
    basic_text = block_text(basics[0]) if basics else ""
    basic_meta = block_fields(basics[0]) if basics else ""
    sidebar = f'<h1>{esc(basics[0].get("title") if basics else title)}</h1><div class="side-meta">{basic_meta}</div><p class="side-copy">{basic_text}</p>'
    sidebar += "".join(section_html for section_html, _ in section_units("skills", "技能") + section_units("awards", "成果"))
    main_units = []
    for section_id, heading in (("target", "求职目标"), ("profile", "个人简介"), ("experience", "项目与实践"), ("education", "教育经历"), ("links", "链接与作品集")):
        main_units.extend(section_units(section_id, heading))
    chunks: list[str] = []
    current, size = [], 0
    for unit, unit_size in main_units:
        if current and size + unit_size > 2600:
            chunks.append("".join(current)); current, size = [], 0
        current.append(unit); size += unit_size
    if current or not chunks:
        chunks.append("".join(current))
    pages = "".join(f'<section class="page"><aside class="sidebar">{sidebar if index == 0 else ""}</aside><main class="main">{chunk}</main></section>' for index, chunk in enumerate(chunks))
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{esc(title)} v{version_number}</title>
<style>
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }}
html,body {{ margin:0; padding:0; background:#e9efeb; color:#24342f; font-family:Arial,"Microsoft YaHei",sans-serif; }}
body {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.page {{ width:210mm; height:297mm; margin:16px auto; display:grid; grid-template-columns:58mm 1fr; background:#fff; break-after:page; page-break-after:always; box-shadow:0 8px 25px #18302922; overflow:hidden; }}
.page:last-child {{ break-after:auto; page-break-after:auto; }}
.sidebar {{ background:#163b43; color:#f4f7f4; padding:14mm 7mm; overflow:hidden; }}
.sidebar h1 {{ font-family:Georgia,"Microsoft YaHei",serif; font-size:23pt; line-height:1.1; margin:0 0 5mm; }}
    .side-meta {{ display:grid; gap:1.5mm; color:#cad9d5; font-size:8pt; line-height:1.45; }}
    .side-meta .meta {{ display:block; }}
    .side-copy {{ white-space:pre-wrap; color:#cad9d5; font-size:9pt; line-height:1.6; }}
.sidebar .section {{ margin-top:9mm; }}
.sidebar .section h2 {{ border:0; color:#a7c9c2; font-size:8pt; letter-spacing:1.4px; padding:0; margin:0 0 3mm; }}
.sidebar .block {{ margin-bottom:4mm; }}
.sidebar .block h3 {{ color:#fff; font-size:8.5pt; margin:0 0 1mm; }}
.sidebar .block p {{ color:#cad9d5; font-size:8pt; line-height:1.45; margin:0; }}
.main {{ padding:14mm 12mm; overflow:hidden; }}
.main > .section:first-child {{ margin-top:0; }}
.section {{ margin-top:7mm; break-inside:avoid; }}
.section h2 {{ border-bottom:1px solid #d5e0dc; color:#17343a; font-size:12pt; margin:0 0 3mm; padding-bottom:2mm; }}
.block {{ margin:0 0 5mm; break-inside:avoid; }}
    .block h3 {{ color:#263f40; font-size:10.5pt; line-height:1.35; margin:0 0 1.5mm; }}
    .block-meta {{ display:flex; flex-wrap:wrap; gap:1mm 3mm; color:#66807b; font-size:7.8pt; line-height:1.4; margin:0 0 1mm; }}
    .meta b {{ color:#527875; font-weight:600; }}
    .block p {{ color:#4c605d; font-size:9pt; line-height:1.6; margin:0; white-space:normal; }}
    .block a {{ color:#236b74; }}
@media print {{ html,body {{ background:#fff; }} .page {{ margin:0; box-shadow:none; }} }}
</style></head><body>{pages}</body></html>'''
