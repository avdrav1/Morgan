"""add discord oauth fields

Revision ID: i8a9b0c1d2e3
Revises: h7a8b9c0d1e2
Create Date: 2024-11-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i8a9b0c1d2e3'
down_revision = 'h7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    """Add Discord OAuth-related fields.

    This migration is written to be idempotent so that it can run safely
    even if some or all of the columns/index were already created
    manually or by a previous migration.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("users")}

    if "discord_user_id" not in existing_columns:
        op.add_column("users", sa.Column("discord_user_id", sa.String(), nullable=True))
    if "discord_username" not in existing_columns:
        op.add_column("users", sa.Column("discord_username", sa.String(), nullable=True))
    if "discord_discriminator" not in existing_columns:
        op.add_column("users", sa.Column("discord_discriminator", sa.String(), nullable=True))
    if "discord_avatar" not in existing_columns:
        op.add_column("users", sa.Column("discord_avatar", sa.String(), nullable=True))
    if "discord_access_token" not in existing_columns:
        op.add_column("users", sa.Column("discord_access_token", sa.Text(), nullable=True))
    if "discord_refresh_token" not in existing_columns:
        op.add_column("users", sa.Column("discord_refresh_token", sa.Text(), nullable=True))
    if "discord_token_expires_at" not in existing_columns:
        op.add_column("users", sa.Column("discord_token_expires_at", sa.DateTime(), nullable=True))
    if "is_new" not in existing_columns:
        op.add_column(
            "users",
            sa.Column("is_new", sa.Boolean(), nullable=False, server_default="true"),
        )
    if "oauth_provider" not in existing_columns:
        op.add_column("users", sa.Column("oauth_provider", sa.String(), nullable=True))

    # Create unique index on discord_user_id only if it doesn't already exist
    if "ix_users_discord_user_id" not in existing_indexes:
        op.create_index(
            "ix_users_discord_user_id",
            "users",
            ["discord_user_id"],
            unique=True,
        )

    # Make hashed_password nullable for OAuth-only users. This is safe to run
    # even if the column is already nullable.
    op.alter_column("users", "hashed_password", nullable=True)


def downgrade():
    """Reverse the Discord OAuth-related fields where possible.

    This is also written defensively so it won't fail if parts of the
    schema were already removed.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("users")}

    if "ix_users_discord_user_id" in existing_indexes:
        op.drop_index("ix_users_discord_user_id", table_name="users")

    for column_name in [
        "oauth_provider",
        "is_new",
        "discord_token_expires_at",
        "discord_refresh_token",
        "discord_access_token",
        "discord_avatar",
        "discord_discriminator",
        "discord_username",
        "discord_user_id",
    ]:
        if column_name in existing_columns:
            op.drop_column("users", column_name)

    # Make hashed_password non-nullable again
    op.alter_column("users", "hashed_password", nullable=False)
