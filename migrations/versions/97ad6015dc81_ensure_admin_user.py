"""ensure_admin_user

Revision ID: 97ad6015dc81
Revises: 2607c506f9e5
Create Date: 2023-05-01 13:34:47.726714

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

from dundie.models.user import User
from sqlmodel import Session


# revision identifiers, used by Alembic.
revision = '97ad6015dc81'
down_revision = '2607c506f9e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    admin = User(
        name="Admin",
        username="admin",
        email="admin@dm.com",
        dept="management",
        password="admin",  # envvar/secrets - colocar password em settings
        currency="USD"
    )

    try:
        session.add(admin)
        session.commit()
    except sa.exc.IntegrityError:
        session.rollback()


def downgrade() -> None:
    pass
