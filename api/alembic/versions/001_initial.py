"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE platform_enum AS ENUM ('twitter','reddit','email','manual')")
    op.execute("CREATE TYPE risk_enum AS ENUM ('LOW','MEDIUM','HIGH','CRITICAL')")
    op.execute("CREATE TYPE edge_type_enum AS ENUM ('posted','shared')")

    op.create_table(
        "content",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("text_preview", sa.String(300), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("twitter", "reddit", "email", "manual", name="platform_enum"),
            nullable=False,
        ),
        sa.Column("actor_identifier", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_content_hash", "content", ["content_hash"])

    op.create_table(
        "detection_result",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("content.id"),
            nullable=False,
        ),
        sa.Column("ai_probability", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column(
            "risk_level",
            sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_enum"),
            nullable=False,
        ),
        sa.Column("model_attribution", sa.String(50), nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("cluster_id", sa.String(10), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("detected_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_dr_detected_at", "detection_result", ["detected_at"])
    op.create_index("ix_dr_cluster_id", "detection_result", ["cluster_id"])
    op.create_index("ix_dr_risk_level", "detection_result", ["risk_level"])

    op.create_table(
        "actor",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor_identifier", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("content_count", sa.Integer, default=0),
        sa.Column("ai_content_count", sa.Integer, default=0),
        sa.Column("last_seen", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("actor_identifier", "platform", name="uq_actor_platform"),
    )

    op.create_table(
        "network_edge",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor_identifier", sa.String(255), nullable=False),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("content.id"),
            nullable=False,
        ),
        sa.Column(
            "edge_type",
            sa.Enum("posted", "shared", name="edge_type_enum"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("network_edge")
    op.drop_table("actor")
    op.drop_table("detection_result")
    op.drop_table("content")
    op.execute("DROP TYPE edge_type_enum")
    op.execute("DROP TYPE risk_enum")
    op.execute("DROP TYPE platform_enum")