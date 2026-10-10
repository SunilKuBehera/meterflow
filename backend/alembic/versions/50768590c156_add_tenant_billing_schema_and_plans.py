"""add tenant billing schema and plans

Revision ID: 50768590c156
Revises:
Create Date: 2026-10-10 16:32:43.535937

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '50768590c156'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tenants table
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # Tenant members table
    op.create_table(
        "tenant_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("OWNER", "ADMIN", "MEMBER", name="tenant_role", native_enum=False),
            nullable=False,
            server_default="MEMBER",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_member"),
    )
    op.create_index("ix_tenant_members_tenant_id", "tenant_members", ["tenant_id"])
    op.create_index("ix_tenant_members_user_id", "tenant_members", ["user_id"])

    # Plans table
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "name",
            sa.Enum("FREE", "PRO", name="plan_name", native_enum=False),
            nullable=False,
            unique=True,
        ),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("price_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("billing_period", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("api_calls_limit", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("ai_tokens_limit", sa.Integer, nullable=False, server_default="100000"),
        sa.Column("api_call_price_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_input_token_price_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_cached_input_token_price_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_output_token_price_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ai_reasoning_token_price_paise", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("razorpay_plan_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "PAST_DUE",
                "CANCELED",
                "TRIALING",
                "INCOMPLETE",
                name="subscription_status",
                native_enum=False,
            ),
            nullable=False,
            server_default="INCOMPLETE",
        ),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("razorpay_subscription_id", sa.String(100), nullable=True, unique=True),
        sa.Column("razorpay_customer_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"], unique=True)
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index(
        "ix_subscriptions_razorpay_subscription_id",
        "subscriptions",
        ["razorpay_subscription_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_subscriptions_razorpay_subscription_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_tenant_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    op.drop_index("ix_tenant_members_user_id", table_name="tenant_members")
    op.drop_index("ix_tenant_members_tenant_id", table_name="tenant_members")
    op.drop_table("tenant_members")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS subscription_status")
    op.execute("DROP TYPE IF EXISTS plan_name")
    op.execute("DROP TYPE IF EXISTS tenant_role")
