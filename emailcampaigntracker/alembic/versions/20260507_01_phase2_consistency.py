"""Phase 2 consistency migration.

Revision ID: 20260507_01
Revises:
Create Date: 2026-05-07
"""

from alembic import op

revision = "20260507_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS open_count INTEGER DEFAULT 0")
    op.execute("ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS click_count INTEGER DEFAULT 0")
    op.execute("ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS replied BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS last_opened TIMESTAMP")
    op.execute("ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS last_clicked TIMESTAMP")
    op.execute("ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS last_replied TIMESTAMP")
    op.execute("ALTER TABLE email_sequences ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP")
    op.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS created_at TIMESTAMP")
    op.execute(
        "ALTER TABLE email_sequences ADD CONSTRAINT IF NOT EXISTS unique_tracking_id UNIQUE (tracking_id)"
    )
    op.execute("UPDATE email_sequences SET open_count = 0 WHERE open_count IS NULL")
    op.execute("UPDATE email_sequences SET click_count = 0 WHERE click_count IS NULL")
    op.execute("UPDATE email_sequences SET replied = FALSE WHERE replied IS NULL")
    op.execute("UPDATE events SET timestamp = NOW() WHERE timestamp IS NULL")
    op.execute("UPDATE leads SET created_at = NOW() WHERE created_at IS NULL")


def downgrade() -> None:
    # Downgrade is intentionally minimal and migration-safe; we only drop added constraint.
    op.execute("ALTER TABLE email_sequences DROP CONSTRAINT IF EXISTS unique_tracking_id")

