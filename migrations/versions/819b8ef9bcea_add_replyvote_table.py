"""Add replyvote table

Revision ID: 819b8ef9bcea
Revises: bedc6ee1aa3c
Create Date: 2025-05-26 20:50:23.081099

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '819b8ef9bcea'
down_revision = 'bedc6ee1aa3c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comment_vote', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voter_id', sa.Integer(), nullable=False))
        batch_op.drop_constraint('unique_comment_vote', type_='unique')
        batch_op.create_unique_constraint('unique_comment_vote', ['voter_id', 'comment_id'])
        batch_op.drop_column('user_id')  # this implicitly drops the FK in SQLite
        batch_op.create_foreign_key('unique_reply_vote', 'user', ['voter_id'], ['id'], ondelete='CASCADE')

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('comment_vote', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=False))
        batch_op.drop_constraint('unique_comment_vote', type_='unique')
        batch_op.create_unique_constraint('unique_comment_vote', ['user_id', 'comment_id'])
        batch_op.drop_column('voter_id')  # this implicitly drops the FK in SQLite
        batch_op.create_foreign_key('unique_reply_vote', 'user', ['user_id'], ['id'], ondelete='CASCADE')

    # ### end Alembic commands ###
