from __future__ import annotations

import base64
import copy
import hashlib
import mimetypes
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from .domain.catalog import (
    available_templates,
    ensure_templates,
    resolve_template,
    successor_key,
    template_response,
)
from .domain.delivery import export_events as list_export_events
from .domain.delivery import record_export
from .domain.evidence import sync_evidence_changes
from .domain.profiles import add_audit, apply_profile_values, clone_profile_for_resume
from .domain.resume_chain import (
    convert_draft,
    create_draft,
    current_version,
    restore_version as restore_formal_version,
    save_working_copy,
    working_copy as load_working_copy,
)
from .services import (
    DETAIL_COLUMNS,
    FACT_CATEGORY_LABELS,
    FACT_FIELD_OPTIONS,
    SCHEMA_FIELDS,
    business_key_for,
    dump,
    ensure_fact_catalog,
    evidence_count,
    evidence_manifest,
    fact_audit_snapshot,
    fact_tags,
    json_value,
    lint_resume,
    linked_skill_ids,
    linked_skills,
    profile_photo_snapshot,
    replace_experience_skills,
    replace_fact_details,
    replace_fact_tags,
    render_resume_html,
    serialize_fact,
    serialize_profile,
    serialize_version,
    source_manifest,
    sync_references,
)
from .templates import descriptor_for, template_public_info
from .workbench_database import get_db
from .workbench_models import (
    Evidence,
    EvidenceAuditEvent,
    ExportEvent,
    ExperienceSkillLink,
    FactAchievementDetail,
    FactAuditEvent,
    FactBasicsDetail,
    FactCategory,
    FactEducationDetail,
    FactEvidence,
    FactExperienceDetail,
    FactFieldDefinition,
    FactRecord,
    FactSchemaVersion,
    FactSkillDetail,
    FactTag,
    JobOpportunity,
    LinkedResume,
    PendingIssue,
    ProfileAuditEvent,
    RequirementProfile,
    Resume,
    ResumeEvidenceUse,
    ResumeFactUse,
    ResumeVersion,
    ResumeVersionFactSnapshot,
    ResumeWorkingCopy,
    ProfilePhoto,
    SkillGroup,
    Tag,
    Template,
    TemplatePreference,
    Workspace,
    now,
)


APP_VERSION = "2.0.0"
WORKSPACE_ID = 1
ATTACHMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "attachments"
MAX_EVIDENCE_SIZE = 10 * 1024 * 1024
MAX_PROFILE_PHOTO_SIZE = 5 * 1024 * 1024
ALLOWED_EVIDENCE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_PROFILE_PHOTO_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".jfif"}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    sync_global_catalogues()
    yield


app = FastAPI(title="ResumeCraft API", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactInput(StrictModel):
    category_code: str
    schema_version_id: int | None = None
    title: str = Field(min_length=1, max_length=250)
    fields: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    skill_ids: list[int] = Field(default_factory=list)
    source_note: str = ""
    status: str = "active"


class FactPatchInput(StrictModel):
    schema_version_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=250)
    fields: dict[str, Any] | None = None
    tags: list[str] | None = None
    skill_ids: list[int] | None = None
    source_note: str | None = None
    status: str | None = None


class ProfileInput(StrictModel):
    name: str = Field(min_length=1, max_length=180)
    role_direction: str = ""
    core_requirements: list[str] = Field(default_factory=list)
    general_requirements: str = ""
    responsibilities: str = ""
    resume_strategy: str = ""
    raw_jd: str = ""
    source_note: str = ""


class ProfilePatchInput(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    role_direction: str | None = None
    core_requirements: list[str] | None = None
    general_requirements: str | None = None
    responsibilities: str | None = None
    resume_strategy: str | None = None
    raw_jd: str | None = None
    source_note: str | None = None
    status: str | None = None


class ProfileCopyInput(StrictModel):
    name: str | None = None
    role_direction: str | None = None
    core_requirements: list[str] | None = None
    general_requirements: str | None = None
    responsibilities: str | None = None
    resume_strategy: str | None = None
    raw_jd: str | None = None
    source_note: str | None = None


class OpportunityInput(StrictModel):
    requirement_profile_id: int
    company: str = ""
    title: str = ""
    raw_jd: str = ""
    url: str = ""
    source_note: str = ""


class OpportunityPatchInput(StrictModel):
    company: str | None = None
    title: str | None = None
    raw_jd: str | None = None
    url: str | None = None
    source_note: str | None = None
    status: str | None = None


class SelectionInput(StrictModel):
    selection: dict[str, list[int]] | None = None
    template_id: int | None = None


class LinkedResumeInput(StrictModel):
    profile_id: int
    template_id: int | None = None
    selection: dict[str, list[int]] = Field(default_factory=dict)


class WorkingCopyInput(StrictModel):
    content: dict
    expected_version_id: int | None = None


class SaveInput(StrictModel):
    change_summary: str = "用户保存"
    expected_version_id: int | None = None


class EvidenceInput(StrictModel):
    kind: str = "link"
    title: str = ""
    url: str = ""
    note: str = ""
    fact_id: int | None = None
    relation_note: str = ""


class EvidenceUpdateInput(StrictModel):
    title: str | None = None
    status: str | None = None
    reason: str = ""


class TemplateChoiceInput(StrictModel):
    template_id: int


class TemplatePreferenceInput(StrictModel):
    default_template_id: int | None = None
    last_selected_template_id: int | None = None


class ResumeCreateInput(StrictModel):
    linked_resume_id: int | None = None
    profile_id: int | None = None
    template_id: int | None = None
    selection: dict[str, list[int]] | None = None


class ResumeUpdateInput(StrictModel):
    display_name: str | None = None
    status: str | None = None


class PendingIssueInput(StrictModel):
    status: str
    reason: str = ""


class SkillGroupInput(StrictModel):
    code: str
    display_name: str
    sort_order: int = 0


def sync_global_catalogues() -> None:
    from .workbench_database import SessionLocal

    with SessionLocal() as db:
        if not db.scalar(select(Workspace.id).limit(1)):
            return
        ensure_fact_catalog(db)
        ensure_templates(db)
        preference = db.get(TemplatePreference, WORKSPACE_ID)
        if preference is None:
            preference = TemplatePreference(workspace_id=WORKSPACE_ID)
            db.add(preference)
            db.flush()
        if preference.default_template_id is None:
            templates = available_templates(db)
            if templates:
                preference.default_template_id = templates[0].id
        db.commit()


def require_workspace(db: Session) -> Workspace:
    workspace = db.get(Workspace, WORKSPACE_ID)
    if workspace is None:
        raise HTTPException(503, "数据库尚未初始化，请先运行数据库迁移")
    return workspace


def actor_id(db: Session) -> int:
    return require_workspace(db).owner_id


def get_or_404(db: Session, model, item_id: int):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(404, "对象不存在")
    return item


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def fact_response(db: Session, item: FactRecord) -> dict:
    return {
        **serialize_fact(db, item),
        "evidence_count": evidence_count(db, item.id),
    }


def checked_fact_category(category: str) -> str:
    if category not in FACT_CATEGORY_LABELS:
        raise HTTPException(422, "资料分类不存在")
    return category


def checked_fact_details(
    db: Session,
    category: str,
    values: dict[str, Any],
    schema_version_id: int | None = None,
) -> dict[str, Any]:
    unknown = set(values) - DETAIL_COLUMNS[category]
    extension_definitions = db.scalars(
        select(FactFieldDefinition).where(
            FactFieldDefinition.category_code == category,
            FactFieldDefinition.schema_version_id == schema_version_id,
            FactFieldDefinition.is_extension == 1,
        )
    ).all() if schema_version_id is not None else []
    extension_keys = {item.field_key for item in extension_definitions}
    if unknown - extension_keys:
        raise HTTPException(
            422,
            {
                "code": "unknown_fact_fields",
                "fields": sorted(unknown - extension_keys),
            },
        )
    result = {key: "" for key in DETAIL_COLUMNS[category]}
    result.update({key: value for key, value in values.items() if value is not None})
    if category == "experience" and not str(result.get("experience_kind") or ""):
        result["experience_kind"] = "project"
    if category == "achievement" and not str(
        result.get("achievement_kind") or ""
    ):
        result["achievement_kind"] = "honor"
    for key in ("experience_kind", "achievement_kind"):
        value = str(result.get(key) or "")
        allowed = {item[0] for item in FACT_FIELD_OPTIONS.get(key, [])}
        if value and value not in allowed:
            raise HTTPException(422, f"{key} 的取值不受支持")
    if category == "skill":
        group_id = result.get("skill_group_id")
        if group_id not in (None, ""):
            group = db.get(SkillGroup, int(group_id))
            if group is None or group.workspace_id != WORKSPACE_ID:
                raise HTTPException(422, "技能分组不存在")
            result["skill_group_id"] = group.id
    if category == "achievement" and result.get("experience_fact_id") not in (
        None,
        "",
    ):
        parent = db.get(FactRecord, int(result["experience_fact_id"]))
        if (
            parent is None
            or parent.workspace_id != WORKSPACE_ID
            or parent.category_code != "experience"
        ):
            raise HTTPException(422, "主经历不存在或分类不正确")
        result["experience_fact_id"] = parent.id
    return result


def ensure_fact_status(db: Session, item: FactRecord, status: str) -> None:
    allowed = {
        "active": {"archived", "recycled"},
        "archived": {"active", "recycled"},
        "recycled": {"active", "archived", "purged"},
        "purged": set(),
    }
    if status not in allowed:
        raise HTTPException(422, "资料状态不受支持")
    if status != item.status and status not in allowed[item.status]:
        raise HTTPException(409, "资料状态转换无效")


def write_fact_audit(
    db: Session,
    fact: FactRecord,
    action: str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    changed_fields: list[str] | None = None,
    reason: str = "",
    related_fact_ids: list[int] | None = None,
) -> FactAuditEvent:
    event = FactAuditEvent(
        workspace_id=fact.workspace_id,
        fact_id=fact.id,
        actor_user_id=actor_id(db),
        action=action,
        schema_version_id=fact.schema_version_id,
        changed_fields=dump(changed_fields or []),
        before_values=dump(before or {}),
        after_values=dump(after or {}),
        related_fact_ids=dump(related_fact_ids or []),
        reason=reason,
    )
    db.add(event)
    return event


def evidence_response(item: Evidence) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "url": item.url,
        "filename": item.filename,
        "mime_type": item.mime_type,
        "size_bytes": item.size_bytes,
        "checksum": item.checksum,
        "note": item.note,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "preview_url": (
            f"/api/evidence/{item.id}/file"
            if item.kind == "file"
            else item.url
        ),
    }


def write_evidence_audit(
    db: Session,
    evidence: Evidence,
    action: str,
    *,
    changed_fields: list[str] | None = None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str = "",
) -> EvidenceAuditEvent:
    event = EvidenceAuditEvent(
        workspace_id=evidence.workspace_id,
        evidence_id=evidence.id,
        actor_user_id=actor_id(db),
        action=action,
        changed_fields=dump(changed_fields or []),
        before_values=dump(before or {}),
        after_values=dump(after or {}),
        reason=reason,
    )
    db.add(event)
    return event


def save_file_evidence(
    db: Session,
    *,
    body: bytes,
    suffix: str,
    filename: str,
    mime_type: str,
    title: str,
    note: str = "",
) -> Evidence:
    checksum = hashlib.sha256(body).hexdigest()
    item = db.scalar(
        select(Evidence).where(
            Evidence.workspace_id == WORKSPACE_ID,
            Evidence.kind == "file",
            Evidence.checksum == checksum,
        )
    )
    if item is not None:
        return item
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    storage_key = f"{checksum}{suffix}"
    path = ATTACHMENTS_DIR / storage_key
    if not path.exists():
        path.write_bytes(body)
    item = Evidence(
        workspace_id=WORKSPACE_ID,
        kind="file",
        title=title.strip() or filename or "证据文件",
        storage_key=storage_key,
        filename=filename or storage_key,
        mime_type=mime_type,
        size_bytes=len(body),
        checksum=checksum,
        note=note.strip(),
    )
    db.add(item)
    db.flush()
    write_evidence_audit(db, item, "created", after=evidence_response(item))
    return item


def profile_photo_response(photo: ProfilePhoto, evidence: Evidence) -> dict:
    return {
        "id": photo.id,
        "basics_fact_id": photo.basics_fact_id,
        "evidence_id": photo.evidence_id,
        "status": photo.status,
        "created_at": photo.created_at,
        "archived_at": photo.archived_at,
        "evidence": evidence_response(evidence),
    }


def profile_photo_mime(body: bytes, suffix: str) -> tuple[str, str]:
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(body) >= 12 and body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise HTTPException(422, "档案照片必须是有效的 PNG、JPEG 或 WebP 图片")


def checked_profile_photo_fact(db: Session, fact_id: int) -> FactRecord:
    fact = get_or_404(db, FactRecord, fact_id)
    if (
        fact.workspace_id != WORKSPACE_ID
        or fact.category_code != "basics"
        or fact.status != "active"
    ):
        raise HTTPException(422, "档案照片只能关联当前有效的个人档案")
    return fact


def active_profile_photo(
    db: Session, basics_fact_id: int
) -> ProfilePhoto | None:
    return db.scalar(
        select(ProfilePhoto).where(
            ProfilePhoto.workspace_id == WORKSPACE_ID,
            ProfilePhoto.basics_fact_id == basics_fact_id,
            ProfilePhoto.status == "active",
        )
    )


def sync_profile_photo_to_working_copies(
    db: Session, basics_fact_id: int
) -> None:
    """Carry a photo change into active resume drafts as unsaved edits.

    Published versions stay immutable until the user saves the working copy.
    Existing drafts that already contain the basics block are updated in place,
    so opening an existing resume after uploading a portrait does not require
    recreating the resume.
    """
    current = profile_photo_snapshot(db, basics_fact_id)
    resume_ids = db.scalars(
        select(Resume.id).where(
            Resume.workspace_id == WORKSPACE_ID,
            Resume.status == "active",
        )
    ).all()
    for resume_id in resume_ids:
        working = db.scalar(
            select(ResumeWorkingCopy).where(
                ResumeWorkingCopy.resume_id == resume_id
            )
        )
        if working is None:
            continue
        content = json_value(working.content_json, {})
        basics = next(
            (
                section
                for section in content.get("sections", [])
                if section.get("id") == "basics"
            ),
            None,
        )
        if not basics or not basics.get("blocks"):
            continue
        block = basics["blocks"][0]
        before = block.get("photo")
        if current:
            block["photo"] = copy.deepcopy(current)
        else:
            block.pop("photo", None)
        if before == block.get("photo"):
            continue
        working.content_json = dump(content)
        working.content_state = "dirty"
        working.updated_at = now_utc()


def content_with_embedded_profile_photo(db: Session, content: dict) -> dict:
    """Return a render copy whose portrait is a self-contained data URL."""
    result = copy.deepcopy(content)
    basics = next(
        (
            section
            for section in result.get("sections", [])
            if section.get("id") == "basics"
        ),
        None,
    )
    if not basics or not basics.get("blocks"):
        return result
    block = basics["blocks"][0]
    photo = block.get("photo")
    if not photo:
        return result
    evidence = db.get(Evidence, photo.get("evidence_id"))
    if (
        evidence is None
        or evidence.workspace_id != WORKSPACE_ID
        or evidence.kind != "file"
        or not str(evidence.mime_type or "").startswith("image/")
        or not evidence.storage_key
    ):
        raise HTTPException(409, "档案照片文件缺失，无法导出")
    root = ATTACHMENTS_DIR.resolve()
    path = (root / evidence.storage_key).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(409, "档案照片文件缺失，无法导出")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    photo["data_url"] = f"data:{evidence.mime_type};base64,{encoded}"
    return result


def opportunity_response(item: JobOpportunity) -> dict:
    return {
        "id": item.id,
        "requirement_profile_id": item.requirement_profile_id,
        "company": item.company,
        "title": item.title,
        "raw_jd": item.raw_jd,
        "url": item.url,
        "source_note": item.source_note,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def template_info_response(db: Session, template_id: int | None) -> dict | None:
    if not template_id:
        return None
    template = db.get(Template, template_id)
    if template is None:
        return None
    data = template_response(template)
    data.update(template_public_info(descriptor_for(successor_key(template))))
    return data


def resume_row(db: Session, item: Resume) -> dict:
    current = current_version(db, item)
    copy = db.scalar(
        select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_id == item.id)
    )
    profile = db.get(RequirementProfile, item.requirement_profile_id)
    warnings = db.scalar(
        select(func.count())
        .select_from(PendingIssue)
        .where(
            PendingIssue.resume_id == item.id,
            PendingIssue.status == "open",
        )
    )
    return {
        "id": item.id,
        "display_name": item.display_name,
        "profile_id": item.requirement_profile_id,
        "profile_name": profile.name if profile else "",
        "origin_linked_resume_id": item.origin_linked_resume_id,
        "current_version_id": item.current_version_id,
        "current_version": current.version_number if current else None,
        "content_state": copy.content_state if copy else "clean",
        "evidence_sync_state": copy.evidence_sync_state if copy else "clean",
        "baseline_state": copy.baseline_state if copy else "current",
        "warnings": warnings or 0,
        "status": item.status,
        "template_id": item.template_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    require_workspace(db)
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/overview")
def overview(db: Session = Depends(get_db)):
    require_workspace(db)

    def count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(*conditions))

    rows = db.scalars(
        select(Resume)
        .where(Resume.workspace_id == WORKSPACE_ID, Resume.status == "active")
        .order_by(Resume.updated_at.desc())
        .limit(5)
    ).all()
    return {
        "stats": {
            "facts": count(
                FactRecord,
                FactRecord.workspace_id == WORKSPACE_ID,
                FactRecord.status == "active",
            ),
            "profiles": count(
                RequirementProfile,
                RequirementProfile.workspace_id == WORKSPACE_ID,
                RequirementProfile.status == "active",
            ),
            "resumes": count(
                Resume,
                Resume.workspace_id == WORKSPACE_ID,
                Resume.status == "active",
            ),
            "working_copies": count(
                ResumeWorkingCopy,
                ResumeWorkingCopy.workspace_id == WORKSPACE_ID,
                ResumeWorkingCopy.content_state == "dirty",
            ),
            "pending_issues": count(
                PendingIssue,
                PendingIssue.workspace_id == WORKSPACE_ID,
                PendingIssue.status == "open",
            ),
        },
        "recent_resumes": [resume_row(db, item) for item in rows],
    }


@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    require_workspace(db)
    ensure_fact_catalog(db)
    db.commit()
    return [
        {
            "code": item.code,
            "display_name": item.display_name,
            "sort_order": item.sort_order,
            "status": item.status,
        }
        for item in db.scalars(
            select(FactCategory).order_by(FactCategory.sort_order)
        ).all()
    ]


@app.get("/api/fact-schemas/{category}")
def fact_schema(category: str, db: Session = Depends(get_db)):
    require_workspace(db)
    category = checked_fact_category(category)
    ensure_fact_catalog(db)
    db.commit()
    schema = db.scalar(
        select(FactSchemaVersion).where(
            FactSchemaVersion.category_code == category,
            FactSchemaVersion.status == "published",
        )
    )
    definitions = db.scalars(
        select(FactFieldDefinition)
        .where(FactFieldDefinition.schema_version_id == schema.id)
        .order_by(FactFieldDefinition.sort_order, FactFieldDefinition.id)
    ).all()
    return {
        "category_code": category,
        "schema_version_id": schema.id,
        "version_number": schema.version_number,
        "fields": [
            {
                "key": item.field_key,
                "label": item.label,
                "value_type": item.value_type,
                "requirement_level": item.requirement_level,
                "is_extension": bool(item.is_extension),
                "storage_table": item.storage_table,
                "storage_column": item.storage_column,
                "sort_order": item.sort_order,
                "options": [
                    {"value": value, "label": label}
                    for value, label in FACT_FIELD_OPTIONS.get(
                        item.field_key, []
                    )
                ],
            }
            for item in definitions
        ],
    }


@app.get("/api/tags")
def list_tags(db: Session = Depends(get_db)):
    require_workspace(db)
    return [
        {
            "id": item.id,
            "display_name": item.display_name,
            "normalized_name": item.normalized_name,
            "status": item.status,
        }
        for item in db.scalars(
            select(Tag)
            .where(Tag.workspace_id == WORKSPACE_ID, Tag.status == "active")
            .order_by(Tag.display_name)
        ).all()
    ]


@app.get("/api/skill-groups")
def list_skill_groups(db: Session = Depends(get_db)):
    require_workspace(db)
    return [
        {
            "id": item.id,
            "code": item.code,
            "display_name": item.display_name,
            "sort_order": item.sort_order,
            "status": item.status,
        }
        for item in db.scalars(
            select(SkillGroup)
            .where(
                SkillGroup.workspace_id == WORKSPACE_ID,
                SkillGroup.status == "active",
            )
            .order_by(SkillGroup.sort_order, SkillGroup.display_name)
        ).all()
    ]


@app.post("/api/skill-groups", status_code=201)
def create_skill_group(payload: SkillGroupInput, db: Session = Depends(get_db)):
    require_workspace(db)
    normalized = re.sub(r"\s+", " ", payload.display_name).strip().lower()
    if not normalized:
        raise HTTPException(422, "技能分组名称不能为空")
    item = SkillGroup(
        workspace_id=WORKSPACE_ID,
        code=payload.code.strip(),
        display_name=payload.display_name.strip(),
        normalized_name=normalized,
        sort_order=payload.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "code": item.code,
        "display_name": item.display_name,
        "sort_order": item.sort_order,
        "status": item.status,
    }


@app.get("/api/facts")
def list_facts(
    category_code: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    query = select(FactRecord).where(FactRecord.workspace_id == WORKSPACE_ID)
    if status:
        if status not in {"active", "archived", "recycled", "purged"}:
            raise HTTPException(422, "资料状态不受支持")
        query = query.where(FactRecord.status == status)
    else:
        query = query.where(FactRecord.status == "active")
    if category_code:
        query = query.where(
            FactRecord.category_code == checked_fact_category(category_code)
        )
    if q:
        query = query.where(FactRecord.title.contains(q))
    if tag:
        query = query.join(FactTag).join(Tag).where(
            FactTag.workspace_id == WORKSPACE_ID,
            Tag.normalized_name == tag.strip().lower(),
            Tag.status == "active",
        )
    return [
        fact_response(db, item)
        for item in db.scalars(
            query.order_by(FactRecord.updated_at.desc())
        ).all()
    ]


@app.post("/api/facts", status_code=201)
def create_fact(payload: FactInput, db: Session = Depends(get_db)):
    require_workspace(db)
    category = checked_fact_category(payload.category_code)
    schema = (
        db.get(FactSchemaVersion, payload.schema_version_id)
        if payload.schema_version_id
        else db.scalar(
            select(FactSchemaVersion).where(
                FactSchemaVersion.category_code == category,
                FactSchemaVersion.status == "published",
            )
        )
    )
    if schema is None or schema.category_code != category:
        raise HTTPException(422, "资料字段结构不存在")
    fields = checked_fact_details(db, category, payload.fields, schema.id)
    if category == "basics":
        exists = db.scalar(
            select(FactRecord.id).where(
                FactRecord.workspace_id == WORKSPACE_ID,
                FactRecord.category_code == "basics",
                FactRecord.status.in_(["active", "archived", "recycled"]),
            )
        )
        if exists:
            raise HTTPException(409, "个人档案已存在，请直接编辑现有档案")
    business_key = business_key_for(category, payload.title, fields)
    duplicate = db.scalar(
        select(FactRecord.id).where(
            FactRecord.workspace_id == WORKSPACE_ID,
            FactRecord.category_code == category,
            FactRecord.business_key == business_key,
            FactRecord.status.in_(["active", "archived", "recycled"]),
        )
    )
    if duplicate:
        raise HTTPException(409, "已存在业务身份相同的资料")
    item = FactRecord(
        workspace_id=WORKSPACE_ID,
        category_code=category,
        schema_version_id=schema.id,
        title=payload.title.strip(),
        business_key=business_key,
        source_note=payload.source_note.strip(),
        status="active",
    )
    db.add(item)
    db.flush()
    replace_fact_details(db, item, fields)
    replace_fact_tags(db, WORKSPACE_ID, item.id, payload.tags)
    replace_experience_skills(
        db, WORKSPACE_ID, item.id, category, payload.skill_ids
    )
    write_fact_audit(
        db,
        item,
        "created",
        after=fact_audit_snapshot(db, item),
        changed_fields=sorted(payload.model_dump()),
    )
    db.commit()
    db.refresh(item)
    return fact_response(db, item)


@app.get("/api/facts/{fact_id}")
def get_fact(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, FactRecord, fact_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    return fact_response(db, item)


@app.patch("/api/facts/{fact_id}")
def update_fact(
    fact_id: int,
    payload: FactPatchInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, FactRecord, fact_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    before = fact_audit_snapshot(db, item)
    current_fields = before["fields"]
    content_changed = payload.fields is not None or payload.title is not None
    fields = (
        checked_fact_details(
            db,
            item.category_code,
            payload.fields,
            item.schema_version_id,
        )
        if payload.fields is not None
        else current_fields
    )
    if payload.title is not None:
        item.title = payload.title.strip()
    if payload.source_note is not None:
        item.source_note = payload.source_note.strip()
    if payload.status is not None:
        ensure_fact_status(db, item, payload.status)
        if (
            payload.status == "active"
            and item.category_code == "basics"
            and item.status != "active"
        ):
            exists = db.scalar(
                select(FactRecord.id).where(
                    FactRecord.workspace_id == WORKSPACE_ID,
                    FactRecord.category_code == "basics",
                    FactRecord.status.in_(["active", "archived", "recycled"]),
                    FactRecord.id != item.id,
                )
            )
            if exists:
                raise HTTPException(409, "已有其他有效个人档案")
    if payload.status == "purged":
        _purge_fact_rows(db, item)
    if payload.title is not None or payload.fields is not None:
        item.business_key = business_key_for(
            item.category_code,
            item.title,
            fields,
            existing=item.business_key,
        )
        duplicate = db.scalar(
            select(FactRecord.id).where(
                FactRecord.workspace_id == item.workspace_id,
                FactRecord.category_code == item.category_code,
                FactRecord.business_key == item.business_key,
                FactRecord.status.in_(["active", "archived", "recycled"]),
                FactRecord.id != item.id,
            )
        )
        if duplicate:
            db.rollback()
            raise HTTPException(409, "已存在业务身份相同的资料")
    if payload.fields is not None:
        replace_fact_details(db, item, fields)
    if payload.tags is not None:
        replace_fact_tags(db, WORKSPACE_ID, item.id, payload.tags)
    if payload.skill_ids is not None:
        replace_experience_skills(
            db,
            WORKSPACE_ID,
            item.id,
            item.category_code,
            payload.skill_ids,
        )
    if payload.status is not None:
        item.status = payload.status
        if payload.status == "active":
            item.archived_at = None
            item.recycled_at = None
        elif payload.status == "archived":
            item.archived_at = now()
        elif payload.status == "recycled":
            item.recycled_at = now()
        elif payload.status == "purged":
            item.purged_at = now()
    item.updated_at = now_utc()
    after = fact_audit_snapshot(db, item)
    action = (
        "recycled"
        if payload.status == "recycled"
        else "archived"
        if payload.status == "archived"
        else "restored"
        if payload.status == "active" and before["status"] != "active"
        else "purged"
        if payload.status == "purged"
        else "updated"
    )
    write_fact_audit(
        db,
        item,
        action,
        before=before,
        after=after,
        changed_fields=[
            key
            for key in before
            if before.get(key) != after.get(key)
        ],
    )
    if content_changed or item.status in {"archived", "recycled"}:
        _mark_fact_sources(db, item)
    db.commit()
    db.refresh(item)
    return fact_response(db, item)


def _mark_fact_sources(db: Session, item: FactRecord) -> None:
    for ref in db.scalars(
        select(ResumeFactUse).where(
            ResumeFactUse.workspace_id == WORKSPACE_ID,
            ResumeFactUse.fact_id == item.id,
        )
    ).all():
        exists = db.scalar(
            select(PendingIssue.id).where(
                PendingIssue.workspace_id == WORKSPACE_ID,
                PendingIssue.resume_id == ref.resume_id,
                PendingIssue.fact_id == item.id,
                PendingIssue.section_code == ref.section_code,
                PendingIssue.block_key == ref.block_key,
                PendingIssue.status == "open",
            )
        )
        if exists:
            continue
        db.add(
            PendingIssue(
                workspace_id=WORKSPACE_ID,
                resume_id=ref.resume_id,
                fact_id=item.id,
                section_code=ref.section_code,
                block_key=ref.block_key,
                kind=(
                    "source_recycled"
                    if item.status == "recycled"
                    else "source_changed"
                ),
                message=f"来源资料“{item.title}”已{item.status}",
            )
        )


def _purge_fact_rows(db: Session, item: FactRecord) -> None:
    referenced = db.scalar(
        select(ResumeFactUse.id).where(
            ResumeFactUse.workspace_id == WORKSPACE_ID,
            ResumeFactUse.fact_id == item.id,
        ).limit(1)
    )
    historical = db.scalar(
        select(ResumeVersion).join(
            ResumeVersionFactSnapshot,
            ResumeVersionFactSnapshot.resume_version_id == ResumeVersion.id,
        ).where(
            ResumeVersionFactSnapshot.workspace_id == WORKSPACE_ID,
            ResumeVersionFactSnapshot.fact_id == item.id,
        ).limit(1)
    )
    children = db.scalar(
        select(FactAchievementDetail.fact_id).where(
            FactAchievementDetail.workspace_id == WORKSPACE_ID,
            FactAchievementDetail.experience_fact_id == item.id,
        ).limit(1)
    )
    if referenced or historical or children:
        raise HTTPException(409, "该资料仍有当前、历史或成果引用，不能清理")
    db.execute(delete(FactEvidence).where(FactEvidence.fact_id == item.id))
    db.execute(delete(FactTag).where(FactTag.fact_id == item.id))
    db.execute(
        delete(ExperienceSkillLink).where(
            or_(
                ExperienceSkillLink.experience_fact_id == item.id,
                ExperienceSkillLink.skill_fact_id == item.id,
            )
        )
    )
    for model in (
        FactBasicsDetail,
        FactEducationDetail,
        FactExperienceDetail,
        FactSkillDetail,
        FactAchievementDetail,
    ):
        db.execute(delete(model).where(model.fact_id == item.id))
    item.title = "[purged]"
    item.business_key = None
    item.source_note = None


@app.get("/api/facts/{fact_id}/audits")
def fact_audits(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    fact = get_or_404(db, FactRecord, fact_id)
    return [
        {
            "id": item.id,
            "action": item.action,
            "schema_version_id": item.schema_version_id,
            "changed_fields": json_value(item.changed_fields, []),
            "before_values": json_value(item.before_values, {}),
            "after_values": json_value(item.after_values, {}),
            "related_fact_ids": json_value(item.related_fact_ids, []),
            "reason": item.reason,
            "created_at": item.created_at,
        }
        for item in db.scalars(
            select(FactAuditEvent)
            .where(
                FactAuditEvent.workspace_id == fact.workspace_id,
                FactAuditEvent.fact_id == fact_id,
            )
            .order_by(FactAuditEvent.created_at.desc(), FactAuditEvent.id.desc())
        ).all()
    ]


@app.delete("/api/facts/{fact_id}")
def delete_fact(fact_id: int, db: Session = Depends(get_db)):
    payload = FactPatchInput(status="recycled")
    return update_fact(fact_id, payload, db)


@app.post("/api/facts/{fact_id}/restore")
def restore_fact(fact_id: int, db: Session = Depends(get_db)):
    return update_fact(fact_id, FactPatchInput(status="active"), db)


@app.delete("/api/facts/{fact_id}/purge")
def purge_fact(
    fact_id: int,
    confirm: bool = Query(False),
    db: Session = Depends(get_db),
):
    if not confirm:
        raise HTTPException(422, "清理为匿名墓碑需要二次确认")
    require_workspace(db)
    item = get_or_404(db, FactRecord, fact_id)
    if item.status != "recycled":
        raise HTTPException(409, "仅回收站中的资料可以清理")
    return update_fact(fact_id, FactPatchInput(status="purged"), db)


@app.get("/api/facts/{fact_id}/evidence")
def list_fact_evidence(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    fact = get_or_404(db, FactRecord, fact_id)
    return [
        evidence_response(item)
        for item in db.scalars(
            select(Evidence)
            .join(FactEvidence)
            .where(
                FactEvidence.workspace_id == WORKSPACE_ID,
                FactEvidence.fact_id == fact_id,
            )
            .order_by(Evidence.created_at.desc())
        ).all()
    ]


@app.get("/api/evidence")
def list_evidence(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    query = select(Evidence).where(Evidence.workspace_id == WORKSPACE_ID)
    if status:
        if status not in {"active", "invalid", "archived"}:
            raise HTTPException(422, "证据状态不受支持")
        query = query.where(Evidence.status == status)
    return [
        evidence_response(item)
        for item in db.scalars(query.order_by(Evidence.created_at.desc())).all()
    ]


@app.post("/api/evidence", status_code=201)
def create_evidence(payload: EvidenceInput, db: Session = Depends(get_db)):
    require_workspace(db)
    if payload.kind not in {"link", "note"}:
        raise HTTPException(422, "只能创建链接或说明证据")
    if payload.kind == "link" and not payload.url.startswith(
        ("https://", "http://")
    ):
        raise HTTPException(422, "证据链接必须以 http:// 或 https:// 开头")
    if payload.kind == "note" and not payload.note.strip():
        raise HTTPException(422, "说明证据必须包含内容")
    if payload.fact_id is not None:
        fact = get_or_404(db, FactRecord, payload.fact_id)
        if fact.workspace_id != WORKSPACE_ID:
            raise HTTPException(404, "对象不存在")
    item = Evidence(
        workspace_id=WORKSPACE_ID,
        kind=payload.kind,
        title=payload.title.strip()
        or (payload.url.strip() if payload.kind == "link" else "说明材料"),
        url=payload.url.strip() if payload.kind == "link" else "",
        note=payload.note.strip(),
    )
    db.add(item)
    db.flush()
    write_evidence_audit(
        db,
        item,
        "created",
        after=evidence_response(item),
    )
    if payload.fact_id is not None:
        db.add(
            FactEvidence(
                workspace_id=WORKSPACE_ID,
                fact_id=payload.fact_id,
                evidence_id=item.id,
                relation_note=payload.relation_note,
            )
        )
    db.commit()
    db.refresh(item)
    return evidence_response(item)


@app.get("/api/evidence/{evidence_id}")
def get_evidence(evidence_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, Evidence, evidence_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    return evidence_response(item)


@app.post("/api/evidence/upload", status_code=201)
async def upload_evidence(
    fact_id: int | None = Form(None),
    title: str = Form(""),
    note: str = Form(""),
    relation_note: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    require_workspace(db)
    if fact_id is not None:
        fact = get_or_404(db, FactRecord, fact_id)
        if fact.workspace_id != WORKSPACE_ID:
            raise HTTPException(404, "对象不存在")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EVIDENCE_SUFFIXES:
        raise HTTPException(422, "仅支持 PDF、PNG、JPEG 和 WEBP 证据文件")
    body = await file.read()
    if not body or len(body) > MAX_EVIDENCE_SIZE:
        raise HTTPException(422, "证据文件不能为空且不能超过 10 MB")
    item = save_file_evidence(
        db,
        body=body,
        suffix=suffix,
        filename=file.filename or "",
        mime_type=file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream",
        title=title,
        note=note,
    )
    if fact_id is not None:
        exists = db.scalar(
            select(FactEvidence.id).where(
                FactEvidence.workspace_id == WORKSPACE_ID,
                FactEvidence.fact_id == fact_id,
                FactEvidence.evidence_id == item.id,
            )
        )
        if exists is None:
            db.add(
                FactEvidence(
                    workspace_id=WORKSPACE_ID,
                    fact_id=fact_id,
                    evidence_id=item.id,
                    relation_note=relation_note,
                )
            )
    db.commit()
    db.refresh(item)
    return evidence_response(item)


@app.patch("/api/evidence/{evidence_id}")
def update_evidence(
    evidence_id: int,
    payload: EvidenceUpdateInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, Evidence, evidence_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    before = evidence_response(item)
    changed_fields: list[str] = []
    action = "updated_metadata"
    if payload.title is not None and payload.title.strip() != item.title:
        item.title = payload.title.strip()
        changed_fields.append("title")
    if payload.status is not None:
        if payload.status not in {"active", "invalid", "archived"}:
            raise HTTPException(422, "证据状态不受支持")
        if payload.status != item.status:
            item.status = payload.status
            changed_fields.append("status")
            action = {
                "invalid": "marked_invalid",
                "active": "marked_active",
                "archived": "archived",
            }[payload.status]
    if changed_fields:
        item.updated_at = now_utc()
        write_evidence_audit(
            db,
            item,
            action,
            changed_fields=changed_fields,
            before=before,
            after=evidence_response(item),
            reason=payload.reason,
        )
        sync_evidence_changes(db, item)
    db.commit()
    db.refresh(item)
    return evidence_response(item)


@app.get("/api/evidence/{evidence_id}/audits")
def evidence_audits(evidence_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, Evidence, evidence_id)
    return [
        {
            "id": event.id,
            "action": event.action,
            "changed_fields": json_value(event.changed_fields, []),
            "before_values": json_value(event.before_values, {}),
            "after_values": json_value(event.after_values, {}),
            "reason": event.reason,
            "created_at": event.created_at,
        }
        for event in db.scalars(
            select(EvidenceAuditEvent)
            .where(
                EvidenceAuditEvent.workspace_id == item.workspace_id,
                EvidenceAuditEvent.evidence_id == evidence_id,
            )
            .order_by(
                EvidenceAuditEvent.created_at.desc(),
                EvidenceAuditEvent.id.desc(),
            )
        ).all()
    ]


@app.get("/api/evidence/{evidence_id}/file")
def preview_evidence_file(evidence_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, Evidence, evidence_id)
    if item.workspace_id != WORKSPACE_ID or item.kind != "file" or not item.storage_key:
        raise HTTPException(404, "证据文件不存在")
    root = ATTACHMENTS_DIR.resolve()
    path = (root / item.storage_key).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(404, "证据文件不存在")
    return FileResponse(
        path,
        media_type=item.mime_type or "application/octet-stream",
        filename=item.filename or path.name,
        content_disposition_type="inline",
    )


@app.delete("/api/evidence/{evidence_id}")
def archive_evidence(evidence_id: int, db: Session = Depends(get_db)):
    return update_evidence(
        evidence_id,
        EvidenceUpdateInput(status="archived", reason="用户归档"),
        db,
    )


@app.post("/api/evidence/{evidence_id}/restore")
def restore_evidence(evidence_id: int, db: Session = Depends(get_db)):
    return update_evidence(
        evidence_id,
        EvidenceUpdateInput(status="active", reason="用户恢复"),
        db,
    )


@app.get("/api/facts/{fact_id}/profile-photo")
def get_profile_photo(fact_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    fact = get_or_404(db, FactRecord, fact_id)
    if fact.workspace_id != WORKSPACE_ID or fact.category_code != "basics":
        raise HTTPException(404, "个人档案不存在")
    photos = db.scalars(
        select(ProfilePhoto)
        .where(
            ProfilePhoto.workspace_id == WORKSPACE_ID,
            ProfilePhoto.basics_fact_id == fact.id,
        )
        .order_by(ProfilePhoto.created_at.desc(), ProfilePhoto.id.desc())
    ).all()
    current = None
    history = []
    for photo in photos:
        evidence = db.get(Evidence, photo.evidence_id)
        if evidence is None:
            continue
        payload = profile_photo_response(photo, evidence)
        if photo.status == "active":
            current = payload
        else:
            history.append(payload)
    return {"current": current, "history": history}


@app.post("/api/facts/{fact_id}/profile-photo", status_code=201)
async def upload_profile_photo(
    fact_id: int,
    file: UploadFile = File(...),
    title: str = Form("档案照片"),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    require_workspace(db)
    fact = checked_profile_photo_fact(db, fact_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_PROFILE_PHOTO_SUFFIXES:
        raise HTTPException(422, "仅支持 PNG、JPEG、JFIF 和 WebP 档案照片")
    body = await file.read()
    if not body or len(body) > MAX_PROFILE_PHOTO_SIZE:
        raise HTTPException(422, "档案照片不能为空且不能超过 5 MB")
    mime_type, normalized_suffix = profile_photo_mime(body, suffix)
    evidence = save_file_evidence(
        db,
        body=body,
        suffix=normalized_suffix,
        filename=file.filename or f"profile-photo{normalized_suffix}",
        mime_type=mime_type,
        title=title or "档案照片",
        note=note,
    )
    previous = active_profile_photo(db, fact.id)
    if previous is not None and previous.evidence_id == evidence.id:
        db.commit()
        return profile_photo_response(previous, evidence)

    target = db.scalar(
        select(ProfilePhoto).where(
            ProfilePhoto.workspace_id == WORKSPACE_ID,
            ProfilePhoto.basics_fact_id == fact.id,
            ProfilePhoto.evidence_id == evidence.id,
        )
    )
    before_id = previous.id if previous is not None else None
    if previous is not None:
        previous.status = "archived"
        previous.archived_at = now_utc()
        db.flush()
    if target is None:
        target = ProfilePhoto(
            workspace_id=WORKSPACE_ID,
            basics_fact_id=fact.id,
            basics_category_code="basics",
            evidence_id=evidence.id,
            status="active",
        )
        db.add(target)
    else:
        target.status = "active"
        target.archived_at = None
    fact.updated_at = now_utc()
    db.flush()
    sync_profile_photo_to_working_copies(db, fact.id)
    write_fact_audit(
        db,
        fact,
        "evidence_changed",
        before={"profile_photo_id": before_id},
        after={"profile_photo_id": target.id},
        changed_fields=["profile_photo_id"],
        reason="上传并替换档案照片",
    )
    db.commit()
    db.refresh(target)
    db.refresh(evidence)
    return profile_photo_response(target, evidence)


@app.delete("/api/profile-photos/{photo_id}")
def remove_profile_photo(photo_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    photo = get_or_404(db, ProfilePhoto, photo_id)
    if photo.workspace_id != WORKSPACE_ID or photo.status != "active":
        raise HTTPException(404, "当前档案照片不存在")
    fact = get_or_404(db, FactRecord, photo.basics_fact_id)
    photo.status = "archived"
    photo.archived_at = now_utc()
    fact.updated_at = now_utc()
    db.flush()
    sync_profile_photo_to_working_copies(db, fact.id)
    write_fact_audit(
        db,
        fact,
        "evidence_changed",
        before={"profile_photo_id": photo.id},
        after={"profile_photo_id": None},
        changed_fields=["profile_photo_id"],
        reason="移除当前档案照片",
    )
    db.commit()
    evidence = db.get(Evidence, photo.evidence_id)
    return profile_photo_response(photo, evidence)


@app.post("/api/profile-photos/{photo_id}/restore")
def restore_profile_photo(photo_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    photo = get_or_404(db, ProfilePhoto, photo_id)
    if photo.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "档案照片不存在")
    if photo.status == "active":
        evidence = db.get(Evidence, photo.evidence_id)
        return profile_photo_response(photo, evidence)
    current = active_profile_photo(db, photo.basics_fact_id)
    before_id = current.id if current is not None else None
    if current is not None:
        current.status = "archived"
        current.archived_at = now_utc()
        db.flush()
    photo.status = "active"
    photo.archived_at = None
    fact = get_or_404(db, FactRecord, photo.basics_fact_id)
    fact.updated_at = now_utc()
    db.flush()
    sync_profile_photo_to_working_copies(db, fact.id)
    write_fact_audit(
        db,
        fact,
        "evidence_changed",
        before={"profile_photo_id": before_id},
        after={"profile_photo_id": photo.id},
        changed_fields=["profile_photo_id"],
        reason="恢复历史档案照片",
    )
    db.commit()
    evidence = db.get(Evidence, photo.evidence_id)
    return profile_photo_response(photo, evidence)


@app.get("/api/requirement-profiles")
def list_profiles(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    query = select(RequirementProfile).where(
        RequirementProfile.workspace_id == WORKSPACE_ID
    )
    query = query.where(
        RequirementProfile.status == (status or "active")
    )
    profiles = db.scalars(
        query.order_by(RequirementProfile.updated_at.desc())
    ).all()
    active_resumes = {
        item.requirement_profile_id: item.id
        for item in db.scalars(
            select(Resume).where(
                Resume.workspace_id == WORKSPACE_ID,
                Resume.status == "active",
            )
        ).all()
    }
    opportunity_counts = {
        item.requirement_profile_id: item.count
        for item in db.execute(
            select(
                JobOpportunity.requirement_profile_id,
                func.count().label("count"),
            )
            .where(
                JobOpportunity.workspace_id == WORKSPACE_ID,
                JobOpportunity.status == "active",
            )
            .group_by(JobOpportunity.requirement_profile_id)
        ).all()
    }
    return [
        {
            **serialize_profile(item),
            "active_resume_id": active_resumes.get(item.id),
            "opportunity_count": opportunity_counts.get(item.id, 0),
        }
        for item in profiles
    ]


@app.post("/api/requirement-profiles", status_code=201)
def create_profile(payload: ProfileInput, db: Session = Depends(get_db)):
    require_workspace(db)
    item = RequirementProfile(workspace_id=WORKSPACE_ID)
    apply_profile_values(item, payload.model_dump())
    db.add(item)
    db.flush()
    add_audit(
        db,
        WORKSPACE_ID,
        item.id,
        actor_id(db),
        "created",
        after=serialize_profile(item),
    )
    db.commit()
    db.refresh(item)
    return serialize_profile(item)


@app.get("/api/requirement-profiles/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, RequirementProfile, profile_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    return serialize_profile(item)


@app.patch("/api/requirement-profiles/{profile_id}")
def update_profile(
    profile_id: int,
    payload: ProfilePatchInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, RequirementProfile, profile_id)
    before = serialize_profile(item)
    values = payload.model_dump(exclude_unset=True, exclude={"status"})
    changed = apply_profile_values(item, values)
    status = payload.status
    if status is not None and status != item.status:
        transitions = {
            "active": {"archived", "recycled"},
            "archived": {"active", "recycled"},
            "recycled": {"active", "archived", "purged"},
            "purged": set(),
        }
        if status not in transitions or status not in transitions[item.status]:
            raise HTTPException(409, "画像状态转换无效")
        if status == "purged":
            history = db.scalar(
                select(Resume.id).where(
                    Resume.workspace_id == WORKSPACE_ID,
                    Resume.requirement_profile_id == item.id,
                    Resume.status != "purged",
                ).limit(1)
            )
            if history:
                raise HTTPException(409, "画像仍关联正式简历历史，不能清理")
        item.status = status
        if status == "active":
            item.archived_at = None
            item.recycled_at = None
        elif status == "archived":
            item.archived_at = now()
        elif status == "recycled":
            item.recycled_at = now()
        elif status == "purged":
            item.purged_at = now()
            item.name = "[purged]"
            item.role_direction = ""
            item.core_requirements = "[]"
            item.general_requirements = ""
            item.responsibilities = ""
            item.resume_strategy = ""
            item.raw_jd = ""
            item.source_note = ""
        changed = [*changed, "status"]
        action = {
            "active": "restored",
            "archived": "archived",
            "recycled": "recycled",
            "purged": "purged",
        }[status]
    else:
        action = "updated"
    if changed:
        add_audit(
            db,
            WORKSPACE_ID,
            item.id,
            actor_id(db),
            action,
            changed_fields=sorted(set(changed)),
            before=before,
            after=serialize_profile(item),
        )
    if values:
        for resume in db.scalars(
            select(Resume).where(
                Resume.workspace_id == WORKSPACE_ID,
                Resume.requirement_profile_id == item.id,
                Resume.status == "active",
            )
        ).all():
            exists = db.scalar(
                select(PendingIssue.id).where(
                    PendingIssue.profile_id == item.id,
                    PendingIssue.resume_id == resume.id,
                    PendingIssue.kind == "profile_changed",
                    PendingIssue.status == "open",
                )
            )
            if exists is None:
                db.add(
                    PendingIssue(
                        workspace_id=WORKSPACE_ID,
                        profile_id=item.id,
                        resume_id=resume.id,
                        kind="profile_changed",
                        message=f"岗位画像“{item.name}”已更新",
                    )
                )
    db.commit()
    db.refresh(item)
    return serialize_profile(item)


@app.delete("/api/requirement-profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    return update_profile(
        profile_id,
        ProfilePatchInput(status="recycled"),
        db,
    )


@app.post("/api/requirement-profiles/{profile_id}/restore")
def restore_profile(profile_id: int, db: Session = Depends(get_db)):
    return update_profile(
        profile_id,
        ProfilePatchInput(status="active"),
        db,
    )


@app.get("/api/requirement-profiles/{profile_id}/audits")
def profile_audits(profile_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, RequirementProfile, profile_id)
    return [
        {
            "id": event.id,
            "action": event.action,
            "changed_fields": json_value(event.changed_fields_json, []),
            "before_values": json_value(event.before_values_json, {}),
            "after_values": json_value(event.after_values_json, {}),
            "related_profile_ids": json_value(
                event.related_profile_ids_json, []
            ),
            "reason": event.reason,
            "created_at": event.created_at,
        }
        for event in db.scalars(
            select(ProfileAuditEvent)
            .where(ProfileAuditEvent.profile_id == profile_id)
            .order_by(
                ProfileAuditEvent.created_at.desc(),
                ProfileAuditEvent.id.desc(),
            )
        ).all()
    ]


@app.get("/api/opportunities")
def list_opportunities(
    profile_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    query = select(JobOpportunity).where(
        JobOpportunity.workspace_id == WORKSPACE_ID
    )
    if profile_id is not None:
        query = query.where(
            JobOpportunity.requirement_profile_id == profile_id
        )
    query = query.where(JobOpportunity.status == (status or "active"))
    return [
        opportunity_response(item)
        for item in db.scalars(
            query.order_by(JobOpportunity.created_at.desc())
        ).all()
    ]


@app.post("/api/opportunities", status_code=201)
def create_opportunity(
    payload: OpportunityInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    profile = get_or_404(
        db, RequirementProfile, payload.requirement_profile_id
    )
    if profile.workspace_id != WORKSPACE_ID or profile.status == "purged":
        raise HTTPException(422, "岗位画像不可用")
    item = JobOpportunity(
        workspace_id=WORKSPACE_ID,
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    add_audit(
        db,
        WORKSPACE_ID,
        profile.id,
        actor_id(db),
        "opportunity_changed",
        related_profile_ids=[profile.id],
        after={"opportunity_id": item.id},
    )
    db.commit()
    db.refresh(item)
    return opportunity_response(item)


@app.patch("/api/opportunities/{opportunity_id}")
def update_opportunity(
    opportunity_id: int,
    payload: OpportunityPatchInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, JobOpportunity, opportunity_id)
    before = opportunity_response(item)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = now_utc()
    after = opportunity_response(item)
    add_audit(
        db,
        WORKSPACE_ID,
        item.requirement_profile_id,
        actor_id(db),
        "opportunity_changed",
        changed_fields=[
            key for key in before if before.get(key) != after.get(key)
        ],
        before=before,
        after=after,
        related_profile_ids=[item.requirement_profile_id],
    )
    db.commit()
    db.refresh(item)
    return opportunity_response(item)


@app.delete("/api/opportunities/{opportunity_id}")
def delete_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    return update_opportunity(
        opportunity_id,
        OpportunityPatchInput(status="recycled"),
        db,
    )


@app.get("/api/search")
def global_search(q: str, db: Session = Depends(get_db)):
    require_workspace(db)
    keyword = q.strip()
    if not keyword:
        return []
    facts = db.scalars(
        select(FactRecord)
        .where(
            FactRecord.workspace_id == WORKSPACE_ID,
            FactRecord.title.contains(keyword),
        )
        .order_by(FactRecord.updated_at.desc())
        .limit(5)
    ).all()
    profiles = db.scalars(
        select(RequirementProfile)
        .where(
            RequirementProfile.workspace_id == WORKSPACE_ID,
            or_(
                RequirementProfile.name.contains(keyword),
                RequirementProfile.role_direction.contains(keyword),
            ),
        )
        .order_by(RequirementProfile.updated_at.desc())
        .limit(5)
    ).all()
    opportunities = db.scalars(
        select(JobOpportunity)
        .where(
            JobOpportunity.workspace_id == WORKSPACE_ID,
            or_(
                JobOpportunity.company.contains(keyword),
                JobOpportunity.title.contains(keyword),
            ),
        )
        .limit(5)
    ).all()
    resumes = db.scalars(
        select(Resume)
        .where(
            Resume.workspace_id == WORKSPACE_ID,
            Resume.display_name.contains(keyword),
        )
        .limit(5)
    ).all()
    evidence_rows = db.scalars(
        select(Evidence)
        .where(
            Evidence.workspace_id == WORKSPACE_ID,
            or_(
                Evidence.title.contains(keyword),
                Evidence.filename.contains(keyword),
            ),
        )
        .limit(5)
    ).all()
    results: list[dict] = []
    for item in facts:
        results.append(
            {
                "type": "fact",
                "id": item.id,
                "title": item.title,
                "subtitle": FACT_CATEGORY_LABELS[item.category_code],
                "status": item.status,
                "updated_at": item.updated_at,
                "payload": fact_response(db, item),
            }
        )
    for item in evidence_rows:
        results.append(
            {
                "type": "evidence",
                "id": item.id,
                "title": item.title,
                "subtitle": item.filename or item.url or "说明材料",
                "status": item.status,
                "updated_at": item.updated_at,
                "payload": evidence_response(item),
            }
        )
    for item in profiles:
        results.append(
            {
                "type": "profile",
                "id": item.id,
                "title": item.name,
                "subtitle": item.role_direction or "岗位方向待补充",
                "status": item.status,
                "updated_at": item.updated_at,
                "payload": serialize_profile(item),
            }
        )
    for item in opportunities:
        results.append(
            {
                "type": "opportunity",
                "id": item.id,
                "title": f"{item.company} · {item.title}".strip(" ·"),
                "subtitle": "招聘机会",
                "status": item.status,
                "updated_at": item.updated_at,
                "payload": {
                    "profile_id": item.requirement_profile_id
                },
            }
        )
    for item in resumes:
        results.append(
            {
                "type": "resume",
                "id": item.id,
                "title": item.display_name,
                "subtitle": "正式简历",
                "status": item.status,
                "updated_at": item.updated_at,
                "payload": resume_row(db, item),
            }
        )
    return results


@app.get("/api/templates")
def templates(db: Session = Depends(get_db)):
    require_workspace(db)
    rows = available_templates(db)
    result = [template_response(item) for item in rows]
    db.commit()
    return result


@app.get("/api/template-preferences")
def get_template_preferences(db: Session = Depends(get_db)):
    require_workspace(db)
    item = db.get(TemplatePreference, WORKSPACE_ID)
    if item is None:
        item = TemplatePreference(workspace_id=WORKSPACE_ID)
        db.add(item)
        db.commit()
        db.refresh(item)
    return {
        "workspace_id": item.workspace_id,
        "default_template_id": item.default_template_id,
        "last_selected_template_id": item.last_selected_template_id,
        "updated_at": item.updated_at,
    }


@app.patch("/api/template-preferences")
def update_template_preferences(
    payload: TemplatePreferenceInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = db.get(TemplatePreference, WORKSPACE_ID)
    if item is None:
        item = TemplatePreference(workspace_id=WORKSPACE_ID)
        db.add(item)
        db.flush()
    for field in ("default_template_id", "last_selected_template_id"):
        value = getattr(payload, field)
        if value is not None:
            template = resolve_template(
                db, template_id=value, workspace_id=WORKSPACE_ID
            )
            setattr(item, field, template.id)
    item.updated_at = now_utc()
    db.commit()
    db.refresh(item)
    return {
        "workspace_id": item.workspace_id,
        "default_template_id": item.default_template_id,
        "last_selected_template_id": item.last_selected_template_id,
        "updated_at": item.updated_at,
    }


@app.get("/api/linked-resumes")
def list_linked_resumes(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    query = select(LinkedResume).where(
        LinkedResume.workspace_id == WORKSPACE_ID
    )
    if status:
        query = query.where(LinkedResume.status == status)
    return [
        {
            "id": item.id,
            "profile_id": item.requirement_profile_id,
            "template_id": item.template_id,
            "selection": json_value(item.selection_json, {}),
            "status": item.status,
            "converted_resume_id": item.converted_resume_id,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in db.scalars(
            query.order_by(LinkedResume.updated_at.desc())
        ).all()
    ]


@app.post("/api/linked-resumes", status_code=201)
def create_linked_resume(
    payload: LinkedResumeInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = create_draft(
        db,
        WORKSPACE_ID,
        payload.profile_id,
        payload.template_id,
    )
    item.selection_json = dump(payload.selection)
    preference = db.get(TemplatePreference, WORKSPACE_ID)
    if preference:
        preference.last_selected_template_id = item.template_id
    db.commit()
    return {
        "id": item.id,
        "profile_id": item.requirement_profile_id,
        "template_id": item.template_id,
        "selection": payload.selection,
        "status": item.status,
    }


@app.get("/api/linked-resumes/{linked_id}")
def get_linked_resume(linked_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, LinkedResume, linked_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    profile = get_or_404(
        db, RequirementProfile, item.requirement_profile_id
    )
    selection = json_value(item.selection_json, {})
    from .services import build_resume_content

    return {
        "id": item.id,
        "profile": serialize_profile(profile),
        "selection": selection,
        "preview": build_resume_content(db, profile, selection),
        "template": template_info_response(db, item.template_id),
        "status": item.status,
        "converted_resume_id": item.converted_resume_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@app.patch("/api/linked-resumes/{linked_id}")
def update_linked_resume(
    linked_id: int,
    payload: SelectionInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, LinkedResume, linked_id)
    if item.status != "open":
        raise HTTPException(409, "已转化或放弃的临时简历不可修改")
    if payload.template_id is not None:
        item.template_id = resolve_template(
            db, template_id=payload.template_id, workspace_id=WORKSPACE_ID
        ).id
    if payload.selection is not None:
        item.selection_json = dump(payload.selection)
    item.updated_at = now_utc()
    db.commit()
    return get_linked_resume(linked_id, db)


@app.post("/api/linked-resumes/{linked_id}/convert", status_code=201)
def convert_linked_resume(linked_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, LinkedResume, linked_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    resume = convert_draft(db, item)
    db.commit()
    db.refresh(resume)
    return {
        "resume_id": resume.id,
        "version": 1,
        "linked_resume_id": item.id,
    }


@app.get("/api/resumes")
def list_resumes(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    query = select(Resume).where(Resume.workspace_id == WORKSPACE_ID)
    query = query.where(Resume.status == (status or "active"))
    return [
        resume_row(db, item)
        for item in db.scalars(
            query.order_by(Resume.updated_at.desc())
        ).all()
    ]


@app.post("/api/resumes", status_code=201)
def create_resume(
    payload: ResumeCreateInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    if payload.linked_resume_id is not None:
        draft = get_or_404(db, LinkedResume, payload.linked_resume_id)
    elif payload.profile_id is not None:
        draft = create_draft(
            db,
            WORKSPACE_ID,
            payload.profile_id,
            payload.template_id,
        )
        if payload.selection is not None:
            draft.selection_json = dump(payload.selection)
    else:
        raise HTTPException(422, "linked_resume_id 或 profile_id 必须提供一个")
    resume = convert_draft(db, draft)
    db.commit()
    db.refresh(resume)
    return resume_row(db, resume)


@app.get("/api/resumes/{resume_id}")
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    item = get_or_404(db, Resume, resume_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    copy = load_working_copy(db, resume_id)
    current = current_version(db, item)
    return {
        **resume_row(db, item),
        "working_copy": {
            "content": json_value(copy.content_json, {}),
            "content_state": copy.content_state,
            "evidence_sync_state": copy.evidence_sync_state,
            "baseline_state": copy.baseline_state,
            "pending_reason": copy.pending_reason,
            "base_version_id": copy.base_version_id,
            "template_id": copy.template_id,
            "updated_at": copy.updated_at,
        },
        "current": serialize_version(current) if current else None,
        "template": template_info_response(db, item.template_id),
    }


@app.patch("/api/resumes/{resume_id}")
def update_resume(
    resume_id: int,
    payload: ResumeUpdateInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, Resume, resume_id)
    if payload.display_name is not None:
        value = payload.display_name.strip()
        if not value:
            raise HTTPException(422, "简历名称不能为空")
        item.display_name = value
    if payload.status is not None and payload.status != item.status:
        transitions = {
            "active": {"archived", "recycled"},
            "archived": {"active", "recycled"},
            "recycled": {"active", "archived", "purged"},
            "purged": set(),
        }
        if (
            payload.status not in transitions
            or payload.status not in transitions[item.status]
        ):
            raise HTTPException(409, "简历状态转换无效")
        if payload.status == "active":
            active = db.scalar(
                select(Resume.id).where(
                    Resume.workspace_id == WORKSPACE_ID,
                    Resume.requirement_profile_id
                    == item.requirement_profile_id,
                    Resume.status == "active",
                    Resume.id != item.id,
                )
            )
            if active:
                raise HTTPException(
                    409,
                    "同一岗位画像已有活跃正式简历，请先归档当前简历",
                )
            item.archived_at = None
            item.recycled_at = None
        elif payload.status == "archived":
            item.archived_at = now()
        elif payload.status == "recycled":
            item.recycled_at = now()
        elif payload.status == "purged":
            item.purged_at = now()
        item.status = payload.status
    item.updated_at = now_utc()
    db.commit()
    db.refresh(item)
    return resume_row(db, item)


@app.delete("/api/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    return update_resume(
        resume_id,
        ResumeUpdateInput(status="recycled"),
        db,
    )


@app.post("/api/resumes/{resume_id}/restore")
def restore_resume(
    resume_id: int,
    replace_active: bool = Query(False),
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, Resume, resume_id)
    active = db.scalar(
        select(Resume).where(
            Resume.workspace_id == WORKSPACE_ID,
            Resume.requirement_profile_id == item.requirement_profile_id,
            Resume.status == "active",
            Resume.id != item.id,
        )
    )
    if active:
        if not replace_active:
            raise HTTPException(
                409,
                "同一岗位画像已有活跃正式简历；确认归档当前简历后可恢复",
            )
        active.status = "archived"
        active.archived_at = now()
    return update_resume(
        resume_id,
        ResumeUpdateInput(status="active"),
        db,
    )


@app.patch("/api/resumes/{resume_id}/template")
def choose_template(
    resume_id: int,
    payload: TemplateChoiceInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    resume = get_or_404(db, Resume, resume_id)
    template = resolve_template(
        db, template_id=payload.template_id, workspace_id=WORKSPACE_ID
    )
    resume.template_id = template.id
    copy = load_working_copy(db, resume.id)
    copy.template_id = template.id
    preference = db.get(TemplatePreference, WORKSPACE_ID)
    if preference:
        preference.last_selected_template_id = template.id
    db.commit()
    return {
        "template": template_info_response(db, template.id),
        "content_state": copy.content_state,
        "evidence_sync_state": copy.evidence_sync_state,
        "baseline_state": copy.baseline_state,
    }


@app.get("/api/resumes/{resume_id}/working-copy")
def get_working_copy(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    get_or_404(db, Resume, resume_id)
    copy = load_working_copy(db, resume_id)
    return {
        "resume_id": resume_id,
        "content": json_value(copy.content_json, {}),
        "content_state": copy.content_state,
        "evidence_sync_state": copy.evidence_sync_state,
        "baseline_state": copy.baseline_state,
        "base_version_id": copy.base_version_id,
        "template_id": copy.template_id,
        "pending_reason": copy.pending_reason,
        "updated_at": copy.updated_at,
    }


@app.patch("/api/resumes/{resume_id}/working-copy")
def update_working_copy(
    resume_id: int,
    payload: WorkingCopyInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    resume = get_or_404(db, Resume, resume_id)
    copy = load_working_copy(db, resume_id)
    latest = current_version(db, resume)
    if payload.expected_version_id is not None and (
        latest is None or latest.id != payload.expected_version_id
    ):
        raise HTTPException(409, "正式版本已变化，请重新载入")
    copy.content_json = dump(payload.content)
    copy.content_state = "dirty"
    copy.baseline_state = (
        "current"
        if latest and copy.base_version_id == latest.id
        else "stale"
    )
    copy.updated_at = now_utc()
    sync_references(db, resume.id, resume.workspace_id, payload.content)
    db.commit()
    return {
        "content_state": copy.content_state,
        "evidence_sync_state": copy.evidence_sync_state,
        "baseline_state": copy.baseline_state,
        "updated_at": copy.updated_at,
    }


@app.post("/api/resumes/{resume_id}/save")
def save_resume(
    resume_id: int,
    payload: SaveInput = SaveInput(),
    db: Session = Depends(get_db),
):
    require_workspace(db)
    resume = get_or_404(db, Resume, resume_id)
    version = save_working_copy(
        db,
        resume,
        payload.change_summary,
        expected_version_id=payload.expected_version_id,
    )
    db.commit()
    db.refresh(version)
    return serialize_version(version)


@app.get("/api/resumes/{resume_id}/versions")
def versions(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    get_or_404(db, Resume, resume_id)
    return [
        serialize_version(item)
        for item in db.scalars(
            select(ResumeVersion)
            .where(
                ResumeVersion.workspace_id == WORKSPACE_ID,
                ResumeVersion.resume_id == resume_id,
            )
            .order_by(ResumeVersion.version_number.desc())
        ).all()
    ]


def version_block_index(content: dict) -> dict:
    index: dict[str, dict] = {}
    for section in content.get("sections", []):
        for block in section.get("blocks", []):
            entry = {
                "section_id": section["id"],
                "section_title": section.get("title"),
                "block_id": block.get("id"),
                "title": block.get("title"),
                "content": block.get("content"),
                "fields": block.get("fields") or {},
                "display_fields": block.get("display_fields") or [],
                "origin": block.get("origin"),
                "source_refs": block.get("source_refs") or [],
                "evidence_refs": block.get("evidence_refs") or [],
            }
            index[f"{section['id']}|{block['id']}"] = entry
    return index


@app.get("/api/resumes/{resume_id}/versions/{from_number}/diff/{to_number}")
def diff_versions(
    resume_id: int,
    from_number: int,
    to_number: int,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    get_or_404(db, Resume, resume_id)
    rows = {
        item.version_number: item
        for item in db.scalars(
            select(ResumeVersion).where(
                ResumeVersion.workspace_id == WORKSPACE_ID,
                ResumeVersion.resume_id == resume_id,
                ResumeVersion.version_number.in_([from_number, to_number]),
            )
        ).all()
    }
    if from_number not in rows or to_number not in rows:
        raise HTTPException(404, "版本不存在")
    source = rows[from_number]
    target = rows[to_number]
    before_index = version_block_index(json_value(source.content_json, {}))
    after_index = version_block_index(json_value(target.content_json, {}))
    changes: list[dict] = []
    for key, after in after_index.items():
        before = before_index.get(key)
        if before is None:
            kind = "added"
        elif before != after:
            kind = "modified"
        else:
            continue
        changes.append(
            {
                "section_id": after["section_id"],
                "block_id": after["block_id"],
                "kind": kind,
                "before": before,
                "after": after,
                "source_refs_changed": (
                    (before or {}).get("source_refs") != after["source_refs"]
                ),
                "evidence_refs_changed": (
                    (before or {}).get("evidence_refs")
                    != after["evidence_refs"]
                ),
            }
        )
    for key, before in before_index.items():
        if key not in after_index:
            changes.append(
                {
                    "section_id": before["section_id"],
                    "block_id": before["block_id"],
                    "kind": "removed",
                    "before": before,
                    "after": None,
                    "source_refs_changed": True,
                    "evidence_refs_changed": bool(before["evidence_refs"]),
                }
            )
    return {
        "resume_id": resume_id,
        "from_version": from_number,
        "to_version": to_number,
        "changes": changes,
        "source_manifest_changed": (
            json_value(source.source_manifest_json, [])
            != json_value(target.source_manifest_json, [])
        ),
        "evidence_manifest_changed": (
            json_value(source.evidence_manifest_json, [])
            != json_value(target.evidence_manifest_json, [])
        ),
    }


@app.post("/api/resumes/{resume_id}/versions/{version_number}/restore")
def restore_version(
    resume_id: int,
    version_number: int,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    resume = get_or_404(db, Resume, resume_id)
    version, dirty = restore_formal_version(db, resume, version_number)
    db.commit()
    return {
        "restored_version": version_number,
        "content_state": "dirty" if dirty else "clean",
        "pending_reason": "rollback" if dirty else None,
    }


@app.patch("/api/resumes/{resume_id}/profile")
def update_resume_profile(
    resume_id: int,
    payload: ProfileCopyInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    resume = get_or_404(db, Resume, resume_id)
    values = {
        key: value
        for key, value in payload.model_dump().items()
        if value is not None
    }
    if not values:
        raise HTTPException(422, "没有需要修改的岗位字段")
    profile = clone_profile_for_resume(db, resume, values, actor_id(db))
    db.commit()
    return {"resume_id": resume.id, "profile": serialize_profile(profile)}


@app.post("/api/resumes/{resume_id}/versions/{version_number}/export")
def export_resume(
    resume_id: int,
    version_number: int,
    force: bool = False,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    resume = get_or_404(db, Resume, resume_id)
    version = db.scalar(
        select(ResumeVersion).where(
            ResumeVersion.workspace_id == WORKSPACE_ID,
            ResumeVersion.resume_id == resume_id,
            ResumeVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(404, "版本不存在")
    content = content_with_embedded_profile_photo(
        db, json_value(version.content_json, {})
    )
    template = db.get(Template, resume.template_id)
    if template is None:
        raise HTTPException(503, "没有可用模板")
    warnings = lint_resume(content)
    if warnings and not force:
        raise HTTPException(
            409,
            f"导出体检发现 {len(warnings)} 个问题；确认风险后可强制导出",
        )
    html = render_resume_html(
        content,
        resume.display_name,
        version_number,
        successor_key(template),
        lint_issues=warnings,
    )
    event = record_export(
        db, resume, version, template, html, warnings, force
    )
    db.commit()
    filename = re.sub(
        r"[^A-Za-z0-9\u4e00-\u9fff._-]+",
        "-",
        f"{resume.display_name}-v{version_number}",
    ).strip("-") or f"resume-v{version_number}"
    header_filename = quote(f"{filename}.html")
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="resume-v{version_number}.html"; '
                f"filename*=UTF-8''{header_filename}"
            ),
            "X-Export-Event-Id": str(event.id),
            "X-Content-Hash": version.content_hash,
        },
    )


@app.get("/api/export-events")
def export_events(db: Session = Depends(get_db)):
    require_workspace(db)
    return [
        {
            "id": item.id,
            "resume_id": item.resume_id,
            "resume_version_id": item.resume_version_id,
            "template_id": item.template_id,
            "format": item.format,
            "warnings": json_value(item.warnings_json, []),
            "forced": item.forced,
            "content_hash": item.content_hash,
            "output_hash": item.output_hash,
            "created_at": item.created_at,
        }
        for item in list_export_events(db, WORKSPACE_ID)
    ]


@app.get("/api/pending-issues")
def pending_issues(
    status: str = "open",
    db: Session = Depends(get_db),
):
    require_workspace(db)
    items = db.scalars(
        select(PendingIssue)
        .outerjoin(Resume, Resume.id == PendingIssue.resume_id)
        .where(
            PendingIssue.workspace_id == WORKSPACE_ID,
            PendingIssue.status == status,
            or_(PendingIssue.resume_id.is_(None), Resume.status == "active"),
        )
        .order_by(PendingIssue.created_at.desc())
    ).all()
    result = []
    for item in items:
        fact = db.get(FactRecord, item.fact_id) if item.fact_id else None
        evidence = db.get(Evidence, item.evidence_id) if item.evidence_id else None
        profile = db.get(RequirementProfile, item.profile_id) if item.profile_id else None
        result.append(
            {
                "id": item.id,
                "kind": item.kind,
                "status": item.status,
                "resume_id": item.resume_id,
                "fact_id": item.fact_id,
                "evidence_id": item.evidence_id,
                "profile_id": item.profile_id,
                "section_code": item.section_code,
                "block_key": item.block_key,
                "message": item.message,
                "created_at": item.created_at,
                "resolved_at": item.resolved_at,
                "source": {
                    "fact": fact_response(db, fact) if fact else None,
                    "evidence": evidence_response(evidence) if evidence else None,
                    "profile": serialize_profile(profile) if profile else None,
                },
            }
        )
    return result


@app.patch("/api/pending-issues/{issue_id}")
def resolve_pending_issue(
    issue_id: int,
    payload: PendingIssueInput,
    db: Session = Depends(get_db),
):
    require_workspace(db)
    item = get_or_404(db, PendingIssue, issue_id)
    if item.workspace_id != WORKSPACE_ID:
        raise HTTPException(404, "对象不存在")
    if item.status != "open":
        raise HTTPException(409, "该事项已经处理")
    if payload.status not in {"resolved", "dismissed"}:
        raise HTTPException(422, "事项处理状态必须为 resolved 或 dismissed")
    item.status = payload.status
    item.resolved_at = now()
    db.commit()
    return {
        "id": item.id,
        "status": item.status,
        "resolved_at": item.resolved_at,
    }


@app.post("/api/resumes/{resume_id}/lint")
def lint_working_copy(resume_id: int, db: Session = Depends(get_db)):
    require_workspace(db)
    get_or_404(db, Resume, resume_id)
    copy = load_working_copy(db, resume_id)
    return {"issues": lint_resume(json_value(copy.content_json, {}))}
