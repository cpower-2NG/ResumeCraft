"""Complete target schema guards introduced by the v2 resource contract."""

from alembic import op


revision = "0017_target_guard_completion"
down_revision = "0016_target_resource_model"
branch_labels = None
depends_on = None


TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS trg_extension_value_definition_update
    BEFORE UPDATE ON fact_extension_values
    WHEN NOT EXISTS (
        SELECT 1 FROM fact_field_definitions
        WHERE id=NEW.field_definition_id AND category_code=NEW.category_code
          AND schema_version_id=NEW.schema_version_id AND is_extension=1
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-018: extension field does not match fact schema'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_extension_value_type_update
    BEFORE UPDATE ON fact_extension_values
    WHEN EXISTS (
        SELECT 1 FROM fact_field_definitions
        WHERE id=NEW.field_definition_id AND (
            (value_type IN ('text','long_text','date','year_month','url','enum') AND NEW.text_value IS NULL)
            OR (value_type='number' AND NEW.numeric_value IS NULL)
            OR (value_type='boolean' AND NEW.boolean_value IS NULL)
            OR (value_type='integer' AND NEW.json_value IS NULL)
        )
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-018: extension value type mismatch'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_field_definition_insert_draft_only
    BEFORE INSERT ON fact_field_definitions
    WHEN NOT EXISTS (
        SELECT 1 FROM fact_schema_versions
        WHERE id=NEW.schema_version_id AND status='draft'
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-017: fields can only be added to a draft schema'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_published_field_definition_no_update
    BEFORE UPDATE ON fact_field_definitions
    WHEN EXISTS (
        SELECT 1 FROM fact_schema_versions
        WHERE id=OLD.schema_version_id AND status IN ('published','retired')
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-017: published field definitions are immutable'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_published_field_definition_no_delete
    BEFORE DELETE ON fact_field_definitions
    WHEN EXISTS (
        SELECT 1 FROM fact_schema_versions
        WHERE id=OLD.schema_version_id AND status IN ('published','retired')
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-017: published field definitions are immutable'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_schema_version_status_transition
    BEFORE UPDATE OF status ON fact_schema_versions
    WHEN NEW.status <> OLD.status AND NOT (
        (OLD.status='draft' AND NEW.status='published')
        OR (OLD.status='published' AND NEW.status='retired')
    )
    BEGIN SELECT RAISE(ABORT, 'RL-STS-004: invalid schema status transition'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_tag_name_not_alias
    BEFORE INSERT ON tags
    WHEN EXISTS (
        SELECT 1 FROM tag_aliases
        WHERE workspace_id=NEW.workspace_id AND normalized_alias=NEW.normalized_name
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag name collides with alias'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_tag_alias_not_name
    BEFORE INSERT ON tag_aliases
    WHEN EXISTS (
        SELECT 1 FROM tags
        WHERE workspace_id=NEW.workspace_id AND normalized_name=NEW.normalized_alias
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag alias collides with name'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_tag_name_not_alias_update
    BEFORE UPDATE OF workspace_id,normalized_name ON tags
    WHEN EXISTS (
        SELECT 1 FROM tag_aliases
        WHERE workspace_id=NEW.workspace_id AND normalized_alias=NEW.normalized_name
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag name collides with alias'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_tag_alias_not_name_update
    BEFORE UPDATE OF workspace_id,normalized_alias ON tag_aliases
    WHEN EXISTS (
        SELECT 1 FROM tags
        WHERE workspace_id=NEW.workspace_id AND normalized_name=NEW.normalized_alias
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag alias collides with name'); END
    """,
)


def upgrade() -> None:
    for statement in TRIGGERS:
        op.execute(statement)


def downgrade() -> None:
    for name in (
        "trg_tag_alias_not_name_update",
        "trg_tag_name_not_alias_update",
        "trg_tag_alias_not_name",
        "trg_tag_name_not_alias",
        "trg_schema_version_status_transition",
        "trg_published_field_definition_no_delete",
        "trg_published_field_definition_no_update",
        "trg_field_definition_insert_draft_only",
        "trg_extension_value_type_update",
        "trg_extension_value_definition_update",
    ):
        op.execute(f'DROP TRIGGER IF EXISTS "{name}"')
