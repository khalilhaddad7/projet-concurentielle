"""
Configuration centralisée et chargement des variables d'environnement.

Ce module charge le fichier .env une seule fois, valide la présence des
variables critiques au démarrage, et expose les valeurs aux autres modules.
Importer ce module suffit à déclencher la validation : si une variable
essentielle manque, une erreur claire est levée immédiatement plutôt que
de laisser l'application planter plus tard (connexion DB, appel API...).
"""

import os

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
