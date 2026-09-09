from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .services import build_resume_content, content_hash, dump, evidence_count, identity_key, json_value, serialize_fact, serialize_profile, serialize_version, source_manifest, sync_references
from .workbench_database import get_db
from .workbench_models import Evidence, FactAudit, FactEvidence, FactRecord, JobOpportunity, LinkedResume, PendingItem, RequirementProfile, ResumeFactReference, ResumeIdentity, ResumeTemplate, ResumeVersion, ResumeWorkingCopy, TemplateVersion, Workspace


app = FastAPI(title="简历工作台 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
WORKSPACE_ID = 1
ATTACHMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "attachments"
MAX_EVIDENCE_SIZE = 10 * 1024 * 1024
ALLOWED_EVIDENCE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


class FactInput(BaseModel):
    category: str
    title: str
    content: dict = Field(default_factory=dict)
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
    selection: dict[str, list[int]]


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


def fact_response(db: Session, item: FactRecord) -> dict:
    return {**serialize_fact(item), "evidence_count": evidence_count(db, item.id)}


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
    return {"stats": {"facts": count(FactRecord, FactRecord.workspace_id == WORKSPACE_ID, FactRecord.status == "active"), "profiles": count(RequirementProfile, RequirementProfile.workspace_id == WORKSPACE_ID), "resumes": count(ResumeIdentity, ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.status == "active"), "working_copies": count(ResumeWorkingCopy, ResumeWorkingCopy.dirty.is_(True))}, "recent_resumes": [resume_row(db, item) for item in rows]}


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


@app.post("/api/facts", status_code=201)
def create_fact(payload: FactInput, db: Session = Depends(get_db)):
    require_workspace(db)
    data = payload.model_dump(exclude={"content", "tags"})
    item = FactRecord(workspace_id=WORKSPACE_ID, **data, content=dump(payload.content), tags=dump(payload.tags))
    db.add(item); db.flush()
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
    for key, value in payload.model_dump(exclude={"content", "tags"}).items(): setattr(item, key, value)
    item.content, item.tags = dump(payload.content), dump(payload.tags)
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
    return [serialize_profile(item) for item in db.scalars(query.order_by(RequirementProfile.updated_at.desc())).all()]


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


def default_template_version(db: Session) -> TemplateVersion:
    item = db.scalar(select(TemplateVersion).join(ResumeTemplate).where(ResumeTemplate.workspace_id == WORKSPACE_ID, ResumeTemplate.active.is_(True)).order_by(TemplateVersion.id))
    if not item: raise HTTPException(503, "没有可用模板，请先迁移原型模板")
    return item


@app.get("/api/templates")
def templates(db: Session = Depends(get_db)):
    require_workspace(db)
    templates = db.scalars(select(ResumeTemplate).where(ResumeTemplate.workspace_id == WORKSPACE_ID, ResumeTemplate.active.is_(True))).all()
    result = []
    for item in templates:
        version = db.scalar(select(TemplateVersion).where(TemplateVersion.template_id == item.id).order_by(TemplateVersion.version_number.desc()))
        result.append({"id": item.id, "name": item.name, "slug": item.slug, "description": item.description, "version": version.version_number})
    return result


@app.post("/api/linked-resumes", status_code=201)
def create_linked_resume(profile_id: int, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, RequirementProfile, profile_id)
    item = LinkedResume(workspace_id=WORKSPACE_ID, requirement_profile_id=profile_id, template_version_id=default_template_version(db).id, selection="{}")
    db.add(item); db.commit(); return {"id": item.id}


@app.get("/api/linked-resumes/{linked_id}")
def get_linked_resume(linked_id: int, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, LinkedResume, linked_id); profile = get_or_404(db, RequirementProfile, item.requirement_profile_id); selection = json_value(item.selection, {})
    return {"id": item.id, "profile": serialize_profile(profile), "selection": selection, "preview": build_resume_content(db, profile, selection)}


@app.patch("/api/linked-resumes/{linked_id}")
def update_linked_resume(linked_id: int, payload: SelectionInput, db: Session = Depends(get_db)):
    require_workspace(db); item = get_or_404(db, LinkedResume, linked_id); item.selection = dump(payload.selection); db.commit(); return get_linked_resume(linked_id, db)


@app.post("/api/linked-resumes/{linked_id}/convert", status_code=201)
def convert_linked_resume(linked_id: int, db: Session = Depends(get_db)):
    require_workspace(db); linked = get_or_404(db, LinkedResume, linked_id); profile = get_or_404(db, RequirementProfile, linked.requirement_profile_id)
    if db.scalar(select(ResumeIdentity).where(ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.requirement_profile_id == profile.id)): raise HTTPException(409, "该岗位画像已有正式简历")
    content = build_resume_content(db, profile, json_value(linked.selection, {})); identity = ResumeIdentity(workspace_id=WORKSPACE_ID, requirement_profile_id=profile.id, identity_key=profile.identity_key, display_name=f"{profile.name}简历")
    db.add(identity); db.flush()
    version = ResumeVersion(resume_identity_id=identity.id, version_number=1, content=dump(content), source_manifest=dump(source_manifest(content)), profile_snapshot=dump(serialize_profile(profile)), template_version_id=linked.template_version_id, reason="format_conversion", change_summary="格式化简历、未润色", content_hash=content_hash(content))
    db.add(version); db.flush(); identity.current_version_id = version.id; db.add(ResumeWorkingCopy(resume_identity_id=identity.id, base_version_id=version.id, content=dump(content), dirty=False)); sync_references(db, identity.id, content); db.commit()
    return {"resume_id": identity.id, "version": 1}


def resume_row(db: Session, item: ResumeIdentity) -> dict:
    current = db.get(ResumeVersion, item.current_version_id) if item.current_version_id else None; copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == item.id)); profile = db.get(RequirementProfile, item.requirement_profile_id)
    warnings = db.scalar(select(func.count()).select_from(PendingItem).where(PendingItem.resume_identity_id == item.id, PendingItem.status == "open"))
    return {"id": item.id, "display_name": item.display_name, "profile_name": profile.name if profile else "", "current_version": current.version_number if current else None, "updated_at": item.updated_at, "dirty": copy.dirty if copy else False, "warnings": warnings}


@app.get("/api/resumes")
def list_resumes(db: Session = Depends(get_db)):
    require_workspace(db)
    return [resume_row(db, item) for item in db.scalars(select(ResumeIdentity).where(ResumeIdentity.workspace_id == WORKSPACE_ID, ResumeIdentity.status == "active").order_by(ResumeIdentity.updated_at.desc())).all()]


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
    require_workspace(db); item = get_or_404(db, ResumeIdentity, resume_id); copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == item.id)); current = db.get(ResumeVersion, item.current_version_id)
    return {**resume_row(db, item), "working_copy": {"content": json_value(copy.content, {}), "dirty": copy.dirty, "base_version_id": copy.base_version_id, "updated_at": copy.updated_at}, "current": serialize_version(current)}


@app.patch("/api/resumes/{resume_id}/working-copy")
def update_working_copy(resume_id: int, payload: WorkingCopyInput, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, ResumeIdentity, resume_id); copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == resume_id)); copy.content, copy.dirty = dump(payload.content), True; db.commit(); return {"dirty": True, "updated_at": copy.updated_at}


@app.post("/api/resumes/{resume_id}/save")
def save_resume(resume_id: int, payload: SaveInput, db: Session = Depends(get_db)):
    require_workspace(db); identity = get_or_404(db, ResumeIdentity, resume_id); copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == resume_id)); latest = db.get(ResumeVersion, identity.current_version_id)
    if copy.base_version_id != latest.id: raise HTTPException(409, "工作副本基线已过期，请从当前版本重新载入")
    content = json_value(copy.content, {}); version = ResumeVersion(resume_identity_id=identity.id, version_number=latest.version_number + 1, content=dump(content), source_manifest=dump(source_manifest(content)), profile_snapshot=latest.profile_snapshot, template_version_id=latest.template_version_id, reason="user_save", change_summary=payload.change_summary, content_hash=content_hash(content))
    db.add(version); db.flush(); identity.current_version_id = version.id; copy.base_version_id = version.id; copy.dirty = False; sync_references(db, identity.id, content); db.commit(); return serialize_version(version)


@app.get("/api/resumes/{resume_id}/versions")
def versions(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db); get_or_404(db, ResumeIdentity, resume_id)
    return [serialize_version(item) for item in db.scalars(select(ResumeVersion).where(ResumeVersion.resume_identity_id == resume_id).order_by(ResumeVersion.version_number.desc())).all()]


@app.post("/api/resumes/{resume_id}/versions/{version_number}/restore")
def restore_version(resume_id: int, version_number: int, db: Session = Depends(get_db)):
    require_workspace(db); identity = get_or_404(db, ResumeIdentity, resume_id); version = db.scalar(select(ResumeVersion).where(ResumeVersion.resume_identity_id == resume_id, ResumeVersion.version_number == version_number))
    if not version: raise HTTPException(404, "版本不存在")
    copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == resume_id)); copy.content, copy.base_version_id, copy.dirty = version.content, identity.current_version_id, True; db.commit(); return {"restored_version": version_number, "dirty": True}
