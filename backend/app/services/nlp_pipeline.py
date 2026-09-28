import os

# Les modèles sont déjà présents dans le cache local HuggingFace. On force le
# mode hors-ligne AVANT d'importer transformers : cela supprime les requêtes
# réseau de vérification au démarrage qui, en cas d'échec SSL, provoquaient un
# long blocage après "Loading weights: 100%" (retries répétés).
# Pour réactiver le réseau : définir HF_HUB_OFFLINE=0 / TRANSFORMERS_OFFLINE=0.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from typing import Dict, List, Any, Optional
import ollama

# ─── Chargement paresseux (lazy) des modèles NLP ─────────────────────
# Les modèles spaCy et CamemBERT sont volumineux (plusieurs Go en RAM une fois
# torch chargé). Auparavant ils étaient chargés au niveau module, donc dès
# l'import par main.py : l'API entière refusait alors de démarrer si la mémoire
# manquait. Désormais chaque modèle n'est chargé qu'au PREMIER appel réel de la
# fonction qui l'utilise (donc au premier /process-nlp), puis mis en cache et
# réutilisé. Conséquence : l'API démarre toujours et instantanément ; la RAM des
# modèles n'est consommée que lorsqu'on lance effectivement un traitement.
# Les imports lourds (spacy, transformers→torch) sont aussi déférés dans les
# chargeurs pour que le simple import du module reste léger.
#
# NOTE : la classification des catégories d'alerte n'utilise PLUS de modèle local
# (mDeBERTa zero-shot). Elle est désormais confiée à Groq (LLM distant), bien plus
# fiable sur des titres/contenus en français. spaCy et CamemBERT restent en local.
_nlp_fr = None
_sentiment_pipeline = None


def get_nlp_fr():
    """Charge (une seule fois, à la demande) le modèle spaCy français."""
    global _nlp_fr
    if _nlp_fr is None:
        import spacy
        print("[NLP] Chargement du modèle spaCy fr_core_news_md...")
        _nlp_fr = spacy.load("fr_core_news_md")
    return _nlp_fr


def get_sentiment_pipeline():
    """Charge (une seule fois, à la demande) le pipeline de sentiment CamemBERT."""
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        from transformers import pipeline
        print("[NLP] Chargement du modèle de sentiment CamemBERT...")
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="cmarkea/distilcamembert-base-sentiment",
            tokenizer="cmarkea/distilcamembert-base-sentiment",
            device=-1,  # CPU explicite (pas de GPU sur cette machine)
        )
    return _sentiment_pipeline


# Modèle Ollama utilisé pour le résumé automatique
OLLAMA_MODEL = "llama3.2:3b"

# Le modèle renvoie des labels type "1 star"..."5 stars" (ou "positive"/"negative"/"neutral"
# selon la version) : on normalise ici vers les valeurs exactes de ton SentimentEnum.
LABEL_MAPPING = {
    "1 star": "Négatif",
    "2 stars": "Négatif",
    "3 stars": "Neutre",
    "4 stars": "Positif",
    "5 stars": "Positif",
    "negative": "Négatif",
    "neutral": "Neutre",
    "positive": "Positif",
}

# ─── Classification des catégories d'alerte via Groq (LLM distant) ───
# On a abandonné le classifieur zero-shot local (mDeBERTa) : il était trop peu
# fiable sur des titres/contenus en français (≈4/10 sur un jeu de test), et avait
# tendance à concentrer les articles sur une seule catégorie « fourre-tout ».
# Groq (même fournisseur que le chatbot RAG) atteint 10/10 sur le même jeu de test.
#
# Modèle principal + repli, surchargeables par variables d'environnement. Les deux
# modèles disponibles sur le compte et validés pour cette tâche sont des modèles
# « à raisonnement » (openai/gpt-oss-*) : on leur laisse une marge de max_tokens
# confortable pour éviter les réponses vides observées avec un budget trop serré.
ALERT_CATEGORY_MODEL = os.getenv("ALERT_CATEGORY_MODEL", "openai/gpt-oss-120b")
ALERT_CATEGORY_MODEL_FALLBACK = os.getenv("ALERT_CATEGORY_MODEL_FALLBACK", "openai/gpt-oss-20b")
ALERT_CATEGORY_MAX_TOKENS = int(os.getenv("ALERT_CATEGORY_MAX_TOKENS", "1024"))

# Catégories valides = valeurs de AlertCategoryEnum SAUF "Non classé" (qui n'est
# jamais proposé au modèle : il ne sert que de repli en cas d'échec/réponse invalide).
# Import différé pour éviter tout couplage inutile à l'import du module.
from app.models import AlertCategoryEnum  # noqa: E402

ALERT_CATEGORIES = [c.value for c in AlertCategoryEnum if c != AlertCategoryEnum.non_classe]

# Prompt court en français : 7 catégories, une définition d'une ligne chacune,
# réponse JSON. On demande aussi :
#  - "confiance" (0..1) : confiance du modèle dans la catégorie choisie (indicatif) ;
#  - "critique" (booléen) : l'article rapporte-t-il un ÉVÉNEMENT MAJEUR ? Ce booléen
#    alimente is_critical (voir pipeline). On le distingue volontairement de la
#    confiance : Groq est presque toujours très confiant, donc la confiance seule ne
#    permet pas de repérer les rares événements réellement majeurs.
ALERT_CLASSIFICATION_PROMPT = (
    "Tu es un classifieur d'articles de veille concurrentielle sur l'intelligence artificielle. "
    "Classe l'article dans UNE seule catégorie parmi les sept suivantes :\n"
    "- Produit : lancement ou mise à jour d'un produit, service ou modèle commercial, fonctionnalité, tarifs.\n"
    "- Finance : levée de fonds, investissement, valorisation, chiffre d'affaires, introduction en bourse.\n"
    "- Ressources Humaines : recrutement, départ, licenciement ou réorganisation d'équipe.\n"
    "- Stratégie : partenariat, acquisition, fusion ou décision stratégique d'entreprise.\n"
    "- Sécurité : piratage, faille, cyberattaque, fuite de données ou incident de sécurité.\n"
    "- Réglementation : loi, régulation (AI Act), procès, enquête, décision de justice ou position d'un gouvernement.\n"
    "- Recherche : découverte scientifique, publication de recherche, benchmark ou avancée technique de laboratoire.\n"
    "Indique aussi si l'article rapporte un ÉVÉNEMENT CRITIQUE (critique=true). Sois TRÈS "
    "STRICT : la grande majorité des articles ne sont PAS critiques (critique=false). "
    "Réserve critique=true aux rares événements à fort impact et exceptionnels : incident "
    "de sécurité grave ou fuite de données confirmée, procès ou sanction réglementaire "
    "majeur, levée de fonds ou acquisition de très grande ampleur, crise ou bouleversement "
    "stratégique. Les lancements de produits, changements de prix, mises à jour, résultats "
    "d'étape, tribunes et actualités routinières doivent avoir critique=false.\n"
    'Réponds UNIQUEMENT en JSON, au format '
    '{"categorie": "<une des sept catégories exactes>", "confiance": <nombre entre 0 et 1>, '
    '"critique": <true ou false>}.'
)

# Client Groq chargé paresseusement (une seule instance réutilisée).
_groq_client = None


def get_groq_client():
    """Instancie (une seule fois) le client Groq à partir de GROQ_API_KEY."""
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        from app.config import GROQ_API_KEY
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extrait les entités nommées d'un texte : organisations, personnes, montants, lieux.
    Retourne un dict structuré, ex: {"ORG": [...], "PERSON": [...], "MONEY": [...]}
    """
    if not text:
        return {}

    doc = get_nlp_fr()(text)

    entities: Dict[str, List[str]] = {
        "ORG": [],
        "PERSON": [],
        "MONEY": [],
        "LOC": [],
        "MISC": [],
    }

    for ent in doc.ents:
        label = ent.label_
        value = ent.text.strip()

        if label == "ORG":
            entities["ORG"].append(value)
        elif label == "PER":
            entities["PERSON"].append(value)
        elif label in ("LOC", "GPE"):
            entities["LOC"].append(value)
        elif label == "MISC":
            entities["MISC"].append(value)

    # Dédupliquer tout en gardant l'ordre
    for key in entities:
        entities[key] = list(dict.fromkeys(entities[key]))

    return entities


def extract_financial_amount(text: str) -> Optional[float]:
    """
    Cherche un montant financier dans le texte (en millions de dollars/euros).
    Version simple par regex — à améliorer plus tard si besoin.
    """
    import re

    if not text:
        return None

    pattern = r"(\d+(?:[.,]\d+)?)\s*(million|milliard|billion|M\$|B\$)"
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return None

    number = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()

    if "milliard" in unit or "billion" in unit or "b$" in unit:
        number *= 1000  # convertir en millions

    return number


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyse le sentiment d'un texte avec CamemBERT.
    Retourne {"label": "Positif"|"Négatif"|"Neutre", "score": float}.
    """
    if not text or not text.strip():
        return {"label": None, "score": None}

    truncated_text = text[:512]

    result = get_sentiment_pipeline()(truncated_text)[0]
    raw_label = result["label"].lower()
    score = round(result["score"], 4)

    label = LABEL_MAPPING.get(raw_label, "Neutre")

    return {"label": label, "score": score}


def _groq_classify_once(text: str, model: str) -> Optional[Dict[str, Any]]:
    """
    Un seul appel Groq de classification. Retourne un dict
    {"category": <catégorie valide>, "confidence": float|None} en cas de succès, ou
    None si la réponse est vide / invalide / en erreur (le repli est géré par
    l'appelant). Ne lève JAMAIS d'exception.
    """
    import json

    try:
        response = get_groq_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ALERT_CLASSIFICATION_PROMPT},
                {"role": "user", "content": text[:4000]},
            ],
            temperature=0,
            max_tokens=ALERT_CATEGORY_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()
        if not raw:
            print(f"[NLP] Groq ({model}) a renvoyé une réponse vide.")
            return None

        data = json.loads(raw)
        category = str(data.get("categorie", "")).strip()
        if category not in ALERT_CATEGORIES:
            print(f"[NLP] Groq ({model}) a renvoyé une catégorie invalide : {category!r}")
            return None

        # "confiance" (0..1) : indicative. "critique" (booléen) : alimente is_critical.
        confidence = data.get("confiance")
        try:
            confidence = round(float(confidence), 4) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None

        is_critical = bool(data.get("critique", False))

        return {"category": category, "confidence": confidence, "is_critical": is_critical}
    except Exception as e:  # noqa: BLE001 — jamais propager : le pipeline ne doit pas casser
        print(f"[ERREUR Groq classification] modèle={model} : {e}")
        return None


def classify_alert_category(text: str) -> Dict[str, Any]:
    """
    Classe un article dans l'une des 7 catégories d'alerte via Groq (LLM distant).

    Robustesse :
      - Essaie d'abord le modèle principal (ALERT_CATEGORY_MODEL), puis, si la
        réponse est vide/invalide/en erreur, le modèle de repli
        (ALERT_CATEGORY_MODEL_FALLBACK).
      - Si les deux échouent, renvoie "Non classé" (jamais d'exception) : le
        pipeline n'est donc jamais interrompu par la classification.

    Retour : {"category": str, "confidence": float|None, "is_critical": bool}.
    "is_critical" provient du champ "critique" renvoyé par le modèle (événement
    majeur) et alimente la colonne is_critical dans le pipeline. "confidence" est
    indicative. Un repli "Non classé" n'est jamais critique.
    """
    if not text or not text.strip():
        return {"category": "Non classé", "confidence": None, "is_critical": False}

    for model in (ALERT_CATEGORY_MODEL, ALERT_CATEGORY_MODEL_FALLBACK):
        if not model:
            continue
        result = _groq_classify_once(text, model)
        if result is not None:
            return result

    # Les deux modèles ont échoué : repli sûr.
    return {"category": "Non classé", "confidence": None, "is_critical": False}


def generate_summary(text: str, max_sentences: int = 3) -> Optional[str]:
    """
    Génère un résumé automatique en français via Ollama (LLM local).
    Retourne None si le texte est vide ou si Ollama échoue (ex: non démarré).
    """
    if not text or not text.strip():
        return None

    # On limite la taille du texte envoyé au modèle pour rester rapide
    truncated_text = text[:3000]

    prompt = (
        f"Résume l'article suivant en français, en {max_sentences} phrases maximum, "
        f"de façon factuelle et neutre, sans introduction ni commentaire :\n\n"
        f"{truncated_text}"
    )

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = response["message"]["content"].strip()
        return summary
    except Exception as e:
        print(f"[ERREUR Ollama] Impossible de générer le résumé : {e}")
        return None