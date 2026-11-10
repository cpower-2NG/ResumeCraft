from __future__ import annotations

import hashlib

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..services import (
    build_resume_content,
    content_hash,
    dump,
    evidence_manifest,
    json_value,
    serialize_profile,
    source_manifest,
    sync_references,
)
from ..workbench_models import (
    LinkedResume,
    PendingIssue,
    RequirementProfile,
    Resume,
    ResumeVersion,
    ResumeVersionEvidenceSnapshot,
    ResumeVersionFactSnapshot,
    ResumeWorkingCopy,
    now,
)
from .catalog import resolve_template


def create_draft(db: Session, workspace_id: int, profile_id: int, template_id: int | None = None) -> LinkedResume:
    profile = db.get(RequirementProfile, profile_id)
    if profile is None or profile.workspace_id != workspace_id:
        raise HTTPException(404, "岗位画像不存在")
    template = resolve_template(db, template_id=template_id, workspace_id=workspace_id)
    draft = LinkedResume(
        workspace_id=workspace_id,
        requirement_profile_id=profile.id,
        template_id=template.id,
        selection_json="{}",
        status="open",
    )
    db.add(draft)
    db.flush()
    return draft


def version_content_hash(version: ResumeVersion) -> str:
    return content_hash(
        json_value(version.content_json, {}),
        json_value(version.profile_snapshot_json, {}),
        json_value(version.source_manifest_json, []),
        json_value(version.evidence_manifest_json, []),
    )


def build_version(
    db: Session,
    resume: Resume,
    content: dict,
    profile: RequirementProfile,
    template_id: int,
    *,
    version_number: int,
    reason: str,
    change_summary: str,
) -> ResumeVersion:
    profile_snapshot = serialize_profile(profile)
    sources = source_manifest(content)
    evidence = evidence_manifest(db, content)
    version = ResumeVersion(
        workspace_id=resume.workspace_id,
        resume_id=resume.id,
        version_number=version_number,
        content_json=dump(content),
        source_manifest_json=dump(sources),
        profile_snapshot_json=dump(profile_snapshot),
        profile_snapshot_hash=hashlib.sha256(
            dump(profile_snapshot).encode("utf-8")
        ).hexdigest(),
        evidence_manifest_json=dump(evidence),
        reason=reason,
        change_summary=change_summary,
        content_hash=content_hash(content, profile_snapshot, sources, evidence),
    )
    db.add(version)
    db.flush()
    return version


def snapshot_references(db: Session, version: ResumeVersion) -> None:
    content = json_value(version.content_json, {})
    for order, item in enumerate(json_value(version.source_manifest_json, [])):
        db.add(
            ResumeVersionFactSnapshot(
                workspace_id=version.workspace_id,
                resume_version_id=version.id,
                fact_id=item["fact_id"],
                section_code=item["section_id"],
                block_key=item["block_id"],
                display_order=order,
            )
        )
    for order, item in enumerate(json_value(version.evidence_manifest_json, [])):
        db.add(
            ResumeVersionEvidenceSnapshot(
                workspace_id=version.workspace_id,
                resume_version_id=version.id,
                evidence_id=item["evidence_id"],
                section_code=item["section_id"],
                block_key=item["block_id"],
                display_mode=item.get("display_mode", "reference"),
                label=item.get("label", ""),
                display_order=order,
            )
        )
    sync_references(db, version.resume_id, version.workspace_id, content, json_value(version.evidence_manifest_json, []))


def convert_draft(db: Session, draft: LinkedResume) -> Resume:
    if draft.status != "open" or draft.converted_resume_id is not None:
        raise HTTPException(409, "该临时简历已经转化或已放弃")
    existing = db.scalar(
        select(Resume).where(
            Resume.workspace_id == draft.workspace_id,
            Resume.requirement_profile_id == draft.requirement_profile_id,
            Resume.status == "active",
        )
    )
    if existing:
        raise HTTPException(409, "该岗位画像已有活跃正式简历")
    profile = db.get(RequirementProfile, draft.requirement_profile_id)
    if profile is None and draft.requirement_profile_id is not None:
        raise HTTPException(404, "岗位画像不存在")
    content = build_resume_content(db, profile, json_value(draft.selection_json, {}))
    resume = Resume(
        workspace_id=draft.workspace_id,
        requirement_profile_id=profile.id,
        origin_linked_resume_id=draft.id,
        template_id=draft.template_id,
        display_name=f"{profile.name}简历",
        status="active",
    )
    db.add(resume)
    db.flush()
    version = build_version(
        db,
        resume,
        content,
        profile,
        draft.template_id,
        version_number=1,
        reason="format_conversion",
        change_summary="格式化简历、未润色",
    )
    resume.current_version_id = version.id
    db.add(
        ResumeWorkingCopy(
            workspace_id=draft.workspace_id,
            resume_id=resume.id,
            base_version_id=version.id,
            template_id=draft.template_id,
            content_json=dump(content),
            content_state="clean",
            evidence_sync_state="clean",
            baseline_state="current",
        )
    )
    draft.status = "converted"
    draft.converted_resume_id = resume.id
    snapshot_references(db, version)
    return resume


def working_copy(db: Session, resume_id: int) -> ResumeWorkingCopy:
    item = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_id == resume_id))
    if item is None:
        raise HTTPException(404, "该简历还没有工作副本")
    return item


def current_version(db: Session, resume: Resume) -> ResumeVersion | None:
    return db.get(ResumeVersion, resume.current_version_id) if resume.current_version_id else None


def save_working_copy(
    db: Session,
    resume: Resume,
    change_summary: str,
    *,
    expected_version_id: int | None = None,
) -> ResumeVersion:
    copy = working_copy(db, resume.id)
    latest = current_version(db, resume)
    if latest and copy.base_version_id != latest.id:
        copy.baseline_state = "stale"
        raise HTTPException(409, "工作副本基线已过期，请从当前版本重新载入")
    if expected_version_id is not None and (latest is None or latest.id != expected_version_id):
        raise HTTPException(409, "正式版本已变化，请重新载入")
    profile = db.get(RequirementProfile, resume.requirement_profile_id)
    if profile is None:
        raise HTTPException(409, "岗位画像不存在")
    content = json_value(copy.content_json, {})
    reason = copy.pending_reason or "user_save"
    if reason not in {"format_conversion", "user_save", "rollback", "evidence_sync"}:
        reason = "user_save"
    version = build_version(
        db,
        resume,
        content,
        profile,
        copy.template_id,
        version_number=(latest.version_number + 1) if latest else 1,
        reason=reason,
        change_summary=change_summary,
    )
    resume.current_version_id = version.id
    resume.template_id = copy.template_id
    copy.base_version_id = version.id
    copy.content_state = "clean"
    copy.baseline_state = "current"
    copy.pending_reason = None
    copy.evidence_sync_state = "clean"
    snapshot_references(db, version)
    db.query(PendingIssue).filter(
        PendingIssue.resume_id == resume.id,
        PendingIssue.status == "open",
    ).update(
        {"status": "resolved", "resolved_at": now()},
        synchronize_session=False,
    )
    return version


def restore_version(db: Session, resume: Resume, version_number: int) -> tuple[ResumeVersion, bool]:
    version = db.scalar(
        select(ResumeVersion).where(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(404, "版本不存在")
    copy = working_copy(db, resume.id)
    current = current_version(db, resume)
    restoring_current = current is not None and version.id == current.id
    copy.content_json = version.content_json
    copy.base_version_id = resume.current_version_id
    copy.template_id = resume.template_id
    copy.content_state = "clean" if restoring_current else "dirty"
    copy.baseline_state = "current"
    copy.pending_reason = None if restoring_current else "rollback"
    return version, not restoring_current
