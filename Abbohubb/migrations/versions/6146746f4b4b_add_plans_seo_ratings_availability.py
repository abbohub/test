"""add plans seo ratings availability

Revision ID: 6146746f4b4b
Revises: 393aefabfc51
Create Date: 2025-12-21 16:59:49.363412
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, inspect

revision = "6146746f4b4b"
down_revision = "393aefabfc51"
branch_labels = None
depends_on = None


def _col_exists(table_name: str, col_name: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(r[1] == col_name for r in rows)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade():
    # cleanup van eerdere mislukte batch runs
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_abonnement")

    # -----------------------------
    # abonnement: nieuwe kolommen
    # -----------------------------
    if not _col_exists("abonnement", "cutoff_time"):
        op.execute("ALTER TABLE abonnement ADD COLUMN cutoff_time VARCHAR(5)")

    if not _col_exists("abonnement", "lead_time_days"):
        op.execute("ALTER TABLE abonnement ADD COLUMN lead_time_days INTEGER")

    if not _col_exists("abonnement", "pause_possible"):
        op.execute("ALTER TABLE abonnement ADD COLUMN pause_possible BOOLEAN NOT NULL DEFAULT 0")

    if not _col_exists("abonnement", "pause_max_weeks"):
        op.execute("ALTER TABLE abonnement ADD COLUMN pause_max_weeks INTEGER")

    if not _col_exists("abonnement", "rating_avg"):
        op.execute("ALTER TABLE abonnement ADD COLUMN rating_avg FLOAT NOT NULL DEFAULT 5.0")

    if not _col_exists("abonnement", "rating_count"):
        op.execute("ALTER TABLE abonnement ADD COLUMN rating_count INTEGER NOT NULL DEFAULT 0")

    if not _col_exists("abonnement", "last_review_at"):
        op.execute("ALTER TABLE abonnement ADD COLUMN last_review_at DATETIME")

    if not _col_exists("abonnement", "status"):
        op.execute("ALTER TABLE abonnement ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'draft'")

    # SQLite: geen DEFAULT CURRENT_TIMESTAMP bij ALTER TABLE ADD COLUMN
    if not _col_exists("abonnement", "created_at"):
        op.execute("ALTER TABLE abonnement ADD COLUMN created_at DATETIME")
        op.execute("UPDATE abonnement SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    if not _col_exists("abonnement", "updated_at"):
        op.execute("ALTER TABLE abonnement ADD COLUMN updated_at DATETIME")

    if not _col_exists("abonnement", "published_at"):
        op.execute("ALTER TABLE abonnement ADD COLUMN published_at DATETIME")

    if not _col_exists("abonnement", "last_checked_at"):
        op.execute("ALTER TABLE abonnement ADD COLUMN last_checked_at DATETIME")

    if not _col_exists("abonnement", "editor_notes"):
        op.execute("ALTER TABLE abonnement ADD COLUMN editor_notes TEXT")

    # SEO velden in abonnement (die je model al selecteert)
    if not _col_exists("abonnement", "seo_title"):
        op.execute("ALTER TABLE abonnement ADD COLUMN seo_title VARCHAR(255)")

    if not _col_exists("abonnement", "meta_description"):
        op.execute("ALTER TABLE abonnement ADD COLUMN meta_description VARCHAR(255)")

    if not _col_exists("abonnement", "canonical_url"):
        op.execute("ALTER TABLE abonnement ADD COLUMN canonical_url VARCHAR(255)")

    if not _col_exists("abonnement", "og_image"):
        op.execute("ALTER TABLE abonnement ADD COLUMN og_image VARCHAR(255)")

    if not _col_exists("abonnement", "schema_type"):
        op.execute("ALTER TABLE abonnement ADD COLUMN schema_type VARCHAR(50)")

    if not _col_exists("abonnement", "faq_json"):
        op.execute("ALTER TABLE abonnement ADD COLUMN faq_json TEXT")

    # -----------------------------
    # categorie/subcategorie: seo_title
    # -----------------------------
    if not _col_exists("categorie", "seo_title"):
        op.execute("ALTER TABLE categorie ADD COLUMN seo_title VARCHAR(255)")

    if not _col_exists("subcategorie", "seo_title"):
        op.execute("ALTER TABLE subcategorie ADD COLUMN seo_title VARCHAR(255)")

    # -----------------------------
    # plan table + indexes
    # -----------------------------
    if not _table_exists("plan"):
        op.create_table(
            "plan",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("abonnement_id", sa.Integer(), sa.ForeignKey("abonnement.id"), nullable=False),

            sa.Column("plan_name", sa.String(length=80), nullable=False, server_default="Standaard"),
            sa.Column("price_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),

            sa.Column("billing_period", sa.String(length=20), nullable=False, server_default="month"),
            sa.Column("is_from_price", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("vat_included", sa.Boolean(), nullable=False, server_default=sa.text("1")),

            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    bind = op.get_bind()
    idx = inspect(bind).get_indexes("plan") if _table_exists("plan") else []
    idx_names = {i["name"] for i in idx}

    if "ix_plan_abonnement_id" not in idx_names:
        op.create_index("ix_plan_abonnement_id", "plan", ["abonnement_id"])
    if "ix_plan_billing_period" not in idx_names:
        op.create_index("ix_plan_billing_period", "plan", ["billing_period"])
    if "ix_plan_price_cents" not in idx_names:
        op.create_index("ix_plan_price_cents", "plan", ["price_cents"])


def downgrade():
    # best effort downgrade: alleen plan verwijderen
    if _table_exists("plan"):
        bind = op.get_bind()
        idx = inspect(bind).get_indexes("plan")
        idx_names = {i["name"] for i in idx}

        if "ix_plan_price_cents" in idx_names:
            op.drop_index("ix_plan_price_cents", table_name="plan")
        if "ix_plan_billing_period" in idx_names:
            op.drop_index("ix_plan_billing_period", table_name="plan")
        if "ix_plan_abonnement_id" in idx_names:
            op.drop_index("ix_plan_abonnement_id", table_name="plan")

        op.drop_table("plan")
