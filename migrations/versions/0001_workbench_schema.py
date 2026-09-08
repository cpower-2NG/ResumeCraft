"""Create the initial resume workbench schema."""

from alembic import op

from app.workbench_database import WorkbenchBase
import app.workbench_models  # Registers all models before create_all.


revision = "0001_workbench_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    WorkbenchBase.metadata.create_all(bind=op.get_bind())


def downgrade():
    WorkbenchBase.metadata.drop_all(bind=op.get_bind())
