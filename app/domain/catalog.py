from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..templates import BUILTIN_TEMPLATES, descriptor_for, template_public_info
from ..workbench_models import Template, TemplatePreference


def ensure_templates(db: Session) -> bool:
    """Synchronise the global, code-backed template catalogue."""
    changed = False
    by_key = {item.template_key: item for item in db.scalars(select(Template)).all()}
    for key, descriptor in BUILTIN_TEMPLATES.items():
        item = by_key.get(key)
        if item is None:
            item = Template(
                template_key=key,
                display_name=descriptor["name"],
                description=descriptor["description"],
                renderer_key=key,
                supported_sections_json="[]",
                default_sections_json="[]",
                status="available",
            )
            db.add(item)
            by_key[key] = item
            changed = True
            continue
        if (
            item.display_name != descriptor["name"]
            or item.description != descriptor["description"]
            or item.renderer_key != key
            or item.status != "available"
        ):
            item.display_name = descriptor["name"]
            item.description = descriptor["description"]
            item.renderer_key = key
            item.status = "available"
            changed = True
    for item in by_key.values():
        if item.template_key not in BUILTIN_TEMPLATES and item.status == "available":
            item.status = "retired"
            changed = True
    return changed


def available_templates(db: Session) -> list[Template]:
    ensure_templates(db)
    db.flush()
    return list(
        db.scalars(
            select(Template)
            .where(Template.status == "available")
            .order_by(Template.id)
        ).all()
    )


def template_by_key(db: Session, key: str | None) -> Template | None:
    return db.scalar(
        select(Template).where(Template.template_key == (key or "classic"))
    )


def resolve_template(
    db: Session,
    template_id: int | None = None,
    *,
    workspace_id: int | None = None,
) -> Template:
    if template_id is not None:
        item = db.get(Template, template_id)
        if item is None or item.status != "available":
            raise HTTPException(422, "模板不存在或已退役")
        return item
    preference = (
        db.get(TemplatePreference, workspace_id)
        if workspace_id is not None
        else db.scalar(select(TemplatePreference).limit(1))
    )
    if preference and preference.default_template_id:
        item = db.get(Template, preference.default_template_id)
        if item and item.status == "available":
            return item
    choices = available_templates(db)
    if not choices:
        raise HTTPException(503, "没有可用模板")
    return choices[0]


def template_response(item: Template) -> dict:
    descriptor = descriptor_for(item.template_key)
    return {
        "id": item.id,
        "template_key": item.template_key,
        "display_name": item.display_name,
        "description": item.description,
        "renderer_key": item.renderer_key,
        "status": item.status,
        **template_public_info(descriptor),
    }


def successor_key(template: Template | None) -> str:
    return template.template_key if template else "classic"
