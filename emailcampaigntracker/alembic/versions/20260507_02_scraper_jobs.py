"""Add scraper job tracking table.

Revision ID: 20260507_02
Revises: 20260507_01
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa

revision = "20260507_02"
down_revision = "20260507_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scraper_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("source", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("log_excerpt", sa.Text(), nullable=True),
        sa.Column("rq_job_id", sa.String(), nullable=True),
    )
    op.create_index("ix_scraper_jobs_status", "scraper_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_scraper_jobs_status", table_name="scraper_jobs")
    op.drop_table("scraper_jobs")

