# chatbot.py

import os
import json
import sqlite3
import pickle
import collections
from pathlib import Path

import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

# Download benodigde NLTK-data (éénmalig, sla caches op in ~/.cache/nltk_data)
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

# ==== Setup paden ====
BASE_DIR      = Path(__file__).parent.resolve()
INSTANCE_DIR  = BASE_DIR / 'instance'
DATABASE_PATH = INSTANCE_DIR / 'abonnementen.db'
MODEL_PATH    = INSTANCE_DIR / 'chatbot_model.pkl'
CONFIG_PATH   = INSTANCE_DIR / 'config.json'

# Zorg dat de instance-map bestaat
INSTANCE_DIR.mkdir(exist_ok=True)

# ==== FastAPI app + CORS ====
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== Database helper ====
def get_db_connection():
    """Return SQLite connection met row_factory."""
    conn = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ==== NLP setup ====
stopwoorden = set(stopwords.words('dutch'))
lemmatizer = WordNetLemmatizer()

def verwerk_vraag(vraag: str) -> str:
    tokens = word_tokenize(vraag.lower())
    kernwoorden = [
        lemmatizer.lemmatize(w)
        for w in tokens
        if w.isalnum() and w not in stopwoorden
    ]
    return " ".join(kernwoorden)

def extract_zoekterm(vraag: str) -> str:
    tokens = word_tokenize(vraag.lower())
    ignore = {"wat", "is", "de", "prijs", "van", "hoe", "duur", "kosten", "kost", "welke", "zijn", "er"}
    relevante = [lemmatizer.lemmatize(w) for w in tokens if w.isalnum() and w not in ignore]
    return " ".join(relevante) if relevante else verwerk_vraag(vraag)

def extract_advantage_zoekterm(vraag: str) -> str:
    tokens = word_tokenize(vraag.lower())
    ignore = {"wat", "is", "het", "voordeel", "plus", "van", "de", "een"}
    relevante = [lemmatizer.lemmatize(w) for w in tokens if w.isalnum() and w not in ignore]
    return " ".join(relevante) if relevante else verwerk_vraag(vraag)

handmatige_antwoorden = {
    "goedemiddag": "Goedemiddag, waarmee kan ik u helpen?",
    "goedeavond":   "Goedeavond, waarmee kan ik u helpen?",
    "wat is het populairste abonnement": "Het populairste abonnement is HelloFresh.",
}

# ==== Config laden ====
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config niet gevonden: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()

def match_intent(vraag: str, config: dict) -> dict:
    vraag_l = vraag.lower()
    for intent_name, intent_data in config.get("intents", {}).items():
        if intent_name == "default":
            continue
        for kw in intent_data.get("keywords", []):
            if kw in vraag_l:
                return intent_data
    return config["intents"].get("default", {})

# ==== Logging & training ====
context_buffer = collections.deque(maxlen=3)

def log_chat(vraag: str, antwoord: str):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO chatbot_logs (vraag, antwoord) VALUES (?, ?)",
                (vraag, antwoord)
            )
            conn.commit()
    except Exception as e:
        print(f"⚠️ Fout bij loggen: {e}")

def train_chatbot():
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT vraag, antwoord FROM chatbot_logs")
        data = cursor.fetchall()
    if not data:
        print("⚠️ Geen data om te trainen!")
        return
    vragen, antwoorden = zip(*data)
    pipeline = make_pipeline(TfidfVectorizer(), MultinomialNB())
    pipeline.fit(vragen, antwoorden)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)
    print("✅ Chatbot getraind en opgeslagen als pickle!")

# ==== Model laden ====
try:
    with open(MODEL_PATH, "rb") as f:
        loaded = pickle.load(f)
        model_pipeline = loaded if hasattr(loaded, "predict") else None
except FileNotFoundError:
    model_pipeline = None

# ==== API endpoint ====
@app.get("/chatbot/")
def chatbot_endpoint(vraag: str = Query(..., description="Vraag over abonnementen")):
    try:
        context_buffer.append(vraag)
        verwerkte = verwerk_vraag(vraag)
        intent = match_intent(vraag, config)

        # Kies juiste zoekterm-extractie
        tmpl = intent.get("template", "").lower()
        if "voordeel" in tmpl or "plus" in tmpl:
            zoek = extract_advantage_zoekterm(vraag)
        else:
            zoek = verwerkte

        zoekpatroon = f"%{zoek}%"
        cols = intent.get("columns", ["naam", "prijs"])
        case_exprs = [f"(CASE WHEN a.{c} LIKE ? THEN 1 ELSE 0 END)" for c in cols]
        score_expr = " + ".join(case_exprs)
        where_clause = " OR ".join([f"a.{c} LIKE ?" for c in cols])
        params = tuple([zoekpatroon] * (len(cols) * 2))

        extra_filter = ""
        if "voordeel" in tmpl or "plus" in tmpl:
            extra_filter = " AND a.voordelen IS NOT NULL AND TRIM(a.voordelen)!=''"

        with get_db_connection() as conn:
            query = f"""
                SELECT a.naam, a.prijs, a.beschrijving, a.contractduur, a.voordelen,
                       a.wat_is_het_abonnement, a.waarom_kiezen, a.hoe_werkt_het, a.past_dit_bij_jou,
                       sc.naam AS subcategorie, c.naam AS categorie,
                       ({score_expr}) AS score
                FROM abonnement a
                LEFT JOIN subcategorie sc ON a.subcategorie_id = sc.id
                LEFT JOIN categorie c ON sc.categorie_id = c.id
                WHERE {where_clause} {extra_filter}
                ORDER BY score DESC
            """
            cursor = conn.execute(query, params)
            results = cursor.fetchall()

        antwoord = None
        if results:
            if "voordeel" in tmpl or "plus" in tmpl:
                antwoord = " ".join(
                    intent["template"].format(**row) for row in results
                )
            else:
                opties = [f"{r['naam']} ({r['prijs']})" for r in results if r["score"] > 0]
                if opties:
                    antwoord = "Abonnementen: " + ", ".join(opties)

        # Fallback voor prijs/duur
        if not antwoord and any(kw in vraag.lower() for kw in ["prijs", "duur"]):
            with get_db_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT a.naam, a.prijs, sc.naam AS subcategorie, c.naam AS categorie
                    FROM abonnement a
                    LEFT JOIN subcategorie sc ON a.subcategorie_id=sc.id
                    LEFT JOIN categorie c ON sc.categorie_id=c.id
                    WHERE a.naam LIKE ? OR sc.naam LIKE ? OR c.naam LIKE ?
                    """,
                    (zoekpatroon, zoekpatroon, zoekpatroon)
                )
                rec = cur.fetchone()
            if rec:
                antwoord = (
                    f"De prijs van {rec['naam']} (categorie: {rec['categorie']}, "
                    f"subcategorie: {rec['subcategorie']}) is {rec['prijs']}."
                )

        # Fallback ML-model
        if not antwoord and model_pipeline:
            pred = model_pipeline.predict([verwerkte])[0]
            if pred and str(pred).strip().lower() != "undefined":
                antwoord = pred

        # Handmatige fallback
        if not antwoord:
            for key, man in handmatige_antwoorden.items():
                if key in vraag.lower():
                    antwoord = man
                    break

        # Laatste fallback: suggesties uit logs
        if not antwoord:
            with get_db_connection() as conn:
                cur = conn.execute(
                    "SELECT DISTINCT vraag FROM chatbot_logs WHERE vraag LIKE ?",
                    (zoekpatroon,)
                )
                sugg = [r["vraag"] for r in cur.fetchall()]
            if sugg:
                antwoord = f"Ik kon geen exact antwoord vinden, bedoelde je: {', '.join(sugg[:3])}?"
            else:
                antwoord = "Ik kon geen relevante informatie vinden. Kun je de vraag anders formuleren?"

        # Log en return
        log_chat(vraag, antwoord)
        return {"antwoord": antwoord}

    except Exception as e:
        print(f"⚠️ ERROR: {e}")
        return {"fout": str(e)}
