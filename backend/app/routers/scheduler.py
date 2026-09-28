"""Endpoints de pilotage du scheduler (statut + déclenchement manuel)."""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.config import COLLECT_INTERVAL_HOURS
from app.services import scheduler as scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status", response_model=schemas.SchedulerStatusResponse)
def scheduler_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Prochaine exécution prévue + historique des 10 derniers cycles."""
    history = (
        db.query(models.SchedulerRun)
        .order_by(models.SchedulerRun.started_at.desc())
        .limit(10)
        .all()
    )
    next_run = scheduler_service.get_next_run_time()
    return schemas.SchedulerStatusResponse(
        scheduler_running=next_run is not None,
        next_run=next_run,
        interval_hours=COLLECT_INTERVAL_HOURS,
        history=history,
    )


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
def scheduler_trigger(current_user: models.User = Depends(require_admin)):
    """
    Déclenche immédiatement un cycle complet (collecte → NLP → indexation), en
    tâche de fond. La réponse revient tout de suite ; suivez l'avancement via
    GET /scheduler/status (un nouveau SchedulerRun y apparaîtra).
    """
    triggered = scheduler_service.trigger_now()
    if not triggered:
        return {"message": "Scheduler non actif : impossible de déclencher un cycle.", "triggered": False}
    return {"message": "Cycle déclenché en arrière-plan. Suivez /scheduler/status.", "triggered": True}
