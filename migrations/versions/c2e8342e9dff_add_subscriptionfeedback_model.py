"""Add SubscriptionFeedback model

Revision ID: c2e8342e9dff
Revises: c4ec0a5f4495
Create Date: 2025-01-30 21:09:01.734232

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2e8342e9dff'
down_revision = 'c4ec0a5f4495'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('subscription_feedbacks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('feedback', sa.Text(), nullable=False),
    sa.Column('reason', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.alter_column('domain',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=120),
               existing_nullable=True)
        batch_op.create_index(batch_op.f('ix_organizations_domain'), ['domain'], unique=True)
        batch_op.create_index(batch_op.f('ix_organizations_name'), ['name'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_organizations_name'))
        batch_op.drop_index(batch_op.f('ix_organizations_domain'))
        batch_op.alter_column('domain',
               existing_type=sa.String(length=120),
               type_=sa.VARCHAR(length=100),
               existing_nullable=True)

    op.drop_table('subscription_feedbacks')
    # ### end Alembic commands ###
