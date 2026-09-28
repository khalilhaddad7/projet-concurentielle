"""ajout categories securite reglementation recherche

Revision ID: 3129affbb43c
Revises: b6e369cf4155
Create Date: 2026-09-28 03:56:51.352426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3129affbb43c'
down_revision: Union[str, Sequence[str], None] = 'b6e369cf4155'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Nouvelles valeurs à ajouter au type enum PostgreSQL "alertcategoryenum".
# IMPORTANT : ce sont les NOMS des membres de AlertCategoryEnum (ce que SQLAlchemy
# stocke réellement en base), pas les libellés affichés ("Sécurité", etc.).
NEW_VALUES = ("securite", "reglementation", "recherche")
ENUM_NAME = "alertcategoryenum"


def upgrade() -> None:
    """
    Ajoute trois valeurs au type enum PostgreSQL alertcategoryenum.

    « ALTER TYPE ... ADD VALUE » ne peut pas s'exécuter à l'intérieur d'un bloc
    transactionnel (PostgreSQL refuse : "ALTER TYPE ... ADD cannot run inside a
    transaction block"). Alembic ouvre chaque migration dans une transaction ; on
    utilise donc autocommit_block() pour exécuter ces ordres HORS transaction.
    « IF NOT EXISTS » rend la migration idempotente (ré-exécutable sans erreur).

    Cette migration est purement ADDITIVE : elle ne supprime ni ne renomme aucune
    valeur, colonne ou table existante. Les données existantes sont donc intactes.
    """
    with op.get_context().autocommit_block():
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE {ENUM_NAME} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """
    Pas de downgrade automatique.

    PostgreSQL ne permet pas de retirer une valeur d'un type enum par un simple
    « ALTER TYPE ... DROP VALUE » : il faudrait recréer le type et réécrire toutes
    les colonnes qui l'utilisent, opération risquée pour les données. Comme ces
    valeurs sont purement additives et sans effet tant qu'aucune ligne ne les
    utilise, on laisse le downgrade sans action plutôt que de tenter une
    reconstruction destructrice.
    """
    pass
