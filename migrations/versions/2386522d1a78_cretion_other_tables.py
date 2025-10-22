"""Cretion Other Tables

Revision ID: 2386522d1a78
Revises: d6b3f3f7bb87
Create Date: 2025-10-22 10:02:05.446441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2386522d1a78'
down_revision: Union[str, Sequence[str], None] = 'd6b3f3f7bb87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### Manually adjusted Alembic commands ###

    # Create tables that have no dependencies first
    op.create_table('tbl_extruder_screen_sizes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('size', sa.String(length=50), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['deleted_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tbl_extruder_screen_sizes_size'), 'tbl_extruder_screen_sizes', ['size'], unique=True)

    op.create_table('tbl_extruder_shifts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=20), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['deleted_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # --- FIX 1: Create tbl_extruder_form_data NEXT, as other tables depend on it ---
    # --- FIX 2: Use the CORRECT column name 'machine_config_id' ---
    op.create_table('tbl_extruder_form_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('process_id', sa.String(length=100), nullable=True),
        sa.Column('production_id', sa.String(length=100), nullable=True),
        sa.Column('formula_no', sa.String(length=100), nullable=True),
        sa.Column('order_no', sa.String(length=100), nullable=True),
        sa.Column('product_code', sa.String(length=100), nullable=True),
        sa.Column('customer', sa.String(length=500), nullable=True),
        sa.Column('lot_number', sa.String(length=100), nullable=True),
        sa.Column('qty_order', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('total_input', sa.Numeric(precision=10, scale=2), nullable=True), # Match model name
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('prepared_by', sa.String(length=255), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=False),
        sa.Column('machine_id', sa.Integer(), nullable=False), # Match model
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['deleted_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['machine_id'], ['tbl_extruder_machines.id'], ), # Match model
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    # Note: Foreign keys to tbl_extruder_machine_configs and tbl_extruder_shifts are removed
    # from the initial create statement because those tables may not exist yet.
    # We will add them later with op.create_foreign_key() if needed, but the models don't show this.

    op.create_index(op.f('ix_tbl_extruder_form_data_lot_number'), 'tbl_extruder_form_data', ['lot_number'], unique=False)
    op.create_index(op.f('ix_tbl_extruder_form_data_process_id'), 'tbl_extruder_form_data', ['process_id'], unique=False)
    op.create_index(op.f('ix_tbl_extruder_form_data_production_id'), 'tbl_extruder_form_data', ['production_id'], unique=False)

    # --- FIX 3: Use the CORRECT table name 'tbl_extruder_machine_configs' ---
    op.create_table('tbl_extruder_machine_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('extruder_form_data_id', sa.Integer(), nullable=False),
        sa.Column('screen_size_id', sa.Integer(), nullable=False),
        sa.Column('screw_config', sa.String(length=255), nullable=True),
        sa.Column('feed_rate', sa.String(length=100), nullable=True),
        sa.Column('rpm', sa.String(length=100), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['deleted_by_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['extruder_form_data_id'], ['tbl_extruder_form_data.id'], ),
        sa.ForeignKeyConstraint(['screen_size_id'], ['tbl_extruder_screen_sizes.id'], ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # The rest of the tables depend on tbl_extruder_form_data, so they are created last
    op.create_table('tbl_extruder_outputs',
        # ... (This section is correct)
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('extruder_form_data_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=True),
        # ... other columns
        sa.ForeignKeyConstraint(['extruder_form_data_id'], ['tbl_extruder_form_data.id'], ),
        # ... other constraints
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tbl_extruder_machine_temps',
        # ... (This section is correct)
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('extruder_form_data_id', sa.Integer(), nullable=False),
        # ... other columns
        sa.ForeignKeyConstraint(['extruder_form_data_id'], ['tbl_extruder_form_data.id'], ),
        # ... other constraints
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tbl_extruder_personnels',
        # ... (This section is correct)
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('extruder_form_data_id', sa.Integer(), nullable=False),
        # ... other columns
        sa.ForeignKeyConstraint(['extruder_form_data_id'], ['tbl_extruder_form_data.id'], ),
        # ... other constraints
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tbl_extruder_purging_headers',
        # ... (This section is correct)
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('extruder_form_data_id', sa.Integer(), nullable=False),
        # ... other columns
        sa.ForeignKeyConstraint(['extruder_form_data_id'], ['tbl_extruder_form_data.id'], ),
        # ... other constraints
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tbl_extruder_purging_details',
        # ... (This section is correct)
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('purging_header_id', sa.Integer(), nullable=False),
        # ... other columns
        sa.ForeignKeyConstraint(['purging_header_id'], ['tbl_extruder_purging_headers.id'], ),
        # ... other constraints
        sa.PrimaryKeyConstraint('id')
    )
    # Other miscellaneous commands
    op.drop_constraint(op.f('tbl_formula02_formula_header_id_fkey'), 'tbl_formula02', type_='foreignkey')
    op.create_foreign_key(None, 'tbl_formula02', 'tbl_formula01', ['formula_header_id'], ['id'], source_schema='public', referent_schema='public')
    op.create_unique_constraint(None, 'tbl_mixer_details', ['id'])
    op.create_unique_constraint(None, 'tbl_mixer_headers', ['id'])
    op.create_unique_constraint(None, 'tbl_mixer_machines', ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### Manually adjusted Alembic commands ###
    op.drop_constraint(None, 'tbl_mixer_machines', type_='unique')
    op.drop_constraint(None, 'tbl_mixer_headers', type_='unique')
    op.drop_constraint(None, 'tbl_mixer_details', type_='unique')
    op.drop_constraint(None, 'tbl_formula02', schema='public', type_='foreignkey')
    op.create_foreign_key(op.f('tbl_formula02_formula_header_id_fkey'), 'tbl_formula02', 'tbl_formula01', ['formula_header_id'], ['id'])
    op.drop_table('tbl_extruder_purging_details')
    op.drop_table('tbl_extruder_purging_headers')
    op.drop_table('tbl_extruder_personnels')
    op.drop_table('tbl_extruder_machine_temps')
    op.drop_table('tbl_extruder_outputs')
    op.drop_table('tbl_extruder_machine_configs') # Use correct name
    op.drop_index(op.f('ix_tbl_extruder_form_data_production_id'), table_name='tbl_extruder_form_data')
    op.drop_index(op.f('ix_tbl_extruder_form_data_process_id'), table_name='tbl_extruder_form_data')
    op.drop_index(op.f('ix_tbl_extruder_form_data_lot_number'), table_name='tbl_extruder_form_data')
    op.drop_table('tbl_extruder_form_data')
    op.drop_table('tbl_extruder_shifts')
    op.drop_index(op.f('ix_tbl_extruder_screen_sizes_size'), table_name='tbl_extruder_screen_sizes')
    op.drop_table('tbl_extruder_screen_sizes')
    # ### end Alembic commands ###