"""
Script PONCTUEL de reclassement des catégories d'alerte — à exécuter UNE fois
après avoir appliqué la migration qui ajoute les catégories Sécurité,
Réglementation et Recherche (alembic upgrade head).

Ce que fait ce script :
  1. Sauvegarde les anciennes catégories (id, ancienne_categorie) dans un CSV
     horodaté sous backend/scripts/ — pour pouvoir revenir en arrière.
  2. Reclasse TOUS les articles avec les nouveaux labels zero-shot et le nouveau
     seuil (ALERT_CONFIDENCE_THRESHOLD), par petits lots avec un commit par lot.
  3. Affiche la répartition AVANT et APRÈS, ainsi que la liste des articles dont
     la catégorie a changé (titre, ancienne catégorie, nouvelle catégorie).

Garanties (voulues par le cahier des charges) :
  - Ne modifie QUE `alert_category`. Le modèle Article n'a PAS de colonne de score
    pour la catégorie d'alerte (seul `sentiment_score` existe, qui concerne le
    sentiment) : il n'y a donc rien d'autre à mettre à jour.
  - N'appelle JAMAIS Ollama (aucun résumé) : uniquement le classifieur zero-shot.
    Aucun risque de plantage mémoire lié au LLM.
  - Ne touche PAS : sentiment, sentiment_score, summary, is_processed,
    processing_error, is_critical, entities, embeddings.

Usage (depuis le dossier backend/) :
    venv/Scripts/python.exe scripts/reclassify_alert_categories.py

Option : ajouter --dry-run pour simuler sans rien écrire en base (la sauvegarde
CSV est quand même produite, et la répartition APRÈS est celle qui SERAIT obtenue).
"""

import csv
import os
import sys
import time
from collections import Counter
from datetime import datetime

# La console Windows est souvent en cp1252 : certains titres contiennent des
# caractères Unicode (tiret insécable, guillemets typographiques…) qui feraient
# planter print(). On force donc la sortie en UTF-8 (avec repli "replace").
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# Rendre le package "app" importable (le script est dans backend/scripts/).
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
import app.models as models
from app.models import AlertCategoryEnum
# On importe UNIQUEMENT le classifieur de catégorie (Groq) : jamais generate_summary
# (Ollama), jamais l'analyse de sentiment. Seule alert_category sera modifiée.
from app.services.nlp_pipeline import (
    classify_alert_category,
    ALERT_CATEGORY_MODEL,
    ALERT_CATEGORY_MODEL_FALLBACK,
)

BATCH_SIZE = 20
# Courte pause entre deux appels Groq pour respecter les limites de débit (rate limit).
SLEEP_BETWEEN_CALLS = float(os.getenv("RECLASSIFY_SLEEP", "0.4"))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _label(cat) -> str:
    """Libellé affiché d'une catégorie (gère None)."""
    return cat.value if cat is not None else "Non classé"


def print_distribution(title: str, counter: Counter, total: int) -> None:
    print(f"\n=== {title} ===")
    for cat, n in counter.most_common():
        pct = (100 * n / total) if total else 0
        print(f"  {cat:22} {n:4}  ({pct:.0f}%)")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db = SessionLocal()
    try:
        articles = db.query(models.Article).order_by(models.Article.id).all()
        total = len(articles)
        print(f"Classifieur : Groq  (principal={ALERT_CATEGORY_MODEL}, repli={ALERT_CATEGORY_MODEL_FALLBACK})")
        print(f"Articles à reclasser : {total}")
        if dry_run:
            print(">>> MODE DRY-RUN : aucune écriture en base <<<")

        # ─── Répartition AVANT ───
        before = Counter(_label(a.alert_category) for a in articles)
        print_distribution("Répartition AVANT", before, total)

        # ─── Sauvegarde des anciennes catégories (rollback) ───
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(SCRIPTS_DIR, f"backup_alert_categories_{ts}.csv")
        with open(backup_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["id", "ancienne_categorie"])
            for a in articles:
                writer.writerow([a.id, _label(a.alert_category)])
        print(f"\nSauvegarde des anciennes catégories : {backup_path}")

        # ─── Reclassement par lots ───
        after = Counter()
        changes = []           # (id, titre, ancienne, nouvelle)
        from_nonclasse = 0     # passés de "Non classé" -> vraie catégorie

        for start in range(0, total, BATCH_SIZE):
            batch = articles[start:start + BATCH_SIZE]
            for a in batch:
                old_label = _label(a.alert_category)
                text = f"{a.title}. {a.content or ''}"
                result = classify_alert_category(text)   # Groq : ne lève jamais, repli "Non classé"
                new_label = result["category"]
                if SLEEP_BETWEEN_CALLS > 0:
                    time.sleep(SLEEP_BETWEEN_CALLS)

                if new_label != old_label:
                    changes.append((a.id, a.title, old_label, new_label))
                    if old_label == "Non classé" and new_label != "Non classé":
                        from_nonclasse += 1
                    if not dry_run:
                        # SEULE modification : alert_category.
                        a.alert_category = AlertCategoryEnum(new_label)

                after[new_label] += 1

            if not dry_run:
                db.commit()
            done = min(start + BATCH_SIZE, total)
            print(f"  ...{done}/{total} traités")

        # ─── Répartition APRÈS ───
        print_distribution("Répartition APRÈS", after, total)

        # ─── Articles dont la catégorie a changé ───
        print(f"\n=== Articles dont la catégorie a changé ({len(changes)}) ===")
        for _id, title, old, new in changes:
            print(f"  [{_id}] {old} -> {new}")
            print(f"        {title[:100]}")

        # ─── Résumé ───
        nc_before = before.get("Non classé", 0)
        nc_after = after.get("Non classé", 0)
        print("\n=== Résumé ===")
        print(f"  Non classé : {nc_before} -> {nc_after}  (variation : {nc_after - nc_before:+d})")
        print(f"  Articles passés de 'Non classé' à une vraie catégorie : {from_nonclasse}")
        print(f"  Total d'articles ayant changé de catégorie            : {len(changes)}")
        if dry_run:
            print("\n  (DRY-RUN : aucune modification n'a été écrite en base.)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
