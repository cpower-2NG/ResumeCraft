from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..workbench_models import ExportEvent, Resume, ResumeVersion, Template


def record_export(
    db: Session,
    resume: Resume,
    version: ResumeVersion,
    template: Template,
    html: str,
    warnings: list[dict],
    forced: bool,
) -> ExportEvent:
    event = ExportEvent(
        workspace_id=resume.workspace_id,
        resume_id=resume.id,
        resume_version_id=version.id,
        template_id=template.id,
        format="html",
        warnings_json=__import__("json").dumps(warnings, ensure_ascii=False),
        forced=forced,
        content_hash=version.content_hash,
        output_hash=hashlib.sha256(html.encode("utf-8")).hexdigest(),
    )
    db.add(event)
    return event


def export_events(db: Session, workspace_id: int) -> list[ExportEvent]:
    return list(
        db.scalars(
            select(ExportEvent)
            .where(ExportEvent.workspace_id == workspace_id)
            .order_by(ExportEvent.created_at.desc())
        ).all()
    )
