"""Add Bedrijf table and link to Abonnement

Revision ID: 3f5a1adfe640
Revises: a6728336499e
Create Date: 2025-06-19 21:23:36.130035
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f5a1adfe640'
down_revision = 'a6728336499e'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Maak de bedrijfstabel aan
    op.create_table(
        'bedrijf',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('naam', sa.String(length=150), nullable=False, unique=True),
        sa.Column('website_url', sa.String(length=255), nullable=True),
        sa.Column('logo', sa.String(length=200), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('telefoon', sa.String(length=50), nullable=True),
        sa.Column('kvk_nummer', sa.String(length=50), nullable=True),
    )

    # 2) Voeg de FK naar abonnement toe, mét constraint-naam
    with op.batch_alter_table('abonnement') as batch_op:
        batch_op.add_column(sa.Column('bedrijf_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            'fk_abonnement_bedrijf',   # eigen naam
            'bedrijf',
            ['bedrijf_id'],
            ['id'],
        )

    # 3) Slug-constraints op categorie/subcategorie (optioneel kun je hier
    #    ook expliciete namen meegeven ipv None)
    with op.batch_alter_table('categorie') as batch_op:
        batch_op.alter_column('slug',
            existing_type=sa.TEXT(),
            type_=sa.String(length=100),
            nullable=False,
        )
        batch_op.create_unique_constraint('uq_categorie_slug', ['slug'])

    with op.batch_alter_table('subcategorie') as batch_op:
        batch_op.alter_column('slug',
            existing_type=sa.TEXT(),
            type_=sa.String(length=100),
            nullable=False,
        )
        batch_op.create_unique_constraint('uq_subcategorie_slug', ['slug'])


def downgrade():
    # Rol slug-wijzigingen terug
    with op.batch_alter_table('subcategorie') as batch_op:
        batch_op.drop_constraint('uq_subcategorie_slug', type_='unique')
        batch_op.alter_column('slug',
            existing_type=sa.String(length=100),
            type_=sa.TEXT(),
            nullable=True,
        )

    with op.batch_alter_table('categorie') as batch_op:
        batch_op.drop_constraint('uq_categorie_slug', type_='unique')
        batch_op.alter_column('slug',
            existing_type=sa.String(length=100),
            type_=sa.TEXT(),
            nullable=True,
        )

    # Verwijder de FK en kolom uit abonnement
    with op.batch_alter_table('abonnement') as batch_op:
        batch_op.drop_constraint('fk_abonnement_bedrijf', type_='foreignkey')
        batch_op.drop_column('bedrijf_id')

    # Verwijder de bedrijfstabel
    op.drop_table('bedrijf')

