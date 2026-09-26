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
# Les modèles spaCy, CamemBERT et mDeBERTa sont volumineux (plusieurs Go en
# RAM une fois torch chargé). Auparavant ils étaient chargés au niveau module,
# donc dès l'import par main.py : l'API entière refusait alors de démarrer si la
# mémoire manquait. Désormais chaque modèle n'est chargé qu'au PREMIER appel réel
# de la fonction qui l'utilise (donc au premier /process-nlp), puis mis en cache
# et réutilisé. Conséquence : l'API démarre toujours et instantanément ; la RAM
# des modèles n'est consommée que lorsqu'on lance effectivement un traitement.
# Les imports lourds (spacy, transformers→torch) sont aussi déférés dans les
# chargeurs pour que le simple import du module reste léger.
_nlp_fr = None
_sentiment_pipeline = None
_zero_shot_classifier = None


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


def get_zero_shot_classifier():
    """Charge (une seule fois, à la demande) le classifieur zero-shot mDeBERTa."""
    global _zero_shot_classifier
    if _zero_shot_classifier is None:
        from transformers import pipeline
        print("[NLP] Chargement du classifieur zero-shot mDeBERTa...")
        _zero_shot_classifier = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
            device=-1,  # CPU explicite
        )
    return _zero_shot_classifier

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

ALERT_LABELS = [
    "un nouveau produit ou une mise à jour technique",
    "une opération financière (levée de fonds, investissement, chiffre d'affaires)",
    "un recrutement, un départ ou une décision liée aux employés",
    "un partenariat, une réglementation, un procès ou une décision stratégique",
]

# Mapping retour vers tes catégories réelles (valeurs de AlertCategoryEnum)
ALERT_LABEL_TO_CATEGORY = {
    "un nouveau produit ou une mise à jour technique": "Produit",
    "une opération financière (levée de fonds, investissement, chiffre d'affaires)": "Finance",
    "un recrutement, un départ ou une décision liée aux employés": "Ressources Humaines",
    "un partenariat, une réglementation, un procès ou une décision stratégique": "Stratégie",
}


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


def classify_alert_category(text: str, confidence_threshold: float = 0.35) -> Dict[str, Any]:
    """
    Classe un article dans l'une des 4 catégories d'alerte via zero-shot classification.
    """
    if not text or not text.strip():
        return {"category": "Non classé", "confidence": None}

    truncated_text = text[:1000]

    result = get_zero_shot_classifier()(
        truncated_text,
        candidate_labels=ALERT_LABELS,
        hypothesis_template="Cet article parle principalement de {}.",
        multi_label=False,
    )

    top_raw_label = result["labels"][0]
    top_score = round(result["scores"][0], 4)

    if top_score < confidence_threshold:
        return {"category": "Non classé", "confidence": top_score}

    category = ALERT_LABEL_TO_CATEGORY.get(top_raw_label, "Non classé")
    return {"category": category, "confidence": top_score}


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