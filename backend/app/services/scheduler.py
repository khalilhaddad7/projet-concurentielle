"""
Planificateur (APScheduler) de la collecte automatique.

Un BackgroundScheduler exécute un cycle complet (collecte → NLP → indexation)
toutes les COLLECT_INTERVAL_HOURS heures. Il démarre/s'arrête avec le lifespan
de FastAPI. Le déclenchement manuel réutilise le même job.
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.database import SessionLocal
from app.config import COLLECT_INTERVAL_HOURS
from app.services.pipeline import execute_full_cycle

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None
_JOB_ID = "collect_cycle"


def _run_cycle_job() -> None:
    """Job exécuté par le scheduler : ouvre sa propre session DB et lance un cycle."""
    db = SessionLocal()
    try:
        execute_full_cycle(db)
    except Exception:  # noqa: BLE001 — un job planté ne doit pas tuer le scheduler
        logger.error("Erreur non gérée dans le job planifié.", exc_info=True)
    finally:
        db.close()


def start_scheduler() -> None:
    """Démarre le scheduler et programme le cycle récurrent (idempotent)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_cycle_job,
        trigger=IntervalTrigger(hours=COLLECT_INTERVAL_HOURS),
        id=_JOB_ID,
        replace_existing=True,
        max_instances=1,       # jamais deux cycles en parallèle
        coalesce=True,         # regroupe les exécutions manquées en une seule
    )
    _scheduler.start()
    logger.info("Scheduler démarré : cycle toutes les %s heure(s).", COLLECT_INTERVAL_HOURS)


def shutdown_scheduler() -> None:
    """Arrête proprement le scheduler (appelé à l'extinction de l'app)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler arrêté.")
    _scheduler = None


def get_next_run_time() -> Optional[datetime]:
    """Prochaine exécution planifiée, ou None si le scheduler n'est pas actif."""
    if _scheduler is None or not _scheduler.running:
        return None
    job = _scheduler.get_job(_JOB_ID)
    return job.next_run_time if job else None


def trigger_now() -> bool:
    """
    Déclenche un cycle immédiatement (dans le threadpool du scheduler, non bloquant).
    Retourne False si le scheduler n'est pas actif.
    """
    if _scheduler is None or not _scheduler.running:
        return False
    _scheduler.add_job(
        _run_cycle_job,
        trigger=DateTrigger(run_date=datetime.utcnow()),
        id=f"manual_{datetime.utcnow().timestamp()}",
        max_instances=1,
    )
    return True
