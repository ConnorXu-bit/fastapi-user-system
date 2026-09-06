"""add rbac tables

Revision ID: a1626744c1d0
Revises: b7c14a4e5141
Create Date: 2026-09-04 23:57:47.268709

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'a1626744c1d0'
down_revision: Union[str, Sequence[str], None] = 'b7c14a4e5141'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_ROLE_ID = uuid.UUID('29fba644-b976-4f0c-948a-094a19b72200')
USER_ROLE_ID = uuid.UUID('83e65a0d-5169-4fdf-89ac-2ea53c9accf3')

PERMISSIONS = {
    'user:list': uuid.UUID('6f757a8c-42e7-496c-b1ad-503d6c74b163'),
    'user:delete': uuid.UUID('d46d0efc-e0cb-4e59-a15a-add208a6521d'),
    'role:assign': uuid.UUID('b258f859-4b0c-4f7f-95f5-c4dddb2be9a0'),
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('permissions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_permissions_name'), 'permissions', ['name'], unique=True)
    op.create_table('roles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)
    op.create_table('role_permissions',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('permission_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )
    op.create_table('user_roles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

    roles_table = sa.table(
        'roles',
        sa.column('id', sa.Uuid()),
        sa.column('name', sa.String(50)),
        sa.column('description', sa.String(255)),
    )
    op.bulk_insert(roles_table, [
        {'id': ADMIN_ROLE_ID, 'name': 'admin', 'description': 'Default admin role'},
        {'id': USER_ROLE_ID, 'name': 'user', 'description': 'Default user role'},
    ])

    permissions_table = sa.table(
        'permissions',
        sa.column('id', sa.Uuid()),
        sa.column('name', sa.String(100)),
        sa.column('description', sa.String(255)),
    )
    op.bulk_insert(permissions_table, [
        {'id': perm_id, 'name': name, 'description': f'Permission: {name}'}
        for name, perm_id in PERMISSIONS.items()
    ])

    for perm_id in PERMISSIONS.values():
        op.execute(
            'INSERT INTO role_permissions (role_id, permission_id) '
            f"VALUES ('{ADMIN_ROLE_ID.hex}', '{perm_id.hex}')"
        )

    op.execute(
        'INSERT INTO user_roles (user_id, role_id) '
        'SELECT u.id, r.id FROM users u JOIN roles r ON r.name = u.role'
    )
    op.drop_column('users', 'role')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('role', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=50), nullable=True))
    op.execute(
        "UPDATE users u SET u.role = IF(EXISTS("
        "SELECT 1 FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
        "WHERE ur.user_id = u.id AND r.name = 'admin'), 'admin', 'user')"
    )
    op.alter_column('users', 'role', existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=50), nullable=False)
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_index(op.f('ix_roles_name'), table_name='roles')
    op.drop_table('roles')
    op.drop_index(op.f('ix_permissions_name'), table_name='permissions')
    op.drop_table('permissions')
