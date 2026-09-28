"""
Script de nettoyage PONCTUEL de cohérence des données — à exécuter UNE SEULE FOIS.

Ce n'est PAS une route API : c'est un correctif ponctuel pour rattraper l'état
laissé par deux bugs déjà corrigés.

Il fait deux choses :

  1. Nettoie le `processing_error` résiduel du bug déjà corrigé sur les catégories
     d'alerte (messages du type "... is not a valid AlertCategoryEnum"). Ce bug
     n'existe plus (le mapping des catégories a été corrigé), mais son message
     traîne encore dans la colonne processing_error de certains articles.

  2. Backfill `is_embedded=True` et `embedding_id` pour tous les articles déjà
     présents dans ChromaDB mais dont ces colonnes n'avaient jamais été renseignées
     (ils ont été indexés avant la correction de index_article()). L'id ChromaDB
     d'un article est str(article.id) ; on interroge ChromaDB pour retrouver les
     ids réellement présents.

Usage (depuis le dossier backend/) :
    venv/Scripts/python.exe scripts/cleanup_data_consistency.py
"""

import os
import sys

# Rendre le package "app" importable (le script est dans backend/scripts/).
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
import app.models as models
from app.services.rag_engine import get_articles_collection

# Motif SQL (ILIKE) identifiant l'erreur résiduelle du bug déjà corrigé.
RESIDUAL_ERROR_PATTERN = "%is not a valid AlertCategoryEnum%"


def clean_residual_errors(db) -> int:
    """Vide processing_error pour les articles portant l'erreur résiduelle."""
    articles = (
        db.query(models.Article)
        .filter(models.Article.processing_error.ilike(RESIDUAL_ERROR_PATTERN))
        .all()
    )
    for article in articles:
        article.processing_error = None
    db.commit()
    return len(articles)


def backfill_embeddings(db) -> tuple[int, int]:
    """
    Backfill is_embedded/embedding_id à partir des ids réellement présents dans
    ChromaDB. Retourne (nb_docs_dans_chromadb, nb_articles_mis_a_jour).
    """
    collection = get_articles_collection()
    chroma_ids = collection.get().get("ids", [])

    updated = 0
    for chroma_id in chroma_ids:
        try:
            article_id = int(chroma_id)
        except (ValueError, TypeError):
            # Id ChromaDB non numérique : on ignore (ne correspond pas à un article).
            continue

        article = db.query(models.Article).filter(models.Article.id == article_id).first()
        if article is None:
            # Doc présent dans ChromaDB mais article supprimé en base : on ignore.
            continue

        if not article.is_embedded or article.embedding_id != chroma_id:
            article.is_embedded = True
            article.embedding_id = chroma_id
            updated += 1

    db.commit()
    return len(chroma_ids), updated


def main() -> None:
    db = SessionLocal()
    try:
        cleaned = clean_residual_errors(db)
        total_in_chroma, backfilled = backfill_embeddings(db)

        print("=== Nettoyage de cohérence des données ===")
        print(f"processing_error résiduel nettoyé : {cleaned} article(s)")
        print(f"documents présents dans ChromaDB   : {total_in_chroma}")
        print(f"is_embedded/embedding_id backfillés : {backfilled} article(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
