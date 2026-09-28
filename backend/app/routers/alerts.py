"""Endpoints de configuration des alertes + envoi d'une alerte de test."""

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
from app.models import AlertCategoryEnum
from app.database import get_db
from app.auth.dependencies import require_admin
from app.services import notifications

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Alertes"])


@router.get("/alert-config", response_model=List[schemas.AlertConfigResponse])
def list_alert_config(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Liste la configuration d'alerte par catégorie."""
    return db.query(models.AlertConfig).order_by(models.AlertConfig.category).all()


@router.put("/alert-config/{category}", response_model=schemas.AlertConfigResponse)
def update_alert_config(
    category: AlertCategoryEnum,
    payload: schemas.AlertConfigUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Active/désactive les alertes pour une catégorie (créée si absente)."""
    cfg = db.query(models.AlertConfig).filter(models.AlertConfig.category == category.value).first()
    if cfg is None:
        cfg = models.AlertConfig(category=category.value, enabled=payload.enabled)
        db.add(cfg)
    else:
        cfg.enabled = payload.enabled
    db.commit()
    db.refresh(cfg)
    return cfg


@router.post("/alerts/test")
def send_test_alert(current_user: models.User = Depends(require_admin)):
    """
    Envoie une notification de TEST (données factices) sur le(s) canal(aux)
    configuré(s), pour vérifier SMTP/Slack sans attendre un vrai article critique.
    """
    results = notifications.send_test_alert()
    return {"message": "Alerte de test envoyée (voir le détail par canal).", "results": results}
