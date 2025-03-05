# chatbot.py
from fastapi import FastAPI, Query
import sqlite3
import os
import nltk
import json
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from fastapi.middleware.cors import CORSMiddleware
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import collections

# Download benodigde NLTK-data
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

# Definieer FastAPI app
app = FastAPI()

# CORS-instellingen toevoegen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Of specifieker, bijv. ["http://127.0.0.1:5000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Databaseverbinding
DATABASE_PATH = os.path.join(
    "C:\\Users\\timoo\\OneDrive\\Bureaublad\\Abbo-test\\abonnementen_website_test\\instance",
    "abonnementen.db"
)

def get_db_connection():
    """Geeft een SQLite-verbinding terug met row_factory ingesteld."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Stopwoorden en lemmatizer initialiseren
stopwoorden = set(stopwords.words('dutch'))
lemmatizer = WordNetLemmatizer()

def verwerk_vraag(vraag: str) -> str:
    """Tokenizeert de vraag, verwijdert stopwoorden en lemmatiseert de woorden."""
    woorden = word_tokenize(vraag.lower())
    kernwoorden = [lemmatizer.lemmatize(w) for w in woorden if w.isalnum() and w not in stopwoorden]
    return " ".join(kernwoorden)

def extract_zoekterm(vraag: str) -> str:
    """
    Extraheer de relevante zoekterm uit de vraag.
    Bijvoorbeeld: "wat is de prijs van nespresso" -> "nespresso"
    """
    tokens = word_tokenize(vraag.lower())
    ignore = {"wat", "is", "de", "prijs", "van", "hoe", "duur", "kosten", "kost", "welke", "zijn", "er"}
    relevante_tokens = [lemmatizer.lemmatize(w) for w in tokens if w.isalnum() and w not in ignore]
    if relevante_tokens:
        return " ".join(relevante_tokens)
    return verwerk_vraag(vraag)

def extract_advantage_zoekterm(vraag: str) -> str:
    """
    Extraheer de zoekterm voor voordeel-gerelateerde vragen.
    Woorden als "wat", "is", "het", "voordeel", "plus", "van", "de", "een" worden verwijderd,
    zodat bijvoorbeeld "wat is het voordeel van hello fresh" resulteert in "hello fresh".
    """
    tokens = word_tokenize(vraag.lower())
    ignore = {"wat", "is", "het", "voordeel", "plus", "van", "de", "een"}
    relevante_tokens = [lemmatizer.lemmatize(w) for w in tokens if w.isalnum() and w not in ignore]
    if relevante_tokens:
        return " ".join(relevante_tokens)
    return verwerk_vraag(vraag)

# Handmatige fallback-antwoorden
handmatige_antwoorden = {
    "goedemiddag": "Goedemiddag, waarmee kan ik u helpen?",
    "goedeavond": "Goedeavond, waarmee kan ik u helpen?",
    "wat is het populairste abonnement": "Het populairste abonnement is HelloFresh.",
}

# Laad de configuratie uit een extern JSON-bestand
def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()

def match_intent(vraag: str, config: dict) -> dict:
    vraag_lower = vraag.lower()
    for intent_name, intent_data in config.get("intents", {}).items():
        if intent_name == "default":
            continue
        for kw in intent_data.get("keywords", []):
            if kw in vraag_lower:
                print(f"Intent gematcht: {intent_name}")
                return intent_data
    print("Default intent gebruikt")
    return config.get("intents", {}).get("default", {})


# Contextbuffer voor gesprekshistorie (laatste 3 vragen)
context_buffer = collections.deque(maxlen=3)

def log_chat(vraag: str, antwoord: str):
    """Logt de vraag en het antwoord in de database (tabel chatbot_logs)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO chatbot_logs (vraag, antwoord) VALUES (?, ?)", (vraag, antwoord))
            conn.commit()
    except Exception as e:
        print(f"Fout bij het loggen: {e}")

def train_chatbot():
    """Traind het ML-model met een pipeline die TF-IDF en MultinomialNB combineert."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT vraag, antwoord FROM chatbot_logs")
        data = cursor.fetchall()
    if not data:
        print("⚠️ Geen data om te trainen!")
        return
    vragen, antwoorden = zip(*data)
    model_pipeline = make_pipeline(TfidfVectorizer(), MultinomialNB())
    model_pipeline.fit(vragen, antwoorden)
    with open("chatbot_model.pkl", "wb") as f:
        pickle.dump(model_pipeline, f)
    print("✅ Chatbot getraind met verbeterde AI!")

# Probeer het getrainde model te laden
try:
    with open("chatbot_model.pkl", "rb") as f:
        loaded = pickle.load(f)
        if hasattr(loaded, "predict"):
            model_pipeline = loaded
        else:
            print("Oude modelstructuur gedetecteerd, model_pipeline wordt op None gezet.")
            model_pipeline = None
except FileNotFoundError:
    model_pipeline = None

@app.get("/chatbot/")
def chatbot(vraag: str = Query(..., description="Vraag over abonnementen")):
    try:
        # Voeg de vraag toe aan de contextbuffer
        context_buffer.append(vraag)
        verwerkte_vraag = verwerk_vraag(vraag)
        print(f"🔍 Gebruiker zoekt: {verwerkte_vraag}")
        antwoord = None

        # Bepaal de intentie op basis van de vraag via de configuratie
        intent = match_intent(vraag, config)
        
        # Voor voordeel-gerelateerde intenties gebruiken we een aangepaste zoektermextractie
        if "voordeel" in intent.get("template", "").lower() or "plus" in intent.get("template", "").lower():
            zoekterm_str = extract_advantage_zoekterm(vraag)
        else:
            # Voor andere vragen gebruiken we de standaard verwerkte vraag
            zoekterm_str = verwerkte_vraag
        zoekterm = f"%{zoekterm_str}%"

        # Gebruik de kolommen uit de intentie om de query dynamisch op te bouwen
        columns = intent.get("columns", [])
        if not columns:
            columns = ["naam", "prijs"]
        
        # Bouw dynamisch de CASE-expressies voor scoreberekening
        
        case_exprs = []
        for col in columns:
            case_exprs.append(f"(CASE WHEN a.{col} LIKE ? THEN 1 ELSE 0 END)")
        score_expr = " + ".join(case_exprs)
        where_clause = " OR ".join([f"a.{col} LIKE ?" for col in columns])
        # Voor elke kolom wordt de zoekterm 2 keer gebruikt (voor CASE en WHERE)
        params = tuple([zoekterm] * (len(columns) * 2))
        
        # Extra filter als de intentie op voordelen gericht is:
        extra_filter = ""
        if "voordeel" in intent.get("template", "").lower() or "plus" in intent.get("template", "").lower():
            extra_filter = " AND a.voordelen IS NOT NULL AND TRIM(a.voordelen) != '' "

        with get_db_connection() as conn:
            cursor = conn.cursor()
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
            cursor.execute(query, params)
            results = cursor.fetchall()

            if results:
                template = intent.get("template", "{naam} ({prijs})")
                # Als de vraag over voordelen gaat, maak het antwoord op basis van het voordelen-veld
                if "voordeel" in template.lower() or "plus" in template.lower():
                    antwoord_list = []
                    for row in results:
                        data = { key: row[key] for key in row.keys() }
                        antwoord_list.append(template.format(**data))
                    antwoord = " ".join(antwoord_list)
                else:
                    antwoord = "Abonnementen: " + ", ".join([f"{row['naam']} ({row['prijs']})" for row in results if row["score"] > 0])
        
        # Fallback-optie: specifieke prijs-query als de vraag prijs/duur bevat
        if not antwoord and any(kw in vraag.lower() for kw in ["prijs", "duur"]):
            query_price = """
                SELECT a.naam, a.prijs, sc.naam AS subcategorie, c.naam AS categorie
                FROM abonnement a
                LEFT JOIN subcategorie sc ON a.subcategorie_id = sc.id
                LEFT JOIN categorie c ON sc.categorie_id = c.id
                WHERE a.naam LIKE ? OR sc.naam LIKE ? OR c.naam LIKE ?
            """
            cursor.execute(query_price, (zoekterm, zoekterm, zoekterm))
            record = cursor.fetchone()
            if record:
                antwoord = (f"De prijs van {record['naam']} (categorie: {record['categorie']}, "
                            f"subcategorie: {record['subcategorie']}) is {record['prijs']}.")
        
        # Fallback: Gebruik het ML-model indien beschikbaar
        if not antwoord and model_pipeline:
            voorspelling = model_pipeline.predict([verwerkte_vraag])[0]
            if voorspelling and str(voorspelling).strip().lower() != "undefined":
                antwoord = voorspelling
        
        # Fallback: Handmatige antwoorden
        if not antwoord:
            for key, manueel in handmatige_antwoorden.items():
                if key in vraag.lower():
                    antwoord = manueel
                    break
        
        # Fallback: Suggesties uit eerdere logs
        if not antwoord:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT vraag FROM chatbot_logs WHERE vraag LIKE ?", (zoekterm,))
                suggesties = [row['vraag'] for row in cursor.fetchall()]
                if suggesties:
                    antwoord = f"Ik kon geen exact antwoord vinden, bedoelde je: {', '.join(suggesties[:3])}?"
                else:
                    antwoord = "Ik kon geen relevante informatie vinden. Kun je de vraag anders formuleren?"
        
        log_chat(vraag, antwoord)
        return {"antwoord": antwoord}
    except Exception as e:
        print(f"⚠️ ERROR: {e}")
        return {"fout": str(e)}
