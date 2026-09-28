"""
Envoi d'alertes par email (SMTP) et/ou webhook Slack/Discord.

Principes :
- Un seul essai par canal (pas de retry complexe pour l'instant).
- Aucune erreur d'envoi ne doit JAMAIS remonter au pipeline NLP : toutes les
  fonctions d'envoi capturent leurs exceptions, loggent, et renvoient un statut.
- Si un canal n'est pas configuré (SMTP_HOST ou SLACK_WEBHOOK_URL absent), il est
  simplement ignoré. Un avertissement est loggé UNE fois au démarrage
  (log_notification_startup_state), pas à chaque article.
"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Dict, Optional

import requests
from sqlalchemy.orm import Session

import app.models as models
from app.config import (
    ALERT_CHANNEL,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ALERT_EMAIL_TO,
    SLACK_WEBHOOK_URL,
)

logger = logging.getLogger(__name__)


# ─── État au démarrage (avertissements loggés UNE seule fois) ─────────

def log_notification_startup_state() -> None:
    if ALERT_CHANNEL == "none":
        logger.info("Alertes désactivées (ALERT_CHANNEL=none).")
        return
    if ALERT_CHANNEL in ("email", "both") and (not SMTP_HOST or not ALERT_EMAIL_TO):
        logger.warning(
            "ALERT_CHANNEL='%s' inclut l'email mais SMTP_HOST/ALERT_EMAIL_TO n'est pas "
            "configuré : aucun email ne sera envoyé.", ALERT_CHANNEL
        )
    if ALERT_CHANNEL in ("slack", "both") and not SLACK_WEBHOOK_URL:
        logger.warning(
            "ALERT_CHANNEL='%s' inclut Slack mais SLACK_WEBHOOK_URL n'est pas "
            "configuré : aucun webhook ne sera envoyé.", ALERT_CHANNEL
        )


# ─── Envoi bas niveau (retourne (succès, message), ne lève jamais) ────

def _send_email(subject: str, body: str) -> (bool, str):
    if not SMTP_HOST or not ALERT_EMAIL_TO:
        return False, "désactivé (SMTP_HOST/ALERT_EMAIL_TO absent)"
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_USER or "veille@localhost"
        msg["To"] = ALERT_EMAIL_TO
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True, "envoyé"
    except Exception as e:  # noqa: BLE001 — on ne veut JAMAIS propager
        logger.error("Échec de l'envoi de l'email d'alerte : %s", e)
        return False, f"échec: {e}"


def _send_slack(text: str) -> (bool, str):
    if not SLACK_WEBHOOK_URL:
        return False, "désactivé (SLACK_WEBHOOK_URL absent)"
    try:
        # "text" est lu par Slack, "content" par Discord : envoyer les deux rend
        # le webhook compatible avec l'un comme l'autre (chacun ignore l'autre clé).
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": text, "content": text}, timeout=10)
        if resp.status_code >= 300:
            logger.error("Webhook Slack/Discord a répondu %s : %s", resp.status_code, resp.text[:200])
            return False, f"échec: HTTP {resp.status_code}"
        return True, "envoyé"
    except requests.exceptions.RequestException as e:
        logger.error("Échec de l'envoi du webhook Slack/Discord : %s", e)
        return False, f"échec: {e}"


# ─── Construction du message ──────────────────────────────────────────

def _format_alert(competitor: str, category: str, body_text: str, url: str,
                  published_at: str, is_test: bool = False) -> (str, str):
    tag = " TEST" if is_test else ""
    subject = f"[Veille{tag}] Alerte {category} — {competitor}"
    header = "*** CECI EST UNE ALERTE DE TEST ***\n\n" if is_test else "Nouvel événement critique détecté\n\n"
    body = (
        f"{header}"
        f"Concurrent      : {competitor}\n"
        f"Catégorie       : {category}\n"
        f"Publié le       : {published_at}\n\n"
        f"{body_text}\n\n"
        f"Article : {url}"
    )
    return subject, body


def _dispatch(subject: str, body: str) -> Dict[str, str]:
    """Envoie sur le(s) canal(aux) configuré(s). Retourne un statut par canal."""
    results: Dict[str, str] = {}
    if ALERT_CHANNEL in ("email", "both"):
        _, msg = _send_email(subject, body)
        results["email"] = msg
    if ALERT_CHANNEL in ("slack", "both"):
        _, msg = _send_slack(body)
        results["slack"] = msg
    if not results:
        results["info"] = "aucun canal actif (ALERT_CHANNEL=none)"
    return results


def _category_enabled(db: Session, category: str) -> bool:
    """Une catégorie est alertable si sa config n'existe pas encore, ou si enabled=True."""
    cfg = db.query(models.AlertConfig).filter(models.AlertConfig.category == category).first()
    return True if cfg is None else bool(cfg.enabled)


# ─── API publique ─────────────────────────────────────────────────────

def notify_critical_article(db: Session, article: models.Article) -> None:
    """
    Envoie une alerte pour un article critique. Ne lève JAMAIS d'exception :
    en cas d'échec, on log et on continue (le pipeline NLP n'est pas bloqué).
    """
    try:
        if ALERT_CHANNEL == "none":
            return
        category = article.alert_category.value if article.alert_category else "Non classé"
        if not _category_enabled(db, category):
            logger.info("Alerte non envoyée : catégorie '%s' désactivée (article %s).", category, article.id)
            return

        subject, body = _format_alert(
            competitor=article.competitor.value if article.competitor else "Inconnu",
            category=category,
            body_text=article.summary or article.title or "(sans contenu)",
            url=article.url or "—",
            published_at=article.published_at.isoformat() if article.published_at else "—",
        )
        results = _dispatch(subject, body)
        logger.info("Alerte article %s (%s) — résultats: %s", article.id, category, results)
    except Exception:  # noqa: BLE001 — garde-fou ultime, ne bloque jamais le pipeline
        logger.error("Erreur inattendue lors de l'envoi d'alerte (article %s) — ignorée.",
                     getattr(article, "id", None), exc_info=True)


def send_test_alert() -> Dict[str, str]:
    """Envoie une notification de TEST (données factices) sur le(s) canal(aux) configuré(s)."""
    subject, body = _format_alert(
        competitor="CONCURRENT TEST",
        category="Finance",
        body_text="Ceci est une alerte de TEST envoyée manuellement pour vérifier la configuration "
                  "des notifications. Aucune action requise.",
        url="https://example.com/article-de-test",
        published_at="2026-01-01T00:00:00",
        is_test=True,
    )
    return _dispatch(subject, body)
