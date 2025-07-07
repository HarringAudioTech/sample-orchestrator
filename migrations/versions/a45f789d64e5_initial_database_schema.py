"""Initial database schema

Revision ID: a45f789d64e5
Revises: 
Create Date: 2025-07-07 08:16:58.522624

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'a45f789d64e5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum types first
    op.execute("""
    CREATE TABLE IF NOT EXISTS sample_type_enum (
        value VARCHAR(20) PRIMARY KEY
    )
    """)
    
    op.execute("""
    INSERT OR IGNORE INTO sample_type_enum (value) VALUES 
        ('one_shot'),
        ('loop'),
        ('multi_sample'),
        ('sfx')
    """)
    
    op.execute("""
    CREATE TABLE IF NOT EXISTS sample_pack_status_enum (
        value VARCHAR(20) PRIMARY KEY
    )
    """)
    
    op.execute("""
    INSERT OR IGNORE INTO sample_pack_status_enum (value) VALUES 
        ('draft'),
        ('in_progress'),
        ('complete'),
        ('published')
    """)
    
    # Create sample_categories table
    op.create_table(
        'sample_categories',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )
    
    # Create sample_packs table
    op.create_table(
        'sample_packs',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('bpm', sa.Integer(), nullable=True),
        sa.Column('key', sa.String(10), nullable=True),
        sa.Column('status', sa.String(20), sa.ForeignKey('sample_pack_status_enum.value'), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), onupdate=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )
    
    # Create samples table
    op.create_table(
        'samples',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False, unique=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('sample_rate', sa.Integer(), nullable=True),
        sa.Column('bit_depth', sa.Integer(), nullable=True),
        sa.Column('channels', sa.Integer(), nullable=True),
        sa.Column('bpm', sa.Float(), nullable=True),
        sa.Column('key', sa.String(10), nullable=True),
        sa.Column('is_loop', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('sample_type', sa.String(20), sa.ForeignKey('sample_type_enum.value'), nullable=False, server_default='one_shot'),
        sa.Column('is_processed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('sample_pack_id', sa.Integer(), sa.ForeignKey('sample_packs.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )
    
    # Create sample_category_association table
    op.create_table(
        'sample_category_association',
        sa.Column('sample_id', sa.Integer(), sa.ForeignKey('samples.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('sample_categories.id', ondelete='CASCADE'), primary_key=True),
    )
    
    # Create midi_files table
    op.create_table(
        'midi_files',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False, unique=True),
        sa.Column('bpm', sa.Float(), nullable=True),
        sa.Column('key', sa.String(10), nullable=True),
        sa.Column('sample_pack_id', sa.Integer(), sa.ForeignKey('sample_packs.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )
    
    # Create bill_of_materials table
    op.create_table(
        'bill_of_materials',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sample_pack_id', sa.Integer(), sa.ForeignKey('sample_packs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), onupdate=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )
    
    # Create bom_items table
    op.create_table(
        'bom_items',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('bom_id', sa.Integer(), sa.ForeignKey('bill_of_materials.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), onupdate=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )
    
    # Add any additional indexes
    op.create_index(op.f('ix_samples_sample_pack_id'), 'samples', ['sample_pack_id'], unique=False)
    op.create_index(op.f('ix_midi_files_sample_pack_id'), 'midi_files', ['sample_pack_id'], unique=False)
    op.create_index(op.f('ix_bill_of_materials_sample_pack_id'), 'bill_of_materials', ['sample_pack_id'], unique=False)
    op.create_index(op.f('ix_bom_items_bom_id'), 'bom_items', ['bom_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes first
    op.drop_index(op.f('ix_bom_items_bom_id'), table_name='bom_items')
    op.drop_index(op.f('ix_bill_of_materials_sample_pack_id'), table_name='bill_of_materials')
    op.drop_index(op.f('ix_midi_files_sample_pack_id'), table_name='midi_files')
    op.drop_index(op.f('ix_samples_sample_pack_id'), table_name='samples')
    
    # Drop tables in reverse order of creation
    op.drop_table('bom_items')
    op.drop_table('bill_of_materials')
    op.drop_table('midi_files')
    op.drop_table('sample_category_association')
    op.drop_table('samples')
    op.drop_table('sample_packs')
    op.drop_table('sample_categories')
    
    # Drop enum types
    op.drop_table('sample_pack_status_enum')
    op.drop_table('sample_type_enum')
