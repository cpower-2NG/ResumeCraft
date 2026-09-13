from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import quote
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .services import CORE_SECTIONS, FACT_SCHEMAS, build_resume_content, content_hash, dump, evidence_count, identity_key, json_value, replace_custom_fields, replace_fact_details, render_resume_html, serialize_fact, serialize_profile, serialize_version, source_manifest, sync_references
from .templates import BUILTIN_TEMPLATES, template_public_info
from .workbench_database import get_db
from .workbench_models import Evidence, FactAudit, FactEvidence, FactRecord, JobOpportunity, LinkedResume, PendingItem, RequirementProfile, ResumeFactReference, ResumeIdentity, ResumeTemplate, ResumeVersion, ResumeWorkingCopy, TemplateVersion, Workspace


app = FastAPI(title="ResumeCraft API", version="1.0.8")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5175", "http://127.0.0.1:5175", "http://localhost:5176", "http://127.0.0.1:5176"], allow_methods=["*"], allow_headers=["*"])
WORKSPACE_ID = 1
ATTACHMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "attachments"
MAX_EVIDENCE_SIZE = 10 * 1024 * 1024
ALLOWED_EVIDENCE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


@app.on_event("startup")
def ensure_builtin_templates():
    """Create the code-rendered builtin templates once so the library is selectable.

    Missing slugs are seeded; existing rows have their name/description synced
    back to the registry so databases created by earlier releases converge.
    """
    from .workbench_database import SessionLocal

    with SessionLocal() as db:
        if not db.scalar(select(Workspace.id).limit(1)):
            return
        changed = False
        for slug, descriptor in BUILTIN_TEMPLATES.items():
            template = db.scalar(select(ResumeTemplate).where(ResumeTemplate.workspace_id == WORKSPACE_ID, ResumeTemplate.slug == slug))
            if template:
                if template.name != descriptor["name"] or template.description != descriptor["description"]:
                    template.name = descriptor["name"]
                    template.description = descriptor["description"]
                    changed = True
                continue
            template = ResumeTemplate(workspace_id=WORKSPACE_ID, name=descriptor["name"], slug=slug, description=descriptor["description"], active=True)
            db.add(template); db.flush()
            db.add(TemplateVersion(template_id=template.id, version_number=1, content=f"code-rendered:{slug}", checksum="code"))
            changed = True
        if changed:
            db.commit()


class FactInput(BaseModel):
    category: str
    title: str
    content: dict = Field(default_factory=dict)
    details: dict | None = None
    custom_fields: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "active"
    source_note: str = ""


class ProfileInput(BaseModel):
    name: str
    role_direction: str = ""
    core_requirements: list[str] = Field(default_factory=list)
    general_requirements: str = ""
    responsibilities: str = ""
    resume_strategy: str = ""
    raw_jd: str = ""
    source_note: str = ""


class OpportunityInput(BaseModel):
    company: str = ""
    title: str = ""
    raw_jd: str = ""
    url: str = ""
    source_note: str = ""


class SelectionInput(BaseModel):
    selection: dict[str, list[int]] | None = None
    template_version_id: int | None = None


class WorkingCopyInput(BaseModel):
    content: dict


class SaveInput(BaseModel):
    change_summary: str = "用户保存"


class EvidenceInput(BaseModel):
    fact_id: int
    title: str
    url: str
    note: str = ""


def require_workspace(db: Session):
    if not db.get(Workspace, WORKSPACE_ID):
        raise HTTPException(503, "数据库尚未初始化，请先运行数据库迁移和原型资料导入。")


def get_or_404(db: Session, model, item_id: int):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(404, "对象不存在")
    return item


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def unique_resume_identity_key(db: Session, base_key: str) -> str:
    """Keep recycled identities addressable while allowing a new identity for the same profile."""
    candidate = base_key or "resume"
    suffix = 1
    while db.scalar(select(ResumeIdentity.id).where(ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.identity_key == candidate)):
        suffix += 1
        candidate = f"{base_key or 'resume'}-{suffix}"
    return candidate


def fact_response(db: Session, item: FactRecord) -> dict:
    return {**serialize_fact(db, item), "evidence_count": evidence_count(db, item.id)}


def evidence_response(item: Evidence) -> dict:
    return {"id": item.id, "kind": item.kind, "title": item.title, "url": item.url, "filename": item.filename, "mime_type": item.mime_type, "size_bytes": item.size_bytes, "note": item.note, "status": item.status, "created_at": item.created_at}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    require_workspace(db)
    return {"status": "ok"}


@app.get("/api/overview")
def overview(db: Session = Depends(get_db)):
    require_workspace(db)
    count = lambda model, *conditions: db.scalar(select(func.count()).select_from(model).where(*conditions))
    rows = db.scalars(select(ResumeIdentity).where(ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.status == "active").order_by(ResumeIdentity.updated_at.desc()).limit(5)).all()
    return {"stats": {"facts": count(FactRecord, FactRecord.workspace_id == WORKSPACE_ID, FactRecord.status == "active"), "profiles": count(RequirementProfile, RequirementProfile.workspace_id == WORKSPACE_ID, RequirementProfile.status == "active"), "resumes": count(ResumeIdentity, ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.status == "active"), "working_copies": count(ResumeWorkingCopy, ResumeWorkingCopy.dirty.is_(True))}, "recent_resumes": [resume_row(db, item) for item in rows]}


@app.get("/api/pending-items")
def pending_items(db: Session = Depends(get_db)):
    require_workspace(db)
    items = db.scalars(select(PendingItem).where(PendingItem.workspace_id == WORKSPACE_ID, PendingItem.status == "open").order_by(PendingItem.created_at.desc())).all()
    result = []
    for item in items:
        fact = db.get(FactRecord, item.fact_id)
        affected = db.scalars(select(ResumeFactReference).where(ResumeFactReference.resume_identity_id == item.resume_identity_id, ResumeFactReference.fact_id == item.fact_id)).all()
        result.append({"id": item.id, "resume_id": item.resume_identity_id, "fact_id": item.fact_id, "message": item.message, "kind": item.kind, "created_at": item.created_at, "fact_snapshot": fact_response(db, fact) if fact else None, "affected": [{"section_id": ref.section_id, "block_id": ref.block_id} for ref in affected]})
    return result


@app.get("/api/facts")
def list_facts(category: str | None = None, q: str | None = None, include_recycled: bool = False, db: Session = Depends(get_db)):
    require_workspace(db)
    query = select(FactRecord).where(FactRecord.workspace_id == WORKSPACE_ID)
    if not include_recycled: query = query.where(FactRecord.status == "active")
    if category: query = query.where(FactRecord.category == category)
    if q: query = query.where(FactRecord.title.contains(q))
    return [fact_response(db, item) for item in db.scalars(query.order_by(FactRecord.updated_at.desc())).all()]


@app.get("/api/fact-schemas/{category}")
def fact_schema(category: str, db: Session = Depends(get_db)):
    require_workspace(db)
    if category not in FACT_SCHEMAS:
        raise HTTPException(404, "资料分类不存在")
    return [{"key": key, "label": label, "type": kind, "required": required, "displayable": True} for key, label, kind, required in FACT_SCHEMAS[category]]


@app.post("/api/facts", status_code=201)
def create_fact(payload: FactInput, db: Session = Depends(get_db)):
    require_workspace(db)
    details = payload.details if payload.details is not None else payload.content
    data = payload.model_dump(exclude={"content", "details", "custom_fields", "tags"})
    item = FactRecord(workspace_id=WORKSPACE_ID, **data, content=dump(details), tags=dump(payload.tags))
    db.add(item); db.flush()
    replace_fact_details(db, item, details)
    replace_custom_fields(db, item.id, payload.custom_fields)
    db.add(FactAudit(workspace_id=WORKSPACE_ID, fact_id=item.id, action="created", summary="创建事实资料", after_content=item.content))
    db.commit(); db.refresh(item)
    return fact_response(db, item)


@app.get("/api/facts/{fact_id}")
def get_fact(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    return fact_response(db, get_or_404(db, FactRecord, fact_id))


@app.patch("/api/facts/{fact_id}")
def update_fact(fact_id: int, payload: FactInput, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, FactRecord, fact_id); before = item.content
    details = payload.details if payload.details is not None else payload.content
    for key, value in payload.model_dump(exclude={"content", "details", "custom_fields", "tags"}).items(): setattr(item, key, value)
    item.content, item.tags = dump(details), dump(payload.tags)
    replace_fact_details(db, item, details)
    replace_custom_fields(db, item.id, payload.custom_fields)
    db.add(FactAudit(workspace_id=WORKSPACE_ID, fact_id=item.id, action="updated", summary="更新事实资料", before_content=before, after_content=item.content))
    for ref in db.scalars(select(ResumeFactReference).where(ResumeFactReference.fact_id == item.id)).all():
        exists = db.scalar(select(PendingItem.id).where(PendingItem.resume_identity_id == ref.resume_identity_id, PendingItem.fact_id == item.id, PendingItem.status == "open"))
        if not exists: db.add(PendingItem(workspace_id=WORKSPACE_ID, resume_identity_id=ref.resume_identity_id, fact_id=item.id, message=f"来源资料“{item.title}”已更新", kind="source_changed"))
    db.commit(); db.refresh(item)
    return fact_response(db, item)


@app.get("/api/facts/{fact_id}/audits")
def fact_audits(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    return [{"id": item.id, "action": item.action, "summary": item.summary, "created_at": item.created_at} for item in db.scalars(select(FactAudit).where(FactAudit.fact_id == fact_id).order_by(FactAudit.created_at.desc())).all()]


@app.delete("/api/facts/{fact_id}")
def delete_fact(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, FactRecord, fact_id)
    referenced = db.scalar(select(func.count()).select_from(ResumeFactReference).where(ResumeFactReference.fact_id == item.id)) or 0
    if referenced:
        item.status, item.deleted_at = "recycled", now_utc()
        db.add(FactAudit(workspace_id=WORKSPACE_ID, fact_id=item.id, action="recycled", summary="已移入回收站；正式简历历史仍可追溯", after_content=item.content))
        for ref in db.scalars(select(ResumeFactReference).where(ResumeFactReference.fact_id == item.id)).all():
            exists = db.scalar(select(PendingItem.id).where(PendingItem.resume_identity_id == ref.resume_identity_id, PendingItem.fact_id == item.id, PendingItem.status == "open"))
            if not exists: db.add(PendingItem(workspace_id=WORKSPACE_ID, resume_identity_id=ref.resume_identity_id, fact_id=item.id, message=f"来源资料“{item.title}”已移入回收站", kind="source_recycled"))
        db.commit(); return {"mode": "recycled"}
    db.query(FactEvidence).filter(FactEvidence.fact_id == item.id).delete()
    db.query(FactAudit).filter(FactAudit.fact_id == item.id).delete()
    db.delete(item); db.commit(); return {"mode": "permanent"}


@app.post("/api/facts/{fact_id}/restore")
def restore_fact(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, FactRecord, fact_id)
    item.status, item.deleted_at = "active", None
    db.add(FactAudit(workspace_id=WORKSPACE_ID, fact_id=item.id, action="restored", summary="从回收站恢复", after_content=item.content))
    db.commit(); return fact_response(db, item)


@app.get("/api/facts/{fact_id}/evidence")
def list_fact_evidence(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, FactRecord, fact_id)
    return [evidence_response(item) for item in db.scalars(select(Evidence).join(FactEvidence).where(FactEvidence.fact_id == fact_id).order_by(Evidence.created_at.desc())).all()]


@app.post("/api/evidence", status_code=201)
def create_link_evidence(payload: EvidenceInput, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, FactRecord, payload.fact_id)
    if not payload.url.startswith(("https://", "http://")): raise HTTPException(422, "证据链接必须以 http:// 或 https:// 开头")
    item = Evidence(workspace_id=WORKSPACE_ID, kind="link", title=payload.title.strip() or payload.url, url=payload.url.strip(), note=payload.note.strip())
    db.add(item); db.flush(); db.add(FactEvidence(fact_id=payload.fact_id, evidence_id=item.id)); db.commit(); return evidence_response(item)


@app.post("/api/evidence/upload", status_code=201)
async def upload_evidence(fact_id: int = Form(...), title: str = Form(""), note: str = Form(""), file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, FactRecord, fact_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EVIDENCE_SUFFIXES: raise HTTPException(422, "仅支持 PDF、PNG、JPEG 和 WEBP 证据文件")
    body = await file.read()
    if not body or len(body) > MAX_EVIDENCE_SIZE: raise HTTPException(422, "证据文件不能为空且不能超过 10 MB")
    checksum = hashlib.sha256(body).hexdigest(); ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    storage_key = f"{checksum}{suffix}"; path = ATTACHMENTS_DIR / storage_key
    if not path.exists(): path.write_bytes(body)
    item = Evidence(workspace_id=WORKSPACE_ID, kind="file", title=title.strip() or file.filename or "证据文件", storage_key=storage_key, filename=file.filename or storage_key, mime_type=file.content_type or "", size_bytes=len(body), checksum=checksum, note=note.strip())
    db.add(item); db.flush(); db.add(FactEvidence(fact_id=fact_id, evidence_id=item.id)); db.commit(); return evidence_response(item)


@app.delete("/api/evidence/{evidence_id}")
def archive_evidence(evidence_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, Evidence, evidence_id); item.status = "recycled"; db.commit(); return {"mode": "recycled"}


@app.post("/api/evidence/{evidence_id}/restore")
def restore_evidence(evidence_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, Evidence, evidence_id); item.status = "active"; db.commit(); return evidence_response(item)


def set_profile(payload: ProfileInput, db: Session, item: RequirementProfile | None = None):
    item = item or RequirementProfile(workspace_id=WORKSPACE_ID, identity_key="")
    for key, value in payload.model_dump(exclude={"core_requirements"}).items(): setattr(item, key, value)
    item.core_requirements = dump(payload.core_requirements); item.identity_key = identity_key(item) or f"profile-{item.name.strip().lower()}"
    conflict = db.scalar(select(RequirementProfile).where(RequirementProfile.workspace_id == WORKSPACE_ID, RequirementProfile.identity_key == item.identity_key, RequirementProfile.id != (item.id or 0)))
    if conflict: raise HTTPException(409, "岗位画像的身份键已存在")
    return item


@app.get("/api/requirement-profiles")
def list_profiles(include_recycled: bool = False, db: Session = Depends(get_db)):
    require_workspace(db)
    query = select(RequirementProfile).where(RequirementProfile.workspace_id == WORKSPACE_ID)
    if not include_recycled: query = query.where(RequirementProfile.status == "active")
    profiles = db.scalars(query.order_by(RequirementProfile.updated_at.desc())).all()
    active_resumes = {item.requirement_profile_id: item.id for item in db.scalars(select(ResumeIdentity).where(ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.status == "active")).all()}
    opportunity_counts = {item.requirement_profile_id: item.count for item in db.execute(select(JobOpportunity.requirement_profile_id, func.count().label("count")).where(JobOpportunity.workspace_id == WORKSPACE_ID).group_by(JobOpportunity.requirement_profile_id)).all()}
    return [{**serialize_profile(item), "active_resume_id": active_resumes.get(item.id), "opportunity_count": opportunity_counts.get(item.id, 0)} for item in profiles]


@app.post("/api/requirement-profiles", status_code=201)
def create_profile(payload: ProfileInput, db: Session = Depends(get_db)):
    require_workspace(db); item = set_profile(payload, db); db.add(item); db.commit(); db.refresh(item); return serialize_profile(item)


@app.get("/api/requirement-profiles/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    require_workspace(db); return serialize_profile(get_or_404(db, RequirementProfile, profile_id))


@app.patch("/api/requirement-profiles/{profile_id}")
def update_profile(profile_id: int, payload: ProfileInput, db: Session = Depends(get_db)):
    require_workspace(db); item = set_profile(payload, db, get_or_404(db, RequirementProfile, profile_id)); db.commit(); db.refresh(item); return serialize_profile(item)


@app.delete("/api/requirement-profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, RequirementProfile, profile_id)
    has_resume = db.scalar(select(func.count()).select_from(ResumeIdentity).where(ResumeIdentity.requirement_profile_id == item.id)) or 0
    if has_resume:
        item.status, item.deleted_at = "recycled", now_utc(); db.commit(); return {"mode": "recycled"}
    db.query(LinkedResume).filter(LinkedResume.requirement_profile_id == item.id).delete()
    db.query(JobOpportunity).filter(JobOpportunity.requirement_profile_id == item.id).delete()
    db.delete(item); db.commit(); return {"mode": "permanent"}


@app.post("/api/requirement-profiles/{profile_id}/restore")
def restore_profile(profile_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, RequirementProfile, profile_id); item.status, item.deleted_at = "active", None; db.commit(); return serialize_profile(item)


@app.get("/api/requirement-profiles/{profile_id}/opportunities")
def list_opportunities(profile_id: int, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, RequirementProfile, profile_id)
    return [{"id": item.id, "company": item.company, "title": item.title, "raw_jd": item.raw_jd, "url": item.url, "source_note": item.source_note} for item in db.scalars(select(JobOpportunity).where(JobOpportunity.requirement_profile_id == profile_id)).all()]


@app.post("/api/requirement-profiles/{profile_id}/opportunities", status_code=201)
def create_opportunity(profile_id: int, payload: OpportunityInput, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, RequirementProfile, profile_id)
    item = JobOpportunity(workspace_id=WORKSPACE_ID, requirement_profile_id=profile_id, **payload.model_dump()); db.add(item); db.commit(); return {"id": item.id}


@app.patch("/api/opportunities/{opportunity_id}")
def update_opportunity(opportunity_id: int, payload: OpportunityInput, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, JobOpportunity, opportunity_id)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    db.commit(); return {"id": item.id, **payload.model_dump()}


@app.delete("/api/opportunities/{opportunity_id}")
def delete_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, JobOpportunity, opportunity_id); db.delete(item); db.commit(); return {"mode": "permanent"}


def opportunity_response(item: JobOpportunity) -> dict:
    return {"id": item.id, "requirement_profile_id": item.requirement_profile_id, "company": item.company, "title": item.title, "raw_jd": item.raw_jd, "url": item.url, "source_note": item.source_note, "created_at": item.created_at}


@app.get("/api/opportunities")
def list_all_opportunities(db: Session = Depends(get_db)):
    require_workspace(db)
    return [opportunity_response(item) for item in db.scalars(select(JobOpportunity).where(JobOpportunity.workspace_id == WORKSPACE_ID).order_by(JobOpportunity.created_at.desc())).all()]


@app.get("/api/search")
def global_search(q: str, db: Session = Depends(get_db)):
    require_workspace(db)
    keyword = f"%{q.strip()}%"
    if not q.strip(): return []
    facts = db.scalars(select(FactRecord).where(FactRecord.workspace_id == WORKSPACE_ID, FactRecord.title.contains(keyword)).order_by(FactRecord.updated_at.desc()).limit(5)).all()
    profiles = db.scalars(select(RequirementProfile).where(RequirementProfile.workspace_id == WORKSPACE_ID, (RequirementProfile.name.contains(keyword)) | (RequirementProfile.role_direction.contains(keyword))).order_by(RequirementProfile.updated_at.desc()).limit(5)).all()
    opportunities = db.scalars(select(JobOpportunity).where(JobOpportunity.workspace_id == WORKSPACE_ID, (JobOpportunity.company.contains(keyword)) | (JobOpportunity.title.contains(keyword))).limit(5)).all()
    resumes = db.scalars(select(ResumeIdentity).where(ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.display_name.contains(keyword)).limit(5)).all()
    evidence_rows = db.scalars(select(Evidence).where(Evidence.workspace_id == WORKSPACE_ID, (Evidence.title.contains(keyword)) | (Evidence.filename.contains(keyword))).limit(5)).all()
    category_labels = {key: title for key, title in CORE_SECTIONS}
    results = []
    for item in facts: results.append({"type": "fact", "id": item.id, "title": item.title, "subtitle": category_labels.get(item.category, item.category), "status": item.status, "updated_at": item.updated_at, "payload": fact_response(db, item)})
    for item in evidence_rows:
        fact_id = db.scalar(select(FactEvidence.fact_id).where(FactEvidence.evidence_id == item.id))
        results.append({"type": "evidence", "id": item.id, "title": item.title, "subtitle": item.filename or item.url or "说明材料", "status": item.status, "updated_at": item.updated_at, "payload": {"fact": fact_response(db, db.get(FactRecord, fact_id)) if fact_id and db.get(FactRecord, fact_id) else None}})
    for item in profiles: results.append({"type": "profile", "id": item.id, "title": item.name, "subtitle": item.role_direction or "岗位方向待补充", "status": item.status, "updated_at": item.updated_at, "payload": None})
    for item in opportunities: results.append({"type": "opportunity", "id": item.id, "title": f"{item.company} · {item.title}".strip(" ·"), "subtitle": "招聘机会", "status": "active", "updated_at": item.created_at, "payload": {"profile_id": item.requirement_profile_id}})
    for item in resumes: results.append({"type": "resume", "id": item.id, "title": item.display_name, "subtitle": "正式简历", "status": item.status, "updated_at": item.updated_at, "payload": None})
    return results


def default_template_version(db: Session) -> TemplateVersion:
    item = db.scalar(select(TemplateVersion).join(ResumeTemplate).where(ResumeTemplate.workspace_id == WORKSPACE_ID, ResumeTemplate.active.is_(True)).order_by(TemplateVersion.id))
    if not item: raise HTTPException(503, "没有可用模板，请先迁移原型模板")
    return item


def resolve_template_version(db: Session, template_version_id: int) -> TemplateVersion:
    version = db.get(TemplateVersion, template_version_id)
    template = db.get(ResumeTemplate, version.template_id) if version else None
    if not version or not template or not template.active or template.workspace_id != WORKSPACE_ID:
        raise HTTPException(422, "模板不存在或未启用")
    return version


@app.get("/api/templates")
def templates(db: Session = Depends(get_db)):
    require_workspace(db)
    templates = db.scalars(select(ResumeTemplate).where(ResumeTemplate.workspace_id == WORKSPACE_ID, ResumeTemplate.active.is_(True))).all()
    result = []
    for item in templates:
        version = db.scalar(select(TemplateVersion).where(TemplateVersion.template_id == item.id).order_by(TemplateVersion.version_number.desc()))
        descriptor = BUILTIN_TEMPLATES.get(item.slug, {})
        result.append({"id": item.id, "name": item.name, "slug": item.slug, "description": item.description, "version": version.version_number if version else None, "template_version_id": version.id if version else None, **template_public_info(descriptor)})
    return result


@app.post("/api/linked-resumes", status_code=201)
def create_linked_resume(profile_id: int, template_version_id: int | None = None, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, RequirementProfile, profile_id)
    version = resolve_template_version(db, template_version_id) if template_version_id else default_template_version(db)
    item = LinkedResume(workspace_id=WORKSPACE_ID, requirement_profile_id=profile_id, template_version_id=version.id, selection="{}")
    db.add(item); db.commit(); return {"id": item.id}


@app.get("/api/linked-resumes/{linked_id}")
def get_linked_resume(linked_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, LinkedResume, linked_id); profile = get_or_404(db, RequirementProfile, item.requirement_profile_id); selection = json_value(item.selection, {})
    return {"id": item.id, "profile": serialize_profile(profile), "selection": selection, "preview": build_resume_content(db, profile, selection), "template": template_info_response(db, item.template_version_id)}


@app.patch("/api/linked-resumes/{linked_id}")
def update_linked_resume(linked_id: int, payload: SelectionInput, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, LinkedResume, linked_id)
    if payload.template_version_id is not None:
        item.template_version_id = resolve_template_version(db, payload.template_version_id).id
    if payload.selection is not None:
        item.selection = dump(payload.selection)
    db.commit(); return get_linked_resume(linked_id, db)


@app.post("/api/linked-resumes/{linked_id}/convert", status_code=201)
def convert_linked_resume(linked_id: int, db: Session = Depends(get_db)):
    require_workspace(db); linked = get_or_404(db, LinkedResume, linked_id); profile = get_or_404(db, RequirementProfile, linked.requirement_profile_id)
    if db.scalar(select(ResumeIdentity.id).where(ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.requirement_profile_id == profile.id, ResumeIdentity.status == "active")):
        raise HTTPException(409, "该岗位画像已有活跃正式简历")
    content = build_resume_content(db, profile, json_value(linked.selection, {}))
    identity = ResumeIdentity(workspace_id=WORKSPACE_ID, requirement_profile_id=profile.id, identity_key=unique_resume_identity_key(db, profile.identity_key), display_name=f"{profile.name}简历")
    db.add(identity); db.flush()
    version = ResumeVersion(resume_identity_id=identity.id, version_number=1, content=dump(content), source_manifest=dump(source_manifest(content)), profile_snapshot=dump(serialize_profile(profile)), template_version_id=linked.template_version_id, reason="format_conversion", change_summary="格式化简历、未润色", content_hash=content_hash(content))
    db.add(version); db.flush(); identity.current_version_id = version.id; db.add(ResumeWorkingCopy(resume_identity_id=identity.id, base_version_id=version.id, content=dump(content), dirty=False)); sync_references(db, identity.id, content); db.commit()
    return {"resume_id": identity.id, "version": 1}


def resume_row(db: Session, item: ResumeIdentity) -> dict:
    current = db.get(ResumeVersion, item.current_version_id) if item.current_version_id else None; copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == item.id)); profile = db.get(RequirementProfile, item.requirement_profile_id)
    warnings = db.scalar(select(func.count()).select_from(PendingItem).where(PendingItem.resume_identity_id == item.id, PendingItem.status == "open"))
    return {"id": item.id, "display_name": item.display_name, "profile_name": profile.name if profile else "", "current_version": current.version_number if current else None, "updated_at": item.updated_at, "dirty": copy.dirty if copy else False, "warnings": warnings, "status": item.status}


@app.get("/api/resumes")
def list_resumes(include_recycled: bool = False, db: Session = Depends(get_db)):
    require_workspace(db)
    query = select(ResumeIdentity).where(ResumeIdentity.workspace_id == WORKSPACE_ID)
    if not include_recycled:
        query = query.where(ResumeIdentity.status == "active")
    return [resume_row(db, item) for item in db.scalars(query.order_by(ResumeIdentity.updated_at.desc())).all()]


@app.delete("/api/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, ResumeIdentity, resume_id)
    # A formal resume always owns immutable versions, so it is recovered through the recycle bin.
    item.status, item.deleted_at = "recycled", now_utc(); db.commit(); return {"mode": "recycled"}


@app.post("/api/resumes/{resume_id}/restore")
def restore_resume(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, ResumeIdentity, resume_id); item.status, item.deleted_at = "active", None; db.commit(); return resume_row(db, item)


@app.get("/api/resumes/{resume_id}")
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, ResumeIdentity, resume_id); copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == item.id)); current = db.get(ResumeVersion, item.current_version_id) if item.current_version_id else None
    template_version_id = copy.template_version_id if copy and copy.template_version_id else (current.template_version_id if current else None)
    template_info = template_info_response(db, template_version_id)
    return {**resume_row(db, item), "working_copy": {"content": json_value(copy.content, {}), "dirty": copy.dirty, "base_version_id": copy.base_version_id, "updated_at": copy.updated_at}, "current": serialize_version(current) if current else None, "template": template_info}


def template_info_response(db: Session, template_version_id: int | None) -> dict | None:
    if not template_version_id:
        return None
    version = db.get(TemplateVersion, template_version_id)
    if not version:
        return None
    template = db.get(ResumeTemplate, version.template_id)
    descriptor = BUILTIN_TEMPLATES.get(template.slug, {}) if template else {}
    return {"template_version_id": template_version_id, "template_id": template.id if template else None, "slug": template.slug if template else "classic", "name": template.name if template else "经典侧栏模板", **template_public_info(descriptor or BUILTIN_TEMPLATES["classic"])}


class TemplateChoiceInput(BaseModel):
    template_version_id: int


@app.patch("/api/resumes/{resume_id}/template")
def choose_template(resume_id: int, payload: TemplateChoiceInput, db: Session = Depends(get_db)):
    """Record the template choice in the working copy; the next formal save pins it."""
    require_workspace(db); identity = get_or_404(db, ResumeIdentity, resume_id)
    version = resolve_template_version(db, payload.template_version_id)
    copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == resume_id))
    latest = db.get(ResumeVersion, identity.current_version_id) if identity.current_version_id else None
    effective = copy.template_version_id or (latest.template_version_id if latest else None)
    # Re-picking the active template must not mark the working copy dirty.
    if effective != version.id:
        copy.template_version_id = version.id
        copy.dirty = True
    db.commit()
    return {"template": template_info_response(db, version.id), "dirty": copy.dirty}


@app.patch("/api/resumes/{resume_id}/working-copy")
def update_working_copy(resume_id: int, payload: WorkingCopyInput, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, ResumeIdentity, resume_id); copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == resume_id)); copy.content, copy.dirty = dump(payload.content), True; db.commit(); return {"dirty": True, "updated_at": copy.updated_at}


@app.post("/api/resumes/{resume_id}/save")
def save_resume(resume_id: int, payload: SaveInput, db: Session = Depends(get_db)):
    require_workspace(db); identity = get_or_404(db, ResumeIdentity, resume_id); copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == resume_id)); latest = db.get(ResumeVersion, identity.current_version_id) if identity.current_version_id else None
    template_version_id = copy.template_version_id or (latest.template_version_id if latest else None)
    if not template_version_id: raise HTTPException(503, "没有可用模板")
    content = json_value(copy.content, {})
    if latest is None:
        # A forked identity saves the copied working copy as its own v1.
        profile = db.get(RequirementProfile, identity.requirement_profile_id)
        version = ResumeVersion(resume_identity_id=identity.id, version_number=1, content=dump(content), source_manifest=dump(source_manifest(content)), profile_snapshot=dump(serialize_profile(profile)), template_version_id=template_version_id, reason=copy.pending_reason or "identity_copy", change_summary=payload.change_summary, content_hash=content_hash(content))
    else:
        if copy.base_version_id != latest.id: raise HTTPException(409, "工作副本基线已过期，请从当前版本重新载入")
        reason = copy.pending_reason or ("template_change" if template_version_id != latest.template_version_id else "user_save")
        version = ResumeVersion(resume_identity_id=identity.id, version_number=latest.version_number + 1, content=dump(content), source_manifest=dump(source_manifest(content)), profile_snapshot=latest.profile_snapshot, template_version_id=template_version_id, reason=reason, change_summary=payload.change_summary, content_hash=content_hash(content))
    db.add(version); db.flush(); identity.current_version_id = version.id; copy.base_version_id = version.id; copy.dirty = False; copy.pending_reason = None; sync_references(db, identity.id, content)
    db.query(PendingItem).filter(PendingItem.resume_identity_id == identity.id, PendingItem.status == "open").update({"status": "resolved"}, synchronize_session=False)
    db.commit(); return serialize_version(version)


@app.get("/api/resumes/{resume_id}/versions")
def versions(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, ResumeIdentity, resume_id)
    return [serialize_version(item) for item in db.scalars(select(ResumeVersion).where(ResumeVersion.resume_identity_id == resume_id).order_by(ResumeVersion.version_number.desc())).all()]


def block_keys(section: dict, block: dict) -> list[str]:
    keys = [f"{section['id']}|{block['id']}"]
    keys.extend(f"{section['id']}|fact-{fact_id}" for fact_id in block.get("source_refs", []) if isinstance(fact_id, int))
    return keys


def version_block_index(content: dict) -> dict:
    index = {}
    for section in content.get("sections", []):
        for block in section.get("blocks", []):
            entry = {"section_id": section["id"], "section_title": section.get("title"), "title": block.get("title"), "content": block.get("content"), "fields": block.get("fields") or {}, "display_fields": block.get("display_fields") or [], "origin": block.get("origin"), "source_refs": block.get("source_refs") or []}
            for key in block_keys(section, block):
                index.setdefault(key, entry)
    return index


@app.get("/api/resumes/{resume_id}/versions/{from_number}/diff/{to_number}")
def diff_versions(resume_id: int, from_number: int, to_number: int, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, ResumeIdentity, resume_id)
    versions_by_number = {item.version_number: item for item in db.scalars(select(ResumeVersion).where(ResumeVersion.resume_identity_id == resume_id, ResumeVersion.version_number.in_([from_number, to_number]))).all()}
    if from_number not in versions_by_number or to_number not in versions_by_number:
        raise HTTPException(404, "版本不存在")
    before_index = version_block_index(json_value(versions_by_number[from_number].content, {}))
    after_index = version_block_index(json_value(versions_by_number[to_number].content, {}))
    changes = []
    for key, after in after_index.items():
        before = before_index.get(key)
        if not before:
            changes.append({"key": key, "kind": "added", "before": None, "after": after})
        elif before["content"] != after["content"] or before["title"] != after["title"] or before["fields"] != after["fields"] or before["display_fields"] != after["display_fields"]:
            changes.append({"key": key, "kind": "modified", "before": before, "after": after})
    for key, before in before_index.items():
        if key not in after_index:
            changes.append({"key": key, "kind": "removed", "before": before, "after": None})
    return {"from_version": from_number, "to_version": to_number, "changes": changes}


@app.post("/api/resumes/{resume_id}/versions/{version_number}/restore")
def restore_version(resume_id: int, version_number: int, db: Session = Depends(get_db)):
    require_workspace(db); identity = get_or_404(db, ResumeIdentity, resume_id); version = db.scalar(select(ResumeVersion).where(ResumeVersion.resume_identity_id == resume_id, ResumeVersion.version_number == version_number))
    if not version: raise HTTPException(404, "版本不存在")
    copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == resume_id))
    current = db.get(ResumeVersion, identity.current_version_id)
    restoring_current = current is not None and version.id == current.id
    # Restoring an older version arms a "rollback" reason for the next formal save;
    # restoring the current version is a discard, so the copy is clean again.
    copy.content = version.content
    copy.base_version_id = identity.current_version_id
    copy.dirty = not restoring_current
    copy.pending_reason = None if restoring_current else "rollback"
    copy.template_version_id = version.template_version_id
    db.commit()
    return {"restored_version": version_number, "dirty": copy.dirty, "pending_reason": copy.pending_reason}


@app.post("/api/resumes/{resume_id}/fork", status_code=201)
def fork_resume_identity(resume_id: int, db: Session = Depends(get_db)):
    """Create a new resume identity from the current version; the original keeps its history."""
    require_workspace(db); identity = get_or_404(db, ResumeIdentity, resume_id); current = db.get(ResumeVersion, identity.current_version_id)
    if not current: raise HTTPException(409, "该简历还没有正式版本")
    new_identity = ResumeIdentity(workspace_id=WORKSPACE_ID, requirement_profile_id=identity.requirement_profile_id, identity_key=unique_resume_identity_key(db, identity.identity_key), display_name=f"{identity.display_name}（新身份）")
    db.add(new_identity); db.flush()
    # The fork inherits the source version's content and template so its first save can create v1.
    db.add(ResumeWorkingCopy(resume_identity_id=new_identity.id, base_version_id=None, content=current.content, dirty=True, template_version_id=current.template_version_id))
    db.commit()
    return {"resume_id": new_identity.id, "display_name": new_identity.display_name}


@app.post("/api/resumes/{resume_id}/versions/{version_number}/export")
def export_resume(resume_id: int, version_number: int, db: Session = Depends(get_db)):
    require_workspace(db)
    identity = get_or_404(db, ResumeIdentity, resume_id)
    version = db.scalar(select(ResumeVersion).where(ResumeVersion.resume_identity_id == resume_id, ResumeVersion.version_number == version_number))
    if not version:
        raise HTTPException(404, "版本不存在")
    content = json_value(version.content, {})
    template_version = db.get(TemplateVersion, version.template_version_id)
    template = db.get(ResumeTemplate, template_version.template_id) if template_version else None
    html = render_resume_html(content, identity.display_name, version_number, template.slug if template else "classic")
    filename = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff._-]+", "-", f"{identity.display_name}-v{version_number}").strip("-") or f"resume-v{version_number}"
    header_filename = quote(f"{filename}.html")
    return Response(content=html, media_type="text/html; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="resume-v{version_number}.html"; filename*=UTF-8\'\'{header_filename}'})
