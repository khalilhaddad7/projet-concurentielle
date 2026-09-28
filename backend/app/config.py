"""
Configuration centralisée et chargement des variables d'environnement.

Ce module charge le fichier .env une seule fois, valide la présence des
variables critiques au démarrage, et expose les valeurs aux autres modules.
Importer ce module suffit à déclencher la validation : si une variable
essentielle manque, une erreur claire est levée immédiatement plutôt que
de laisser l'application planter plus tard (connexion DB, appel API...).
"""

import logging
import os
import secrets

logger = logging.getLogger(__name__)

# ─── Vérification SSL via le magasin de certificats Windows ──────────
# Sur les postes protégés par un antivirus/proxy qui inspecte le trafic HTTPS,
# le certificat racine injecté n'est pas reconnu par le bundle « certifi »
# d'OpenSSL (erreurs « CERTIFICATE_VERIFY_FAILED » / « Basic Constraints not
# marked critical »). Cela faisait échouer les appels sortants : NewsAPI
# (collecte, via requests) et Groq (chatbot RAG, via httpx).
# « truststore » délègue la vérification au magasin natif de Windows — le même
# que celui utilisé par curl et les navigateurs — ce qui accepte ce certificat.
# On l'active AVANT tout appel réseau (config est le premier module chargé).
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    # truststore absent : on retombe sur la vérification OpenSSL par défaut.
    # Installer avec : pip install truststore
    pass

from dotenv import load_dotenv

# Charge les variables depuis backend/.env (une seule fois pour tout le projet)
load_dotenv()

# Variables obligatoires : nom -> description affichée en cas d'absence
REQUIRED_ENV_VARS = {
    "DATABASE_URL": "URL PostgreSQL, ex: postgresql://user:password@localhost:5432/veille_db",
    "GROQ_API_KEY": "Clé API Groq utilisée pour la génération de réponses du chatbot RAG",
    "NEWSAPI_KEY": "Clé API NewsAPI utilisée pour la collecte des articles",
}


def validate_env() -> None:
    """
    Vérifie que toutes les variables critiques sont définies et non vides.
    Lève une RuntimeError agrégée et lisible listant tout ce qui manque.
    """
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        details = "\n".join(
            f"  - {name} : {REQUIRED_ENV_VARS[name]}" for name in missing
        )
        raise RuntimeError(
            "Variables d'environnement manquantes ou vides.\n"
            "Copiez backend/.env.example vers backend/.env puis renseignez :\n"
            f"{details}"
        )


# Validation au chargement du module (donc au démarrage de l'application)
validate_env()

# Valeurs exposées aux autres modules (garanties présentes après validation)
DATABASE_URL = os.environ["DATABASE_URL"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
NEWSAPI_KEY = os.environ["NEWSAPI_KEY"]

# Variables optionnelles (valeur par défaut si absentes)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


# ─── Authentification / JWT ──────────────────────────────────────────

def _persist_env_var(name: str, value: str) -> None:
    """
    Ajoute une ligne NAME=value à la fin de backend/.env.

    Utilisé pour persister un secret généré automatiquement afin qu'il reste
    stable entre deux redémarrages (sinon tous les tokens seraient invalidés
    à chaque relance de l'API).
    """
    # config.py se trouve dans backend/app/ ; le .env est dans backend/.
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f"\n{name}={value}\n")
    except OSError as e:
        logger.warning("Impossible d'écrire %s dans %s : %s", name, env_path, e)


# Secret de signature des JWT. S'il n'existe pas encore, on en génère un fort
# et aléatoire, puis on l'ajoute à backend/.env pour qu'il reste stable.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = secrets.token_urlsafe(64)
    os.environ["JWT_SECRET_KEY"] = JWT_SECRET_KEY
    _persist_env_var("JWT_SECRET_KEY", JWT_SECRET_KEY)
    logger.warning(
        "JWT_SECRET_KEY absent : un secret aléatoire fort a été généré et ajouté "
        "à backend/.env. Ne le partagez jamais et ne le committez pas."
    )

# Algorithme de signature (symétrique HMAC-SHA256).
JWT_ALGORITHM = "HS256"

# Durées d'expiration des tokens (surchargeable via l'environnement).
#  - Access token court (30 min par défaut) : limite la fenêtre d'exploitation
#    s'il est volé.
#  - Refresh token long (7 jours par défaut) : évite de re-saisir le mot de passe
#    trop souvent.
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Compte admin créé automatiquement au démarrage (optionnel).
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# ─── Collecte planifiée (APScheduler) ────────────────────────────────
# Intervalle (en heures) entre deux cycles automatiques collecte→NLP→indexation.
# Valeur par défaut sûre : 6 heures.
try:
    COLLECT_INTERVAL_HOURS = float(os.getenv("COLLECT_INTERVAL_HOURS", "6"))
    if COLLECT_INTERVAL_HOURS <= 0:
        raise ValueError
except (TypeError, ValueError):
    logger.warning("COLLECT_INTERVAL_HOURS invalide : repli sur 6 heures.")
    COLLECT_INTERVAL_HOURS = 6.0


# ─── Alertes (email SMTP + webhook Slack/Discord) ────────────────────
# Canal(aux) d'alerte : "email", "slack", "both" ou "none" (défaut sûr : "none").
ALERT_CHANNEL = os.getenv("ALERT_CHANNEL", "none").strip().lower()
if ALERT_CHANNEL not in ("email", "slack", "both", "none"):
    logger.warning("ALERT_CHANNEL invalide (%r) : repli sur 'none'.", ALERT_CHANNEL)
    ALERT_CHANNEL = "none"

# Paramètres SMTP (email). Si SMTP_HOST est vide, l'email est désactivé.
SMTP_HOST = os.getenv("SMTP_HOST") or None
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER") or None
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or None
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO") or None

# Webhook Slack (ou Discord) entrant. Si vide, ce canal est désactivé.
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL") or None
