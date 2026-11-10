from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..services import json_value
from ..workbench_models import (
    Evidence,
    RequirementProfile,
    Resume,
    ResumeEvidenceUse,
    ResumeWorkingCopy,
)
from .resume_chain import build_version, current_version, snapshot_references


def sync_evidence_changes(db: Session, evidence: Evidence) -> None:
    """Append evidence-only versions without capturing unsaved body edits."""
    resume_ids = {
        row.resume_id
        for row in db.scalars(
            select(ResumeEvidenceUse).where(
                ResumeEvidenceUse.evidence_id == evidence.id
            )
        ).all()
    }
    for resume_id in resume_ids:
        resume = db.get(Resume, resume_id)
        if resume is None:
            continue
        latest = current_version(db, resume)
        if latest is None:
            continue
        profile = db.get(RequirementProfile, resume.requirement_profile_id)
        if profile is None:
            continue
        version = build_version(
            db,
            resume,
            json_value(latest.content_json, {}),
            profile,
            resume.template_id,
            version_number=latest.version_number + 1,
            reason="evidence_sync",
            change_summary=f"证据同步：{evidence.title}",
        )
        resume.current_version_id = version.id
        copy = db.scalar(
            select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_id == resume.id)
        )
        if copy:
            copy.base_version_id = version.id
            copy.baseline_state = "current"
            copy.evidence_sync_state = (
                "pending" if copy.content_state == "dirty" else "clean"
            )
        snapshot_references(db, version)
