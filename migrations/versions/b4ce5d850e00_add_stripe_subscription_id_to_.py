"""Add stripe_subscription_id to Organization model

Revision ID: b4ce5d850e00
Revises: c2e8342e9dff
Create Date: 2025-01-31 09:02:44.830186

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4ce5d850e00'
down_revision = 'c2e8342e9dff'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stripe_subscription_id', sa.String(length=100), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('stripe_subscription_id')

    # ### end Alembic commands ###
