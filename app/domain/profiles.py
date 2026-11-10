from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..services import dump, serialize_profile
from ..workbench_models import (
    JobOpportunity,
    ProfileAuditEvent,
    RequirementProfile,
    Resume,
    now,
)


PROFILE_FIELDS = (
    "name",
    "role_direction",
    "core_requirements",
    "general_requirements",
    "responsibilities",
    "resume_strategy",
    "raw_jd",
    "source_note",
)


def _snapshot(item: RequirementProfile) -> dict:
    return serialize_profile(item)


def add_audit(
    db: Session,
    workspace_id: int,
    profile_id: int,
    actor_user_id: int,
    action: str,
    *,
    changed_fields: list[str] | None = None,
    before: dict | None = None,
    after: dict | None = None,
    related_profile_ids: list[int] | None = None,
    reason: str = "",
) -> ProfileAuditEvent:
    event = ProfileAuditEvent(
        workspace_id=workspace_id,
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        action=action,
        changed_fields_json=dump(changed_fields or []),
        before_values_json=dump(before or {}),
        after_values_json=dump(after or {}),
        related_profile_ids_json=dump(related_profile_ids or []),
        reason=reason,
    )
    db.add(event)
    return event


def apply_profile_values(item: RequirementProfile, values: dict) -> list[str]:
    before = _snapshot(item)
    for key in PROFILE_FIELDS:
        if key not in values:
            continue
        value = values[key]
        if key == "core_requirements":
            value = dump(value)
        setattr(item, key, value)
    after = _snapshot(item)
    return [key for key in PROFILE_FIELDS if before.get(key) != after.get(key)]


def clone_profile_for_resume(
    db: Session,
    resume: Resume,
    values: dict,
    actor_user_id: int,
) -> RequirementProfile:
    original = db.get(RequirementProfile, resume.requirement_profile_id)
    if original is None:
        raise HTTPException(404, "岗位画像不存在")
    clone = RequirementProfile(
        workspace_id=original.workspace_id,
        name=values.get("name") or f"{original.name}（简历副本）",
        role_direction=original.role_direction,
        core_requirements=original.core_requirements,
        general_requirements=original.general_requirements,
        responsibilities=original.responsibilities,
        resume_strategy=original.resume_strategy,
        raw_jd=original.raw_jd,
        source_note=original.source_note,
        status="active",
    )
    db.add(clone)
    db.flush()
    apply_profile_values(clone, values)
    add_audit(
        db,
        clone.workspace_id,
        original.id,
        actor_user_id,
        "cloned",
        after=_snapshot(clone),
        related_profile_ids=[clone.id],
        reason="resume profile edit",
    )
    add_audit(
        db,
        clone.workspace_id,
        clone.id,
        actor_user_id,
        "created",
        after=_snapshot(clone),
        related_profile_ids=[original.id],
        reason="copied from resume profile",
    )
    resume.requirement_profile_id = clone.id
    return clone


def active_resume_for_profile(
    db: Session, workspace_id: int, profile_id: int, exclude_id: int | None = None
) -> Resume | None:
    query = select(Resume).where(
        Resume.workspace_id == workspace_id,
        Resume.requirement_profile_id == profile_id,
        Resume.status == "active",
    )
    if exclude_id is not None:
        query = query.where(Resume.id != exclude_id)
    return db.scalar(query)


def active_opportunities(db: Session, workspace_id: int, profile_id: int) -> list[JobOpportunity]:
    return list(
        db.scalars(
            select(JobOpportunity).where(
                JobOpportunity.workspace_id == workspace_id,
                JobOpportunity.requirement_profile_id == profile_id,
                JobOpportunity.status == "active",
            )
        ).all()
    )
