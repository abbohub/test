# app.py
import os
import uuid
import csv
import sqlite3
import hashlib
from io import StringIO
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from xml.sax.saxutils import escape
import json

from dotenv import load_dotenv
from PIL import Image
from slugify import slugify

from flask import (
    Flask,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired

from sqlalchemy import (
    func,
    case,
    and_,
    or_,
    exists,
    select,
)
from sqlalchemy.orm import joinedload
from sqlalchemy.schema import UniqueConstraint

# Chatbot (als je dit echt runtime gebruikt)
from chatbot import train_chatbot as train_chatbot_model
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score


# Maak de Flask-app aan
app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'jouw_geheime_sleutel'
app.url_map.strict_slashes = False   # zet dit meteen na je app = Flask(...)

# Activeer CSRF-bescherming
csrf = CSRFProtect(app)

# Laad .env-variabelen (optioneel)
load_dotenv()

# ---------------------------------------
# Configuratie
# ---------------------------------------
# Haal SECRET_KEY op uit de environment, met fallback
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "instance", "abonnementen.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path.replace("\\", "/")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload instellingen
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Initialiseer DB, Migrate en Flask-Login
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = "login"  # waar de user heen gaat als hij moet inloggen


# ---------------------------------------
# Database-modellen verwijderen  na afronding

from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ---------------------------------------

# Databaseverbinding (zorg dat dit overeenkomt met jouw configuratie)
# Bepaal de basisdirectory van dit script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Zet de database in <project_root>/instance/abonnementen.db
DATABASE_PATH = os.path.join(BASE_DIR, "instance", "abonnementen.db")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class Categorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False, unique=True)
    volgorde = db.Column(db.Integer, nullable=False, default=0)
    subcategorieën = db.relationship('Subcategorie', backref='categorie', lazy=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    beschrijving = db.Column(db.Text, nullable=True)  # 🔥 Nieuwe kolom voor pop-up info
    seo_title = db.Column(db.String(255), nullable=True)
meta_description = db.Column(db.String(255), nullable=True)
canonical_url = db.Column(db.String(255), nullable=True)
og_image = db.Column(db.String(255), nullable=True)

status = db.Column(db.String(20), nullable=False, default='draft')
created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
updated_at = db.Column(db.DateTime, nullable=True)
published_at = db.Column(db.DateTime, nullable=True)


class Subcategorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False)
    categorie_id = db.Column(db.Integer, db.ForeignKey('categorie.id'), nullable=False)
    abonnementen = db.relationship('Abonnement', backref='subcategorie', lazy=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    beschrijving = db.Column(db.Text, nullable=True)
    seo_title = db.Column(db.String(255), nullable=True)
meta_description = db.Column(db.String(255), nullable=True)
canonical_url = db.Column(db.String(255), nullable=True)
og_image = db.Column(db.String(255), nullable=True)

status = db.Column(db.String(20), nullable=False, default='draft')
created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
updated_at = db.Column(db.DateTime, nullable=True)
published_at = db.Column(db.DateTime, nullable=True)

    

class Bedrijf(db.Model):
    __tablename__ = 'bedrijf'
    id            = db.Column(db.Integer, primary_key=True)
    naam          = db.Column(db.String(150), nullable=False, unique=True)
    website_url   = db.Column(db.String(255), nullable=True)
    logo          = db.Column(db.String(200), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    telefoon      = db.Column(db.String(50),  nullable=True)
    kvk_nummer    = db.Column(db.String(50),  nullable=True)

    # relatie: 1 bedrijf -> n abonnementen
    abonnementen  = db.relationship('Abonnement', back_populates='bedrijf')


class Abonnement(db.Model):
    __tablename__ = "abonnement"

    id = db.Column(db.Integer, primary_key=True)
    bedrijf_id = db.Column(db.Integer, db.ForeignKey('bedrijf.id'), nullable=True)

    naam = db.Column(db.String(100), nullable=False)
    beschrijving = db.Column(db.String(140), nullable=True)
    filter_optie = db.Column(db.String(20), nullable=False)

    logo = db.Column(db.String(200), nullable=True)
    subcategorie_id = db.Column(db.Integer, db.ForeignKey('subcategorie.id'), nullable=False)

    url = db.Column(db.String(200), nullable=False)
    affiliate_url = db.Column(db.String(255), nullable=True)

    # legacy / blijft voorlopig bestaan
    prijs = db.Column(db.String(50), nullable=True)
    prijs_vanaf = db.Column(db.Float, nullable=True)
    prijs_tot = db.Column(db.Float, nullable=True)
    contractduur = db.Column(db.String(20), nullable=True)

    aanbiedingen = db.Column(db.String(200), nullable=True)
    annuleringsvoorwaarden = db.Column(db.Text, nullable=True)
    voordelen = db.Column(db.Text, nullable=True)

    beoordelingen = db.Column(db.Float, nullable=True)  # legacy
    volgorde = db.Column(db.Integer, nullable=False, default=0)

    # Levering/pauze (MVP)
    cutoff_time = db.Column(db.String(5), nullable=True)       # 'HH:MM'
    lead_time_days = db.Column(db.Integer, nullable=True)
    pause_possible = db.Column(db.Boolean, nullable=False, default=False)
    pause_max_weeks = db.Column(db.Integer, nullable=True)

    # Ratings (listing) - nieuw
    rating_avg = db.Column(db.Float, nullable=False, default=5.0)
    rating_count = db.Column(db.Integer, nullable=False, default=0)
    last_review_at = db.Column(db.DateTime, nullable=True)

    # Publicatie & onderhoud - nieuw
    status = db.Column(db.String(20), nullable=False, default='draft')  # draft/published/archived
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=db.func.now())
    published_at = db.Column(db.DateTime, nullable=True)
    last_checked_at = db.Column(db.DateTime, nullable=True)
    editor_notes = db.Column(db.Text, nullable=True)

    # SEO - nieuw
    seo_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.String(255), nullable=True)
    canonical_url = db.Column(db.String(255), nullable=True)
    og_image = db.Column(db.String(255), nullable=True)
    schema_type = db.Column(db.String(50), nullable=True)
    faq_json = db.Column(db.Text, nullable=True)

    # slug (bestaat al)
    slug = db.Column(db.String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint('slug', name='uq_abonnement_slug'),
    )

    # contentvelden (bestaan al)
    frequentie_bezorging = db.Column(db.String(50), nullable=True)
    wat_is_het_abonnement = db.Column(db.Text, nullable=True)
    waarom_kiezen = db.Column(db.Text, nullable=True)
    hoe_werkt_het = db.Column(db.Text, nullable=True)
    past_dit_bij_jou = db.Column(db.Text, nullable=True)

    youtube_url = db.Column(db.String(255), nullable=True)

    fotos = db.relationship('AbonnementFoto', back_populates='abonnement', cascade="all, delete-orphan")
    doelgroepen = db.relationship('Doelgroep', secondary='abonnement_doelgroep', back_populates='abonnementen')
    tags = db.relationship('Tag', secondary='abonnement_tag', back_populates='abonnementen')
    reviews = db.relationship("Review", back_populates="abonnement", lazy=True)
    bedrijf = db.relationship('Bedrijf', back_populates='abonnementen')

    # -------------------------------------------------
    # Optie A: helpers voor templates + listing rating sync
    # -------------------------------------------------
    def get_average_score(self) -> float:
        """
        Gemiddelde score op basis van reviews (als die er zijn),
        anders fallback naar rating_avg.
        """
        try:
            if self.reviews:
                scores = [r.score for r in self.reviews if r and r.score is not None]
                if scores:
                    return round(sum(scores) / len(scores), 1)
        except Exception:
            pass
        return round(float(self.rating_avg or 0.0), 1)

    def get_review_count(self) -> int:
        """Aantal reviews, fallback naar rating_count."""
        try:
            if self.reviews is not None:
                return len(self.reviews)
        except Exception:
            pass
        return int(self.rating_count or 0)

    def sync_listing_rating(self) -> None:
        """
        Zet rating_avg/rating_count/last_review_at op basis van Review tabel.
        Call deze na het toevoegen/verwijderen van reviews.
        """
        try:
            if self.reviews:
                scores = [r.score for r in self.reviews if r and r.score is not None]
                if scores:
                    self.rating_avg = float(sum(scores) / len(scores))
                    self.rating_count = int(len(scores))

                    # laatste review moment (als created_at bestaat)
                    dates = [r.created_at for r in self.reviews if getattr(r, "created_at", None)]
                    self.last_review_at = max(dates) if dates else None
                    return
        except Exception:
            pass

        # Geen reviews: laat avg op bestaande waarde (default 5.0), count op 0
        self.rating_avg = float(self.rating_avg or 5.0)
        self.rating_count = int(self.rating_count or 0)
        self.last_review_at = None

        from sqlalchemy import and_, or_, exists
from sqlalchemy.orm import joinedload

# ---------- kleine helpers ----------
def _as_int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def _as_float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def _as_bool(v):
    # accepteert 1/0, true/false, on/off, yes/no
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"1", "true", "on", "yes"}:
        return True
    if s in {"0", "false", "off", "no"}:
        return False
    return None

def _as_list(v):
    # request.args kan zowel "a,b,c" als meerdere keys geven
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if str(x).strip()]
    s = str(v).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]

def euro_to_cents_safe(eur_str):
    """
    '19.99' of '19,99' -> 1999
    """
    if not eur_str:
        return None
    s = str(eur_str).strip().replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return int(round(float(s) * 100))
    except ValueError:
        return None


# ---------- price subquery (cheapest plan per abonnement) ----------
def build_min_price_subquery(billing_period=None):
    q = db.session.query(
        Plan.abonnement_id.label("abonnement_id"),
        func.min(Plan.price_cents).label("min_price_cents"),
    )
    if billing_period:
        q = q.filter(Plan.billing_period == billing_period)

    return q.group_by(Plan.abonnement_id).subquery()


# ---------- DE query builder ----------
def build_abonnement_query(args, public=True):
    """
    args = request.args (of dict)
    public=True -> alleen published
    public=False -> admin/preview: alles (of filterbaar op status)
    """

    # 1) basis query + eager loading
    q = (
        Abonnement.query
        .options(
            joinedload(Abonnement.subcategorie).joinedload(Subcategorie.categorie),
            joinedload(Abonnement.bedrijf),
            joinedload(Abonnement.tags),
            joinedload(Abonnement.doelgroepen),
            joinedload(Abonnement.plannen),   # backref in Plan-model
        )
        .join(Subcategorie, Abonnement.subcategorie_id == Subcategorie.id)
        .join(Categorie, Subcategorie.categorie_id == Categorie.id)
        .outerjoin(Bedrijf, Abonnement.bedrijf_id == Bedrijf.id)
    )

    # 2) public/admin status
    if public:
        q = q.filter(Abonnement.status == "published")
    else:
        status = (args.get("status") or "").strip()
        if status in {"draft", "published", "archived"}:
            q = q.filter(Abonnement.status == status)

    # 3) categorie/subcategorie filters (id of slug)
    cat_id = _as_int(args.get("categorie_id"))
    subcat_id = _as_int(args.get("subcategorie_id"))

    cat_slug = (args.get("categorie_slug") or "").strip()
    subcat_slug = (args.get("subcategorie_slug") or "").strip()

    if cat_id:
        q = q.filter(Categorie.id == cat_id)
    elif cat_slug:
        q = q.filter(Categorie.slug == cat_slug)

    if subcat_id:
        q = q.filter(Subcategorie.id == subcat_id)
    elif subcat_slug:
        q = q.filter(Subcategorie.slug == subcat_slug)

    # 4) tekst search (optioneel basis)
    search = (args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            Abonnement.naam.ilike(like),
            Abonnement.beschrijving.ilike(like),
            Bedrijf.naam.ilike(like),
        ))

    # 5) tags/doelgroepen (ids)
    tag_ids = [_as_int(x) for x in _as_list(args.get("tag_ids"))]
    tag_ids = [x for x in tag_ids if x]

    dg_ids = [_as_int(x) for x in _as_list(args.get("doelgroep_ids"))]
    dg_ids = [x for x in dg_ids if x]

    if tag_ids:
        q = q.filter(Abonnement.tags.any(Tag.id.in_(tag_ids)))

    if dg_ids:
        q = q.filter(Abonnement.doelgroepen.any(Doelgroep.id.in_(dg_ids)))

    # 6) availability filters (countries, delivery days, pause)
    countries = [c.upper() for c in _as_list(args.get("countries")) if c]
    if countries:
        q = q.filter(
            exists().where(and_(
                AbonnementCountry.abonnement_id == Abonnement.id,
                AbonnementCountry.country_code.in_(countries)
            ))
        )

    delivery_days = [_as_int(x) for x in _as_list(args.get("delivery_days"))]
    delivery_days = [x for x in delivery_days if x and 1 <= x <= 7]
    if delivery_days:
        q = q.filter(
            exists().where(and_(
                AbonnementDeliveryDay.abonnement_id == Abonnement.id,
                AbonnementDeliveryDay.weekday.in_(delivery_days)
            ))
        )

    pause = _as_bool(args.get("pause_possible"))
    if pause is not None:
        q = q.filter(Abonnement.pause_possible == pause)

    # 7) price filtering via Plan (cents)
    billing_period = (args.get("billing_period") or "").strip() or None
    if billing_period and billing_period not in {"month", "year", "week", "portion", "one_time"}:
        billing_period = None

    price_min_cents = euro_to_cents_safe(args.get("price_min"))
    price_max_cents = euro_to_cents_safe(args.get("price_max"))

    price_sq = build_min_price_subquery(billing_period=billing_period)
    q = q.outerjoin(price_sq, price_sq.c.abonnement_id == Abonnement.id)

    if billing_period:
        q = q.filter(price_sq.c.min_price_cents.isnot(None))
    if price_min_cents is not None:
        q = q.filter(price_sq.c.min_price_cents >= price_min_cents)
    if price_max_cents is not None:
        q = q.filter(price_sq.c.min_price_cents <= price_max_cents)

    # 8) sorting
    sort = (args.get("sort") or "volgorde").strip()
    if sort == "price_asc":
        q = q.order_by(price_sq.c.min_price_cents.asc().nullslast(), Abonnement.volgorde.asc())
    elif sort == "price_desc":
        q = q.order_by(price_sq.c.min_price_cents.desc().nullslast(), Abonnement.volgorde.asc())
    elif sort == "rating_desc":
        q = q.order_by(Abonnement.rating_avg.desc(), Abonnement.rating_count.desc(), Abonnement.volgorde.asc())
    elif sort == "newest":
        q = q.order_by(Abonnement.created_at.desc().nullslast(), Abonnement.id.desc())
    else:
        q = q.order_by(Abonnement.volgorde.asc())

    # join/any kan duplicates geven -> distinct
    q = q.distinct(Abonnement.id)

    return q, price_sq



class AbonnementFoto(db.Model):
    __tablename__ = "abonnement_foto"  # naam mag, maar is handig expliciet
    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False, index=True)
    bestandsnaam = db.Column(db.String(255), nullable=False)

    abonnement = db.relationship('Abonnement', back_populates='fotos')

class Plan(db.Model):
    __tablename__ = "plan"

    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False, index=True)

    plan_name = db.Column(db.String(80), nullable=False, default="Standaard")

    price_cents = db.Column(db.Integer, nullable=False, index=True)
    currency = db.Column(db.String(3), nullable=False, default="EUR")
    billing_period = db.Column(db.String(20), nullable=False, index=True)  # month/year/week/portion/one_time
    is_from_price = db.Column(db.Boolean, nullable=False, default=False)
    vat_included = db.Column(db.Boolean, nullable=False, default=True)

    setup_fee_cents = db.Column(db.Integer, nullable=True)
    delivery_fee_cents = db.Column(db.Integer, nullable=True)

    min_term_months = db.Column(db.Integer, nullable=True)
    cancellation_notice_days = db.Column(db.Integer, nullable=True)

    trial_days = db.Column(db.Integer, nullable=True)
    promo_code = db.Column(db.String(80), nullable=True)
    promo_end_date = db.Column(db.DateTime, nullable=True)
    promo_terms = db.Column(db.Text, nullable=True)

    renewal_price_cents = db.Column(db.Integer, nullable=True)

    price_last_verified_at = db.Column(db.DateTime, nullable=True)
    price_source_url = db.Column(db.String(255), nullable=True)

    features = db.Column(db.Text, nullable=True)
    recommended_for = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=db.func.now())

    abonnement = db.relationship("Abonnement", backref=db.backref("plannen", lazy=True, cascade="all, delete-orphan"))


class AbonnementCountry(db.Model):
    __tablename__ = "abonnement_country"
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), primary_key=True)
    country_code = db.Column(db.String(2), primary_key=True)  # NL, BE
    regions_json = db.Column(db.Text, nullable=True)


class AbonnementDeliveryDay(db.Model):
    __tablename__ = "abonnement_delivery_day"
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), primary_key=True)
    weekday = db.Column(db.Integer, primary_key=True)  # 1=ma..7=zo


class AbonnementDeliveryFrequency(db.Model):
    __tablename__ = "abonnement_delivery_frequency"
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), primary_key=True)
    per_week = db.Column(db.Integer, primary_key=True)  # 1,2,3...


# === associations ===
blogpost_categorie = db.Table(
    'blogpost_categorie',
    db.Column('blogpost_id', db.Integer, db.ForeignKey('blog_post.id'), primary_key=True),
    db.Column('categorie_id', db.Integer, db.ForeignKey('categorie.id'), primary_key=True),
)

blogpost_subcategorie = db.Table(
    'blogpost_subcategorie',
    db.Column('blogpost_id', db.Integer, db.ForeignKey('blog_post.id'), primary_key=True),
    db.Column('subcategorie_id', db.Integer, db.ForeignKey('subcategorie.id'), primary_key=True),
)

blogpost_abonnement = db.Table(
    'blogpost_abonnement',
    db.Column('blogpost_id', db.Integer, db.ForeignKey('blog_post.id'), primary_key=True),
    db.Column('abonnement_id', db.Integer, db.ForeignKey('abonnement.id'), primary_key=True),
)

class BlogPost(db.Model):
    __tablename__ = "blog_post"
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    inhoud = db.Column(db.Text, nullable=False)
    afbeelding = db.Column(db.String(255))
    video_url = db.Column(db.String(255))
    datum = db.Column(db.DateTime, default=db.func.now())
    auteur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    auteur = db.relationship('User', backref='blogposts')
    auteur_naam = db.Column(db.String(120), nullable=True)  # <-- NIEUW (display name)
    

    # SEO fields
    seo_title = db.Column(db.String(255), nullable=True)
    meta_description = db.Column(db.String(255), nullable=True)
    canonical_url = db.Column(db.String(255), nullable=True)
    og_image = db.Column(db.String(255), nullable=True)

    status = db.Column(db.String(20), nullable=False, default='draft')
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)

    # << nieuwe many-to-many’s >>
    categorieen = db.relationship('Categorie', secondary=blogpost_categorie, lazy='dynamic')
    subcategorieen = db.relationship('Subcategorie', secondary=blogpost_subcategorie, lazy='dynamic')
    abonnementen = db.relationship('Abonnement', secondary=blogpost_abonnement, lazy='dynamic')

class Review(db.Model):
    __tablename__ = 'review'

    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False)
    naam = db.Column(db.String(255), nullable=False)  # Toevoegen van de naam kolom
    score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relatie terug naar abonnement
    abonnement = db.relationship("Abonnement", back_populates="reviews")

class Doelgroep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False, unique=True)
    abonnementen = db.relationship('Abonnement', secondary='abonnement_doelgroep', back_populates='doelgroepen')

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False, unique=True)
    abonnementen = db.relationship('Abonnement', secondary='abonnement_tag', back_populates='tags')

# Associatietabel voor Abonnement-Doelgroep (Many-to-Many)
abonnement_doelgroep = db.Table(
    'abonnement_doelgroep',
    db.Column('abonnement_id', db.Integer, db.ForeignKey('abonnement.id'), primary_key=True),
    db.Column('doelgroep_id', db.Integer, db.ForeignKey('doelgroep.id'), primary_key=True)
)

# Associatietabel voor Abonnement-Tag (Many-to-Many)
abonnement_tag = db.Table(
    'abonnement_tag',
    db.Column('abonnement_id', db.Integer, db.ForeignKey('abonnement.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Click(db.Model):
    __tablename__ = 'click'
    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=db.func.now(), index=True)

    # Waar stuurden we heen?
    used_affiliate = db.Column(db.Boolean, nullable=False, default=False)
    target_url = db.Column(db.String(512), nullable=False)

    # Context (privacy-vriendelijk)
    ip_hash = db.Column(db.String(64), nullable=True, index=True)       # SHA-256 (gehashte IP)
    user_agent = db.Column(db.Text, nullable=True)
    referer = db.Column(db.Text, nullable=True)
    landing_path = db.Column(db.String(255), nullable=True)             # vanwaar op jouw site kwam de klik
    ga_client_id = db.Column(db.String(64), nullable=True)              # optioneel, _ga cookie

    # Relatie (optioneel handig)
    abonnement = db.relationship('Abonnement', backref='clicks')


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=db.func.now())

class ContactBericht(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    bericht = db.Column(db.Text, nullable=False)
    datum = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<ContactBericht {self.naam}>'
    
# user tracker-------
def hash_ip(ip: str) -> str:
    """Privacyvriendelijk IP hashen met SECRET_KEY als zout."""
    if not ip:
        return ""
    secret = current_app.config.get('SECRET_KEY', 'fallback-secret-key')
    return hashlib.sha256(f"{ip}|{secret}".encode('utf-8')).hexdigest()

def get_client_ip() -> str:
    # Pak X-Forwarded-For als je achter een proxy/load balancer zit
    ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    return ip or request.remote_addr or ''

def get_ga_client_id() -> str:
    # pakt _ga cookie (Universal) of _ga_ cookie (GA4 client id is anders, maar dit is vaak genoeg)
    ga = request.cookies.get('_ga', '')
    return ga[:64] if ga else ''
    
def looks_like_bot(user_agent: str) -> bool:
    if not user_agent:
        return True
    ua = user_agent.lower()
    # Heel eenvoudige botfilter. Breid gerust uit.
    bot_signatures = ["bot", "crawler", "spider", "preview", "facebookexternalhit",
                      "skypeuripreview", "slackbot", "whatsapp", "telegrambot",
                      "linkedinbot", "discordbot", "embedly", "quora link preview"]
    return any(sig in ua for sig in bot_signatures)

def is_headless_previewer() -> bool:
    # Bots die alleen de pagina willen 'pre-renderen' (OG preview) wil je niet doorsturen.
    return looks_like_bot(request.headers.get('User-Agent', ''))
# ---------------------------------------
# Forms
# ---------------------------------------
class LoginForm(FlaskForm):
    username = StringField('Gebruikersnaam', validators=[DataRequired()])
    password = PasswordField('Wachtwoord', validators=[DataRequired()])


# ---------------------------------------
# Hulpfuncties
# ---------------------------------------
def allowed_file(filename):
    """Controleer of het bestand de juiste extensie heeft."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def update_average_score(abonnement):
    # roep dit aan zodra je een nieuwe review toevoegt of verwijdert
    reviews = abonnement.reviews
    if not reviews:
        abonnement.beoordelingen = 0
    else:
        total = sum(r.score for r in reviews)
        abonnement.beoordelingen = round(total / len(reviews), 1)
    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
def euro_to_cents(value: str):
    """Parse '19,99' / '€19.99' -> 1999. Return None if empty/invalid."""
    if not value:
        return None
    s = value.strip().replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return int(round(float(s) * 100))
    except ValueError:
        return None

def parse_date_yyyy_mm_dd(value: str):
    """Parse <input type=date> -> datetime (UTC naive)."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None

# ---------------------------------------
# Routes: AUTH
# ---------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            # BELANGRIJK: login_user(...) zodat Flask-Login weet dat je ingelogd bent
            login_user(user)

            # Afhankelijk van de rol redirecten we
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash("Onjuiste gebruikersnaam of wachtwoord!", "danger")
            return redirect(url_for('login'))

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ---------------------------------------
# Routes: Dashboard / index
# ---------------------------------------
@app.route("/")
def index():
    # 1) Flat dict voor single-value params
    args = request.args.to_dict(flat=True)

    # 1b) Multi-select keys als list doorgeven (nu vooral countries)
    for key in ("countries",):  # later kun je uitbreiden: "tag_ids", "doelgroep_ids", etc.
        vals = request.args.getlist(key)
        if vals:
            args[key] = vals

    # 2) Legacy -> builder mapping
    if not (args.get("q") or "").strip() and (args.get("zoekterm") or "").strip():
        args["q"] = args["zoekterm"].strip()

    if not (args.get("categorie_id") or "").strip() and (args.get("categorie") or "").strip():
        args["categorie_id"] = args["categorie"].strip()

    if not (args.get("subcategorie_id") or "").strip() and (args.get("subcategorie") or "").strip():
        args["subcategorie_id"] = args["subcategorie"].strip()

    # 3) UI-waarden
    zoekterm = (args.get("q") or "").strip()
    geselecteerde_categorie = (args.get("categorie_id") or "").strip()
    geselecteerde_subcategorie = (args.get("subcategorie_id") or "").strip()

    # 4) Query via builder
    q, price_sq = build_abonnement_query(args, public=True)
    abonnementen = q.all()

    # 5) Dropdown data
    categorieen = Categorie.query.order_by(Categorie.volgorde.asc()).all()
    subcategorieen = Subcategorie.query.all()

    # 6) Abonnementen per categorie
    abonnementen_per_categorie = {cat.id: [] for cat in categorieen}
    for ab in abonnementen:
        if ab.subcategorie and ab.subcategorie.categorie:
            abonnementen_per_categorie[ab.subcategorie.categorie.id].append(ab)

    return render_template(
        "index.html",
        abonnementen=abonnementen,
        abonnementen_per_categorie=abonnementen_per_categorie,
        unieke_categorieën=categorieen,
        unieke_subcategorieën=subcategorieen,
        geselecteerde_categorie=geselecteerde_categorie,
        geselecteerde_subcategorie=geselecteerde_subcategorie,
        zoekterm=zoekterm
    )

@app.route('/categorie/<categorie_slug>/')
@app.route('/categorie/<categorie_slug>/<subcategorie_slug>/')
def abonnement_overzicht(categorie_slug, subcategorie_slug=None):
    # 1) Context-objecten (voor SEO + validatie)
    categorie = Categorie.query.filter_by(slug=categorie_slug).first_or_404()
    subcategorie = None
    if subcategorie_slug:
        subcategorie = (
            Subcategorie.query
            .filter_by(slug=subcategorie_slug, categorie_id=categorie.id)
            .first_or_404()
        )

    # 2) Args bouwen (slug route + querystring filters combineren)
    args = request.args.to_dict(flat=True)

    # mapping: jouw header gebruikt soms "zoekterm", builder gebruikt "q"
    if (args.get("q") or "").strip() == "" and (args.get("zoekterm") or "").strip() != "":
        args["q"] = (args.get("zoekterm") or "").strip()

    # multi-select keys goed doorgeven
    for key in ("countries", "delivery_days", "delivery_frequency", "tag_ids", "doelgroep_ids"):
        vals = request.args.getlist(key)
        if vals:
            args[key] = vals

    # slug-context toevoegen (builder kan zowel id als slug)
    args["categorie_slug"] = categorie_slug
    if subcategorie_slug:
        args["subcategorie_slug"] = subcategorie_slug
    else:
        args.pop("subcategorie_slug", None)

    # 3) Query via builder
    # Publieke categoriepagina: meestal alleen published
    q, price_sq = build_abonnement_query(args, public=True)

    # Builder sorteert al op basis van args['sort'] (default = volgorde)
    abonnementen = q.all()

    # 4) Dropdown data (voor sidebar)
    categorieen = Categorie.query.order_by(Categorie.volgorde.asc()).all()
    subcategorieen = Subcategorie.query.all()

    # 5) Abonnementen per categorie (template verwacht dict per cat.id)
    abonnementen_per_categorie = {cat.id: [] for cat in categorieen}
    for ab in abonnementen:
        if ab.subcategorie and ab.subcategorie.categorie:
            cid = ab.subcategorie.categorie.id
            if cid in abonnementen_per_categorie:
                abonnementen_per_categorie[cid].append(ab)

    # 6) SEO titel/description
    if subcategorie:
        page_title = f"{subcategorie.naam} abonnementen vergelijken | {categorie.naam} | AbboHub"
        page_description = f"Bekijk en vergelijk eenvoudig {subcategorie.naam}-abonnementen binnen de categorie {categorie.naam} op AbboHub."
    else:
        page_title = f"Abonnementen in {categorie.naam} vergelijken | AbboHub"
        page_description = f"Ontdek alle abonnementen binnen de categorie {categorie.naam} en vergelijk eenvoudig prijzen en voordelen."

    return render_template(
        "index.html",
        abonnementen=abonnementen,
        abonnementen_per_categorie=abonnementen_per_categorie,
        unieke_categorieën=categorieen,
        unieke_subcategorieën=subcategorieen,

        # dit gebruikt je template om "actieve_categorie/subcategorie" te bepalen
        geselecteerde_categorie=str(categorie.id),
        geselecteerde_subcategorie=str(subcategorie.id) if subcategorie else "",

        # alleen voor compat met template (zoekterm wordt intern al gemapt -> q)
        zoekterm=args.get("zoekterm", ""),

        page_title=page_title,
        page_description=page_description
    )


@app.template_filter('slugify')
def slugify_filter(text):
    return slugify(text)

@app.route('/privacy-cookieverklaring.html')
def privacy_cookieverklaring():
    return render_template('privacy-cookieverklaring.html')

@app.route('/over-abbohub.html')
def over_abbohub():
    return render_template('over-abbohub.html')

@app.route('/review/<path:slug>', methods=['GET', 'POST'])
def abonnement_reviews(slug):
    abonnement = Abonnement.query.filter_by(slug=slug).first_or_404()
    is_admin = current_user.is_authenticated and getattr(current_user, "is_admin", False)

    # Draft/archived alleen admin
    if abonnement.status in ("draft", "archived") and not is_admin:
        abort(404)

    if request.method == 'POST':
        # Admin: review verwijderen
        if is_admin and 'delete_review_id' in request.form:
            review_id = request.form.get('delete_review_id', '').strip()

            try:
                review_id_int = int(review_id)
            except ValueError:
                flash("Ongeldige review id.", "danger")
                return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

            review = Review.query.get(review_id_int)
            if review and review.abonnement_id == abonnement.id:
                db.session.delete(review)
                db.session.commit()
                flash("Review succesvol verwijderd.", "success")
            else:
                flash("Review niet gevonden (of hoort niet bij dit abonnement).", "danger")

            return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

        # Gebruiker: nieuwe review toevoegen
        score_str = request.form.get('score', '').strip()
        comment = request.form.get('comment', '').strip()
        naam = request.form.get('naam', '').strip()

        if not score_str:
            flash("Geef een score op!", "danger")
            return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

        try:
            score = float(score_str)
        except ValueError:
            flash("Score moet een numerieke waarde zijn!", "danger")
            return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

        if not (1 <= score <= 5):
            flash("Score moet tussen 1 en 5 liggen!", "danger")
            return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

        new_review = Review(
            abonnement_id=abonnement.id,
            naam=naam,
            score=score,
            comment=comment
        )
        db.session.add(new_review)
        db.session.commit()
        flash("Bedankt voor je review!", "success")
        return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

    # Gemiddelde score
    gemiddelde_score = (
        db.session.query(func.avg(Review.score))
        .filter(Review.abonnement_id == abonnement.id)
        .scalar()
    )
    gemiddelde_score = round(float(gemiddelde_score), 1) if gemiddelde_score is not None else None

    # SEO defaults (template gebruikt alsnog abonnement.seo_title/meta_description als die gevuld zijn)
    page_title = f"{abonnement.naam} abonnement review & ervaringen | AbboHub"
    page_description = f"Lees gebruikerservaringen en ontdek wat {abonnement.naam} jou te bieden heeft. Vergelijk nu prijzen, voordelen en meer."

    # Sidebar
    if abonnement.subcategorie_id:
        andere_abonnementen = (
            Abonnement.query
            .filter(Abonnement.subcategorie_id == abonnement.subcategorie_id, Abonnement.id != abonnement.id)
            .order_by(Abonnement.volgorde.asc())
            .all()
        )
    elif getattr(abonnement, "categorie_id", None):
        andere_abonnementen = (
            Abonnement.query
            .filter(Abonnement.categorie_id == abonnement.categorie_id, Abonnement.id != abonnement.id)
            .order_by(Abonnement.volgorde.asc())
            .all()
        )
    else:
        andere_abonnementen = []

    # FAQ JSON parsen (veilig)
    faq_data = None
    if abonnement.faq_json:
        try:
            faq_data = json.loads(abonnement.faq_json)
        except json.JSONDecodeError:
            faq_data = None

    return render_template(
        "abonnement_reviews.html",
        abonnement=abonnement,
        is_admin=is_admin,
        gemiddelde_score=gemiddelde_score,
        andere_abonnementen=andere_abonnementen,
        page_title=page_title,
        page_description=page_description,
        faq_data=faq_data,
        current_year=datetime.now().year
    )

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    """Voorbeeld van een user-dashboard, na inloggen."""
    # In een echte app zou je hier user-specifieke data tonen
    return render_template('user_dashboard.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Je hebt geen toegang tot deze pagina.", "danger")
        return redirect(url_for('index'))

    # --- Stats (DB-gestuurd) ---
    total = db.session.query(func.count(Abonnement.id)).scalar() or 0
    published = db.session.query(func.count(Abonnement.id)).filter(Abonnement.status == "published").scalar() or 0
    draft = db.session.query(func.count(Abonnement.id)).filter(Abonnement.status == "draft").scalar() or 0
    archived = db.session.query(func.count(Abonnement.id)).filter(Abonnement.status == "archived").scalar() or 0

    zonder_bedrijf = db.session.query(func.count(Abonnement.id)).filter(Abonnement.bedrijf_id.is_(None)).scalar() or 0

    seo_mist = db.session.query(func.count(Abonnement.id)).filter(
        (Abonnement.seo_title.is_(None)) | (Abonnement.seo_title == "") |
        (Abonnement.meta_description.is_(None)) | (Abonnement.meta_description == "")
    ).scalar() or 0

    nooit_gecheckt = db.session.query(func.count(Abonnement.id)).filter(
        Abonnement.last_checked_at.is_(None)
    ).scalar() or 0

    # --- Categorieën ---
    categorieen = Categorie.query.order_by(Categorie.volgorde.asc()).all()

    # --- Abonnementen (met eager loading) ---
    abonnementen = (
        Abonnement.query
        .options(joinedload(Abonnement.subcategorie).joinedload(Subcategorie.categorie))
        .order_by(Abonnement.volgorde.asc(), Abonnement.naam.asc())
        .all()
    )

    # --- Groeperen per categorie (sneller dan in template filteren) ---
    abonnementen_per_categorie = {c.id: [] for c in categorieen}
    for a in abonnementen:
        if a.subcategorie and a.subcategorie.categorie:
            abonnementen_per_categorie[a.subcategorie.categorie.id].append(a)

    stats = {
        "total": total,
        "published": published,
        "draft": draft,
        "archived": archived,
        "zonder_bedrijf": zonder_bedrijf,
        "seo_mist": seo_mist,
        "nooit_gecheckt": nooit_gecheckt,
    }

    return render_template(
        'admin_dashboard.html',
        categorieen=categorieen,
        abonnementen_per_categorie=abonnementen_per_categorie,
        stats=stats
    )
@app.route('/update_abonnementen_volgorde', methods=['POST'])
@login_required
def update_abonnementen_volgorde():
    if not current_user.is_admin:
        return jsonify({'error': 'Geen toegang'}), 403

    data = request.get_json(silent=True) or {}
    order = data.get('order', [])
    categorie_id = data.get('categorieId')

    if not isinstance(order, list) or not order:
        return jsonify({'error': 'Ongeldige data: order ontbreekt'}), 400

    if not categorie_id or not str(categorie_id).isdigit():
        return jsonify({'error': 'Ongeldige data: categorieId ontbreekt'}), 400

    categorie_id = int(categorie_id)

    # Offset per categorie: voorkomt dat categorieën elkaar “overrulen”
    base = categorie_id * 10000

    # Update alleen ids die echt numeriek zijn
    ids = []
    for x in order:
        if str(x).isdigit():
            ids.append(int(x))

    if not ids:
        return jsonify({'error': 'Geen geldige abonnement IDs'}), 400

    # Bulk ophalen (sneller)
    abonnementen = Abonnement.query.filter(Abonnement.id.in_(ids)).all()
    abbo_map = {a.id: a for a in abonnementen}

    for index, abonnement_id in enumerate(ids):
        a = abbo_map.get(abonnement_id)
        if a:
            a.volgorde = base + index + 1

    db.session.commit()
    return jsonify({'success': True})
    
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_subscription():
    """Pagina voor abonnementen toevoegen (met bedrijf, tags/doelgroepen, plan-prijzen, availability, SEO)."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 1) Basisvelden (bestaand)
        naam = request.form.get('naam', '').strip()
        beschrijving = request.form.get('beschrijving', '').strip()
        filter_optie = request.form.get('filter_optie', '').strip()
        

        prijs = request.form.get('prijs', '').strip()  # legacy tekst (mag blijven)
        contractduur = request.form.get('contractduur', '').strip()
        aanbiedingen = request.form.get('aanbiedingen', '').strip()
        annuleringsvoorwaarden = request.form.get('annuleringsvoorwaarden', '').strip()
        voordelen = request.form.get('voordelen', '').strip()

        url = request.form.get('url', '').strip()
        affiliate_url = (request.form.get('affiliate_url', '').strip() or None)
        subcategorie_id = request.form.get('subcategorie_id')

        # 2) Extra contentvelden (bestaand)
        bedrijf_naam = request.form.get('bedrijf_naam', '').strip()
        contact_email = (request.form.get('contact_email') or '').strip() or None
        telefoon = (request.form.get('telefoon') or '').strip() or None
        kvk_nummer = (request.form.get('kvk_nummer') or '').strip() or None
        frequentie_bezorging = request.form.get('frequentie_bezorging', '').strip()
        prijs_vanaf = request.form.get('prijs_vanaf', '').strip()  # legacy float (mag blijven)
        prijs_tot = request.form.get('prijs_tot', '').strip()
        

        wat_is_het_abonnement = request.form.get('wat_is_het_abonnement', '').strip()
        waarom_kiezen = request.form.get('waarom_kiezen', '').strip()
        hoe_werkt_het = request.form.get('hoe_werkt_het', '').strip()
        past_dit_bij_jou = request.form.get('past_dit_bij_jou', '').strip()
        youtube_url = request.form.get('youtube_url', '').strip()

        geselecteerde_doelgroepen = request.form.getlist('doelgroepen')
        geselecteerde_tags = request.form.getlist('tags')

        # 3) Nieuwe velden: status/SEO
        status = (request.form.get('status') or 'draft').strip() or 'draft'
        seo_title = (request.form.get('seo_title') or '').strip() or None
        meta_description = (request.form.get('meta_description') or '').strip() or None
        canonical_url = (request.form.get('canonical_url') or '').strip() or None
        og_image = (request.form.get('og_image') or '').strip() or None
        schema_type = (request.form.get('schema_type') or '').strip() or None
        faq_json = (request.form.get('faq_json') or '').strip() or None

        # 4) Nieuwe velden: Plan / prijs & voorwaarden (filterbaar)
        plan_name = (request.form.get('plan_name') or 'Standaard').strip() or 'Standaard'
        plan_price_eur = request.form.get('plan_price', '').strip()
        billing_period = (request.form.get('billing_period') or 'month').strip() or 'month'

        is_from_price = request.form.get('is_from_price') == '1'
        vat_included = request.form.get('vat_included') == '1'

        setup_fee_cents = euro_to_cents(request.form.get('setup_fee', '').strip())
        delivery_fee_cents = euro_to_cents(request.form.get('delivery_fee', '').strip())

        min_term_months = request.form.get('min_term_months', '').strip()
        cancellation_notice_days = request.form.get('cancellation_notice_days', '').strip()
        trial_days = request.form.get('trial_days', '').strip()

        promo_code = (request.form.get('promo_code') or '').strip() or None
        promo_end_date = parse_date_yyyy_mm_dd(request.form.get('promo_end_date', '').strip())
        promo_terms = (request.form.get('promo_terms') or '').strip() or None
        renewal_price_cents = euro_to_cents(request.form.get('renewal_price', '').strip())

        price_source_url = (request.form.get('price_source_url') or '').strip() or None

        # 5) Availability (basis)
        countries = request.form.getlist('countries')  # ['NL','BE']
        delivery_days = request.form.getlist('delivery_days')  # ['1','2',...]
        delivery_frequency = request.form.getlist('delivery_frequency')  # ['1','2',...]
        cutoff_time = (request.form.get('cutoff_time') or '').strip() or None
        lead_time_days = request.form.get('lead_time_days', '').strip()
        pause_possible = request.form.get('pause_possible') == '1'
        pause_max_weeks = request.form.get('pause_max_weeks', '').strip()
        

        # 6) Validatie (basis + plan prijs)
        if not (naam and filter_optie and subcategorie_id and url and bedrijf_naam):
            flash("Vul alle verplichte velden in!", "danger")
            return redirect(url_for('add_subscription'))
        if not url.startswith(('http://', 'https://')):
            flash("De URL moet beginnen met http:// of https://.", "danger")
            return redirect(url_for('add_subscription'))

        price_cents = euro_to_cents(plan_price_eur)
        if price_cents is None or price_cents < 0:
            flash("Vul een geldige planprijs in (bijv. 19,99).", "danger")
            return redirect(url_for('add_subscription'))

        allowed_periods = {"month", "year", "week", "portion", "one_time"}
        if billing_period not in allowed_periods:
            billing_period = "month"

        allowed_status = {"draft", "published", "archived"}
        if status not in allowed_status:
            status = "draft"

        # 7) Slug genereren
        subcat = Subcategorie.query.get(int(subcategorie_id))
        cat = Categorie.query.get(subcat.categorie_id) if subcat else None
        categorie_slug = slugify(cat.naam) if cat else "categorie"
        subcategorie_slug = slugify(subcat.naam) if subcat else "subcategorie"
        naam_slug = slugify(naam)
        full_slug = f"{categorie_slug}/{subcategorie_slug}/{naam_slug}"

        if Abonnement.query.filter_by(slug=full_slug).first():
            flash("Er bestaat al een abonnement met deze naam in dezelfde categorie/subcategorie.", "danger")
            return redirect(url_for('add_subscription'))
        

        # 8) Logo upload & verwerking
        logo_filename = None
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and allowed_file(logo_file.filename):
                filename = secure_filename(logo_file.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                logo_path = os.path.join(upload_folder, filename)

                img = Image.open(logo_file).convert('RGB')
                resample_filter = getattr(Image, "Resampling", Image).LANCZOS
                img.thumbnail((200, 200), resample_filter)
                img.save(logo_path, format='JPEG', optimize=True, quality=85)

                logo_filename = filename

        # 9) Bedrijf ophalen/aanmaken (+ optioneel contactvelden uit form)
        bedrijf = Bedrijf.query.filter_by(naam=bedrijf_naam).first()
        if not bedrijf:
            bedrijf = Bedrijf(naam=bedrijf_naam)
            bedrijf.contact_email = contact_email
            bedrijf.telefoon = telefoon
            bedrijf.kvk_nummer = kvk_nummer
            db.session.add(bedrijf)
            db.session.flush()

            
        # 10) Maak abonnement (rating default 5★)
        new_abonnement = Abonnement(
            naam=naam,
            slug=full_slug,
            beschrijving=beschrijving,
            filter_optie=filter_optie,

            prijs=prijs,
            contractduur=contractduur,
            aanbiedingen=aanbiedingen,
            annuleringsvoorwaarden=annuleringsvoorwaarden,
            voordelen=voordelen,

            url=url,
            affiliate_url=affiliate_url,
            subcategorie_id=int(subcategorie_id),
            logo=logo_filename,

            frequentie_bezorging=frequentie_bezorging,
            prijs_vanaf=float(prijs_vanaf) if prijs_vanaf else None,
            prijs_tot=float(prijs_tot) if prijs_tot else None,

            wat_is_het_abonnement=wat_is_het_abonnement,
            waarom_kiezen=waarom_kiezen,
            hoe_werkt_het=hoe_werkt_het,
            past_dit_bij_jou=past_dit_bij_jou,
            youtube_url=youtube_url or None,

            bedrijf_id=bedrijf.id,

            # nieuw: rating listing
            rating_avg=5.0,
            rating_count=0,
            last_review_at=None,

            # nieuw: status + seo
            status=status,
            published_at=(datetime.utcnow() if status == "published" else None),
            seo_title=seo_title,
            meta_description=meta_description,
            canonical_url=canonical_url,
            og_image=og_image,
            schema_type=schema_type,
            faq_json=faq_json,

            # nieuw: levering/pauze
            cutoff_time=cutoff_time,
            lead_time_days=int(lead_time_days) if lead_time_days.isdigit() else None,
            pause_possible=pause_possible,
            pause_max_weeks=int(pause_max_weeks) if pause_max_weeks.isdigit() else None,
        )

        db.session.add(new_abonnement)
        db.session.flush()  # abonnement.id beschikbaar

        # 11) Maak het plan record
        plan = Plan(
            abonnement_id=new_abonnement.id,
            plan_name=plan_name,
            price_cents=price_cents,
            currency="EUR",
            billing_period=billing_period,
            is_from_price=is_from_price,
            vat_included=vat_included,

            setup_fee_cents=setup_fee_cents,
            delivery_fee_cents=delivery_fee_cents,

            min_term_months=int(min_term_months) if min_term_months.isdigit() else None,
            cancellation_notice_days=int(cancellation_notice_days) if cancellation_notice_days.isdigit() else None,
            trial_days=int(trial_days) if trial_days.isdigit() and int(trial_days) > 0 else None,

            promo_code=promo_code,
            promo_end_date=promo_end_date,
            promo_terms=promo_terms,

            renewal_price_cents=renewal_price_cents,

            price_last_verified_at=datetime.utcnow(),
            price_source_url=price_source_url
        )
        db.session.add(plan)

        # 12) Availability opslaan
        for cc in countries:
            cc = cc.strip().upper()
            if cc in {"NL", "BE"}:
                db.session.add(AbonnementCountry(abonnement_id=new_abonnement.id, country_code=cc))

        for wd in delivery_days:
            if wd.isdigit():
                wdi = int(wd)
                if 1 <= wdi <= 7:
                    db.session.add(AbonnementDeliveryDay(abonnement_id=new_abonnement.id, weekday=wdi))

        for fw in delivery_frequency:
            if fw.isdigit():
                fwi = int(fw)
                if 1 <= fwi <= 7:
                    db.session.add(AbonnementDeliveryFrequency(abonnement_id=new_abonnement.id, per_week=fwi))

        # 13) Foto’s verwerken (max 10)
        foto_bestanden = request.files.getlist('product_fotos')
        for foto in foto_bestanden[:10]:
            if foto and allowed_file(foto.filename):
                foto_filename = secure_filename(foto.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                foto_path = os.path.join(upload_folder, foto_filename)
                foto.save(foto_path)

                db.session.add(AbonnementFoto(
                    abonnement_id=new_abonnement.id,
                    bestandsnaam=foto_filename
                ))

        # 14) Relaties Doelgroepen & Tags
        for dg_id in geselecteerde_doelgroepen:
            if str(dg_id).isdigit():
                dg = Doelgroep.query.get(int(dg_id))
                if dg:
                    new_abonnement.doelgroepen.append(dg)

        for tag_id in geselecteerde_tags:
            if str(tag_id).isdigit():
                tg = Tag.query.get(int(tag_id))
                if tg:
                    new_abonnement.tags.append(tg)

        # 15) Opslaan
        db.session.commit()
        flash("Abonnement succesvol toegevoegd!", "success")
        return redirect(url_for('admin_dashboard'))

    # GET: formulier
    bedrijven = Bedrijf.query.order_by(Bedrijf.naam).all()
    categorieen = Categorie.query.all()
    subcategorieen = Subcategorie.query.all()
    doelgroepen = Doelgroep.query.all()
    tags = Tag.query.all()
    return render_template(
        'add_subscription.html',
        bedrijven=bedrijven,
        categorieen=categorieen,
        subcategorieen=subcategorieen,
        doelgroepen=doelgroepen,
        tags=tags
    )

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_subscription(id):
    """Admin: abonnement bewerken incl. SEO/status, availability en plan-prijzen."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    abonnement = Abonnement.query.get_or_404(id)

    bedrijven = Bedrijf.query.order_by(Bedrijf.naam).all()
    categorieen = Categorie.query.order_by(Categorie.volgorde.asc()).all()

    huidige_cat_id = abonnement.subcategorie.categorie_id if abonnement.subcategorie else None
    subcategorieen = (
        Subcategorie.query
        .filter_by(categorie_id=huidige_cat_id)
        .order_by(Subcategorie.naam.asc())
        .all()
    ) if huidige_cat_id else []

    doelgroepen = Doelgroep.query.all()
    tags = Tag.query.all()

    # Huidig bedrijf object (voor contactvelden in template)
    bedrijf = Bedrijf.query.get(abonnement.bedrijf_id) if abonnement.bedrijf_id else None

    # Pak “eerste plan” als default (MVP). Later kun je multi-plans UI doen.
    plan = Plan.query.filter_by(abonnement_id=abonnement.id).order_by(Plan.id.asc()).first()

    # --- Availability selections (voor template) ---
    selected_countries = [
        x.country_code
        for x in AbonnementCountry.query.filter_by(abonnement_id=abonnement.id).all()
    ]
    selected_days = [
        x.weekday
        for x in AbonnementDeliveryDay.query.filter_by(abonnement_id=abonnement.id).all()
    ]
    selected_freq = [
        x.per_week
        for x in AbonnementDeliveryFrequency.query.filter_by(abonnement_id=abonnement.id).all()
    ]

    if request.method == 'POST':
        # -----------------------
        # 1) Basisvelden
        # -----------------------
        abonnement.naam = (request.form.get('naam') or '').strip()
        abonnement.beschrijving = (request.form.get('beschrijving') or '').strip() or None
        abonnement.filter_optie = (request.form.get('filter_optie') or '').strip()

        abonnement.prijs = (request.form.get('prijs') or '').strip() or None
        abonnement.contractduur = (request.form.get('contractduur') or '').strip() or None
        abonnement.aanbiedingen = (request.form.get('aanbiedingen') or '').strip() or None
        abonnement.annuleringsvoorwaarden = (request.form.get('annuleringsvoorwaarden') or '').strip() or None
        abonnement.voordelen = (request.form.get('voordelen') or '').strip() or None

        abonnement.url = (request.form.get('url') or '').strip()
        abonnement.affiliate_url = (request.form.get('affiliate_url') or '').strip() or None

        # Validatie minimale velden
        if not abonnement.naam or not abonnement.filter_optie or not abonnement.url:
            flash("Vul alle verplichte velden in (naam, filter optie, url).", "danger")
            return redirect(url_for('edit_subscription', id=abonnement.id))
        if not abonnement.url.startswith(("http://", "https://")):
            flash("De URL moet beginnen met http:// of https://.", "danger")
            return redirect(url_for('edit_subscription', id=abonnement.id))

        # -----------------------
        # 2) Bedrijf (optioneel + nieuw aanmaken)
        # Verwacht vanuit template:
        # - select name="bedrijf_id" met optie value="__new__"
        # - input name="bedrijf_naam" (optioneel)
        # - input name="bedrijf_website_url" (optioneel)
        # -----------------------
        bedrijf_id = (request.form.get('bedrijf_id') or '').strip()
        new_bedrijf_naam = (request.form.get('bedrijf_naam') or '').strip()
        new_bedrijf_website = (request.form.get('bedrijf_website_url') or '').strip()

        bedrijf = None

        if bedrijf_id == "__new__":
            # Nieuw bedrijf toevoegen (alleen als naam ingevuld is)
            if new_bedrijf_naam:
                # Probeer bestaand te vinden op naam (case-insensitive)
                bedrijf = Bedrijf.query.filter(Bedrijf.naam.ilike(new_bedrijf_naam)).first()

                if not bedrijf:
                    bedrijf = Bedrijf(
                        naam=new_bedrijf_naam,
                        website_url=new_bedrijf_website or None
                    )
                    db.session.add(bedrijf)
                    db.session.flush()  # zodat bedrijf.id beschikbaar is

                abonnement.bedrijf_id = bedrijf.id
            else:
                # Geen naam ingevuld -> geen bedrijf koppelen
                abonnement.bedrijf_id = None

        elif bedrijf_id.isdigit():
            abonnement.bedrijf_id = int(bedrijf_id)
            bedrijf = Bedrijf.query.get(abonnement.bedrijf_id)

        else:
            abonnement.bedrijf_id = None
            bedrijf = None

        # Optioneel: bedrijf contactvelden opslaan
        # LET OP: dit wijzigt het bedrijf voor ALLE abonnementen die dit bedrijf delen.
        if bedrijf:
            bedrijf.contact_email = (request.form.get('contact_email') or '').strip() or None
            bedrijf.telefoon = (request.form.get('telefoon') or '').strip() or None
            bedrijf.kvk_nummer = (request.form.get('kvk_nummer') or '').strip() or None

        # -----------------------
        # 3) Extra contentvelden
        # -----------------------
        abonnement.frequentie_bezorging = (request.form.get('frequentie_bezorging') or '').strip() or None

        pv = (request.form.get('prijs_vanaf') or '').strip().replace(',', '.')
        pt = (request.form.get('prijs_tot') or '').strip().replace(',', '.')
        try:
            abonnement.prijs_vanaf = float(pv) if pv else None
            abonnement.prijs_tot = float(pt) if pt else None
        except ValueError:
            flash("Prijs vanaf/tot moet een getal zijn (bijv. 12,99).", "danger")
            return redirect(url_for('edit_subscription', id=abonnement.id))

        abonnement.wat_is_het_abonnement = (request.form.get('wat_is_het_abonnement') or '').strip() or None
        abonnement.waarom_kiezen = (request.form.get('waarom_kiezen') or '').strip() or None
        abonnement.hoe_werkt_het = (request.form.get('hoe_werkt_het') or '').strip() or None
        abonnement.past_dit_bij_jou = (request.form.get('past_dit_bij_jou') or '').strip() or None

        abonnement.youtube_url = (request.form.get('youtube_url') or '').strip() or None

        # legacy beoordelingen
        beoordelingen = (request.form.get('beoordelingen') or '').strip()
        if beoordelingen:
            try:
                abonnement.beoordelingen = float(beoordelingen.replace(',', '.'))
            except ValueError:
                flash("Beoordelingen moet een numerieke waarde zijn.", "danger")
                return redirect(url_for('edit_subscription', id=abonnement.id))

        # -----------------------
        # 4) Subcategorie + slug
        # -----------------------
        subcategorie_id = request.form.get('subcategorie_id')
        if not subcategorie_id or not str(subcategorie_id).isdigit():
            flash("Selecteer een geldige subcategorie.", "danger")
            return redirect(url_for('edit_subscription', id=abonnement.id))

        abonnement.subcategorie_id = int(subcategorie_id)

        subcat = Subcategorie.query.get(abonnement.subcategorie_id)
        cat = Categorie.query.get(subcat.categorie_id) if subcat else None

        categorie_slug = (cat.slug if cat and cat.slug else "categorie")
        subcategorie_slug = (subcat.slug if subcat and subcat.slug else "subcategorie")
        naam_slug = slugify(abonnement.naam)
        new_slug = f"{categorie_slug}/{subcategorie_slug}/{naam_slug}"

        exists_slug = Abonnement.query.filter(
            Abonnement.slug == new_slug,
            Abonnement.id != abonnement.id
        ).first()
        if exists_slug:
            flash("Er bestaat al een abonnement met deze slug (zelfde naam/categorie/subcategorie).", "danger")
            return redirect(url_for('edit_subscription', id=abonnement.id))

        abonnement.slug = new_slug

        # -----------------------
        # 5) Status + SEO
        # -----------------------
        allowed_status = {"draft", "published", "archived"}
        new_status = (request.form.get('status') or 'draft').strip()
        if new_status not in allowed_status:
            new_status = "draft"

        old_status = abonnement.status or "draft"
        abonnement.status = new_status

        if old_status != "published" and new_status == "published":
            abonnement.published_at = datetime.utcnow()

        abonnement.seo_title = (request.form.get('seo_title') or '').strip() or None
        abonnement.meta_description = (request.form.get('meta_description') or '').strip() or None
        abonnement.canonical_url = (request.form.get('canonical_url') or '').strip() or None
        abonnement.og_image = (request.form.get('og_image') or '').strip() or None
        abonnement.schema_type = (request.form.get('schema_type') or '').strip() or None
        abonnement.faq_json = (request.form.get('faq_json') or '').strip() or None

        # -----------------------
        # 6) Availability (countries/days/frequency + pause)
        # -----------------------
        abonnement.cutoff_time = (request.form.get('cutoff_time') or '').strip() or None

        ltd = (request.form.get('lead_time_days') or '').strip()
        abonnement.lead_time_days = int(ltd) if ltd.isdigit() else None

        abonnement.pause_possible = (request.form.get('pause_possible') == '1')

        pmw = (request.form.get('pause_max_weeks') or '').strip()
        abonnement.pause_max_weeks = int(pmw) if pmw.isdigit() else None

        AbonnementCountry.query.filter_by(abonnement_id=abonnement.id).delete()
        AbonnementDeliveryDay.query.filter_by(abonnement_id=abonnement.id).delete()
        AbonnementDeliveryFrequency.query.filter_by(abonnement_id=abonnement.id).delete()

        for cc in request.form.getlist('countries'):
            cc = (cc or '').strip().upper()
            if cc in {"NL", "BE"}:
                db.session.add(AbonnementCountry(abonnement_id=abonnement.id, country_code=cc))

        for wd in request.form.getlist('delivery_days'):
            if str(wd).isdigit():
                wdi = int(wd)
                if 1 <= wdi <= 7:
                    db.session.add(AbonnementDeliveryDay(abonnement_id=abonnement.id, weekday=wdi))

        for fw in request.form.getlist('delivery_frequency'):
            if str(fw).isdigit():
                fwi = int(fw)
                if 1 <= fwi <= 7:
                    db.session.add(AbonnementDeliveryFrequency(abonnement_id=abonnement.id, per_week=fwi))

        # -----------------------
        # 7) Plan updaten (cents)
        # -----------------------
        plan_name = ((request.form.get('plan_name') or 'Standaard').strip() or 'Standaard')
        plan_price_eur = (request.form.get('plan_price') or '').strip()
        billing_period = ((request.form.get('billing_period') or 'month').strip() or 'month')

        allowed_periods = {"month", "year", "week", "portion", "one_time"}
        if billing_period not in allowed_periods:
            billing_period = "month"

        price_cents = euro_to_cents(plan_price_eur)
        if price_cents is None or price_cents < 0:
            flash("Vul een geldige planprijs in (bijv. 19,99).", "danger")
            return redirect(url_for('edit_subscription', id=abonnement.id))

        is_from_price = (request.form.get('is_from_price') == '1')
        vat_included = (request.form.get('vat_included') == '1')

        setup_fee_cents = euro_to_cents(request.form.get('setup_fee', '').strip())
        delivery_fee_cents = euro_to_cents(request.form.get('delivery_fee', '').strip())

        min_term_months = (request.form.get('min_term_months') or '').strip()
        cancellation_notice_days = (request.form.get('cancellation_notice_days') or '').strip()
        trial_days = (request.form.get('trial_days') or '').strip()

        promo_code = (request.form.get('promo_code') or '').strip() or None
        promo_end_date = parse_date_yyyy_mm_dd((request.form.get('promo_end_date') or '').strip())
        promo_terms = (request.form.get('promo_terms') or '').strip() or None
        renewal_price_cents = euro_to_cents((request.form.get('renewal_price') or '').strip())
        price_source_url = (request.form.get('price_source_url') or '').strip() or None

        if not plan:
            plan = Plan(abonnement_id=abonnement.id)
            db.session.add(plan)

        plan.plan_name = plan_name
        plan.price_cents = price_cents
        plan.currency = "EUR"
        plan.billing_period = billing_period
        plan.is_from_price = is_from_price
        plan.vat_included = vat_included

        plan.setup_fee_cents = setup_fee_cents
        plan.delivery_fee_cents = delivery_fee_cents

        plan.min_term_months = int(min_term_months) if min_term_months.isdigit() else None
        plan.cancellation_notice_days = int(cancellation_notice_days) if cancellation_notice_days.isdigit() else None
        plan.trial_days = int(trial_days) if trial_days.isdigit() and int(trial_days) > 0 else None

        plan.promo_code = promo_code
        plan.promo_end_date = promo_end_date
        plan.promo_terms = promo_terms
        plan.renewal_price_cents = renewal_price_cents

        plan.price_last_verified_at = datetime.utcnow()
        plan.price_source_url = price_source_url

        # -----------------------
        # 8) Doelgroepen & Tags
        # -----------------------
        dg_ids = [int(x) for x in request.form.getlist('doelgroepen') if str(x).isdigit()]
        tag_ids = [int(x) for x in request.form.getlist('tags') if str(x).isdigit()]

        abonnement.doelgroepen = Doelgroep.query.filter(Doelgroep.id.in_(dg_ids)).all() if dg_ids else []
        abonnement.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

        # -----------------------
        # 9) Logo upload
        # -----------------------
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename and allowed_file(logo_file.filename):
                filename = secure_filename(logo_file.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                logo_path = os.path.join(upload_folder, filename)

                if abonnement.logo:
                    old_path = os.path.join(upload_folder, abonnement.logo)
                    if os.path.exists(old_path):
                        os.remove(old_path)

                img = Image.open(logo_file).convert('RGB')
                resample_filter = getattr(Image, "Resampling", Image).LANCZOS
                img.thumbnail((200, 200), resample_filter)
                img.save(logo_path, format='JPEG', optimize=True, quality=85)

                abonnement.logo = filename

        # -----------------------
        # 10) Foto’s uploaden + verwijderen
        # -----------------------
        foto_bestanden = request.files.getlist('product_fotos')
        for foto in foto_bestanden[:10]:
            if foto and foto.filename and allowed_file(foto.filename):
                foto_filename = secure_filename(foto.filename)
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], foto_filename)
                foto.save(save_path)
                db.session.add(AbonnementFoto(abonnement_id=abonnement.id, bestandsnaam=foto_filename))

        delete_fotos_ids = [int(x) for x in request.form.getlist('delete_fotos') if str(x).isdigit()]
        if delete_fotos_ids:
            fotos_to_delete = AbonnementFoto.query.filter(AbonnementFoto.id.in_(delete_fotos_ids)).all()
            for foto in fotos_to_delete:
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], foto.bestandsnaam)
                if os.path.exists(file_path):
                    os.remove(file_path)
                db.session.delete(foto)

        # -----------------------
        # 11) Commit
        # -----------------------
        db.session.commit()
        flash("Abonnement succesvol bijgewerkt!", "success")
        return redirect(url_for('admin_dashboard'))

    # GET
    return render_template(
        'edit_subscription.html',
        abonnement=abonnement,
        bedrijven=bedrijven,
        categorieen=categorieen,
        subcategorieen=subcategorieen,
        doelgroepen=doelgroepen,
        tags=tags,
        bedrijf=bedrijf,
        plan=plan,
        selected_countries=selected_countries,
        selected_days=selected_days,
        selected_freq=selected_freq
    )

@app.route('/api/subcategorieen/<int:categorie_id>')
def api_subcategorieen(categorie_id):
    """
    Retourneert een JSON-lijst van subcategorieën voor de gegeven categorie_id.
    Wordt gebruikt door edit_subscription.js om dynamisch de <select> te vullen.
    """
    subcats = Subcategorie.query.filter_by(categorie_id=categorie_id).all()
    result = [
        {'id': sub.id, 'naam': sub.naam}
        for sub in subcats
    ]
    return jsonify(result)


@app.route('/tags', methods=['GET', 'POST'])
@login_required
def manage_tags():
    """Beheer tags."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    if request.method == 'POST':
        naam = request.form.get('naam', '').strip()
        if naam:
            bestaande_tag = Tag.query.filter_by(naam=naam).first()
            if bestaande_tag:
                flash(f"Tag '{naam}' bestaat al.", "warning")
            else:
                nieuwe_tag = Tag(naam=naam)
                db.session.add(nieuwe_tag)
                db.session.commit()
                flash(f"Tag '{naam}' toegevoegd!", "success")
        return redirect(url_for('manage_tags'))

    tags = Tag.query.all()
    tag_usage = {tag.id: len(tag.abonnementen) for tag in tags}  # telt hoe vaak elke tag wordt gebruikt

    return render_template('manage_tags.html', tags=tags, tag_usage=tag_usage)



# Route om doelgroepen te beheren
@app.route('/doelgroepen', methods=['GET', 'POST'])
@login_required
def manage_doelgroepen():
    """Beheer doelgroepen."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    if request.method == 'POST':
        naam = request.form.get('naam', '').strip()
        if naam:
            nieuwe_doelgroep = Doelgroep(naam=naam)
            db.session.add(nieuwe_doelgroep)
            db.session.commit()
            flash(f"Doelgroep '{naam}' toegevoegd!", "success")
        return redirect(url_for('manage_doelgroepen'))

    doelgroepen = Doelgroep.query.all()
    return render_template('manage_doelgroepen.html', doelgroepen=doelgroepen)

# Route om een tag te verwijderen
@app.route('/tags/delete/<int:id>', methods=['POST'])
@login_required
def delete_tag(id):
    """Verwijder een tag."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    tag = Tag.query.get_or_404(id)
    db.session.delete(tag)
    db.session.commit()
    flash(f"Tag '{tag.naam}' verwijderd!", "success")
    return redirect(url_for('manage_tags'))


# Route om een doelgroep te verwijderen
@app.route('/doelgroepen/delete/<int:id>', methods=['POST'])
@login_required
def delete_doelgroep(id):
    """Verwijder een doelgroep."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    doelgroep = Doelgroep.query.get_or_404(id)
    db.session.delete(doelgroep)
    db.session.commit()
    flash(f"Doelgroep '{doelgroep.naam}' verwijderd!", "success")
    return redirect(url_for('manage_doelgroepen'))


@app.route('/logs')
@login_required
def view_logs():
    """Optioneel logboek, alleen voor admins."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    logs = Log.query.all()
    return render_template('logs.html', logs=logs)


@app.route('/admin/abonnementen', methods=['GET'])
@login_required
def manage_subscriptions():
    """Overzicht van alle abonnementen met zoek- en filteropties (admin)."""
    if not current_user.is_admin:
        flash("Je hebt geen toegang tot deze pagina.", "danger")
        return redirect(url_for('index'))

    zoekterm = (request.args.get('zoekterm') or '').strip()
    categorie_id = (request.args.get('categorie_id') or '').strip()
    subcategorie_id = (request.args.get('subcategorie_id') or '').strip()
    status = (request.args.get('status') or '').strip()  # optioneel

    # Basis query: abonnementen + (sub)categorie informatie, maar NIET alles wegfilteren als subcategorie ontbreekt
    query = (
        Abonnement.query
        .outerjoin(Subcategorie, Abonnement.subcategorie_id == Subcategorie.id)
        .outerjoin(Categorie, Subcategorie.categorie_id == Categorie.id)
        .options(
            joinedload(Abonnement.subcategorie).joinedload(Subcategorie.categorie)
        )
    )

    # Zoekterm
    if zoekterm:
        query = query.filter(Abonnement.naam.ilike(f'%{zoekterm}%'))

    # Categorie filter
    if categorie_id.isdigit():
        cid = int(categorie_id)
        query = query.filter(Subcategorie.categorie_id == cid)

    # Subcategorie filter
    if subcategorie_id.isdigit():
        scid = int(subcategorie_id)
        query = query.filter(Abonnement.subcategorie_id == scid)

    # Status filter (optioneel)
    allowed_status = {"draft", "published", "archived"}
    if status in allowed_status:
        query = query.filter(Abonnement.status == status)

    abonnementen = query.order_by(Abonnement.naam.asc()).all()

    # Dropdown data
    categorieen = Categorie.query.order_by(Categorie.volgorde.asc()).all()

    subcategorieen = []
    if categorie_id.isdigit():
        subcategorieen = (
            Subcategorie.query
            .filter_by(categorie_id=int(categorie_id))
            .order_by(Subcategorie.naam.asc())
            .all()
        )

    return render_template(
        'manage_subscriptions.html',
        abonnementen=abonnementen,
        categorieen=categorieen,
        subcategorieen=subcategorieen,
        zoekterm=zoekterm,
        geselecteerde_categorie=categorie_id,
        geselecteerde_subcategorie=subcategorie_id,
        geselecteerde_status=status
    )
# =============== ADMIN: blog toevoegen (meervoudige koppelingen) ===============
@app.route('/admin/blog/nieuw', methods=['GET', 'POST'], endpoint='blog_toevoegen')
@login_required
def blog_toevoegen_v2():
    if not current_user.is_admin:
        abort(403)

    categorieen = Categorie.query.order_by(Categorie.naam.asc()).all()
    subcategorieen = Subcategorie.query.order_by(Subcategorie.naam.asc()).all()
    abonnementen = Abonnement.query.order_by(Abonnement.naam.asc()).all()

    if request.method == 'POST':
        auteur_naam = (request.form.get("auteur_naam") or "").strip() or None
        titel = request.form['titel'].strip()
        inhoud = request.form['inhoud']
        video_url = (request.form.get('video_url') or '').strip()
        afbeelding = request.files.get('afbeelding')

        # Unieke slug
        base_slug = slugify(titel)
        slug = base_slug
        i = 1
        while BlogPost.query.filter(func.lower(BlogPost.slug) == slug.lower()).first():
            slug = f"{base_slug}-{i}"
            i += 1

        # YouTube watch -> embed
        if video_url and 'watch?v=' in video_url:
            video_url = video_url.replace('watch?v=', 'embed/')

        # Afbeelding opslaan
        bestandsnaam = None
        if afbeelding and allowed_file(afbeelding.filename):
            bestandsnaam = secure_filename(afbeelding.filename)
            pad = os.path.join(app.config['UPLOAD_FOLDER'], bestandsnaam)
            afbeelding.save(pad)

        # Nieuwe post
        nieuw = BlogPost(
            titel=titel,
            slug=slug,
            inhoud=inhoud,
            afbeelding=bestandsnaam,
            video_url=video_url,
            auteur=current_user,
            auteur_naam=auteur_naam
        )

        # Meervoudige koppelingen (allemaal optioneel)
        cat_ids = [int(x) for x in request.form.getlist('categorie_ids')]
        sub_ids = [int(x) for x in request.form.getlist('subcategorie_ids')]
        abo_ids = [int(x) for x in request.form.getlist('abonnement_ids')]

        if cat_ids:
            nieuw.categorieen = Categorie.query.filter(Categorie.id.in_(cat_ids)).all()
        if sub_ids:
            nieuw.subcategorieen = Subcategorie.query.filter(Subcategorie.id.in_(sub_ids)).all()
        if abo_ids:
            nieuw.abonnementen = Abonnement.query.filter(Abonnement.id.in_(abo_ids)).all()

        db.session.add(nieuw)
        db.session.commit()
        flash("Blogbericht geplaatst!", "success")
        return redirect(url_for('admin_blog_overzicht'))

    return render_template(
        'blog_formulier.html',
        categorieen=categorieen,
        subcategorieen=subcategorieen,
        abonnementen=abonnementen,
        post=None
    )

# =============== ADMIN: blogoverzicht ===============
@app.route('/admin/blog', endpoint='admin_blog_overzicht')
@login_required
def admin_blog_overzicht_v2():
    if not current_user.is_admin:
        abort(403)
    posts = BlogPost.query.order_by(BlogPost.datum.desc()).all()
    return render_template('admin_blog_overzicht.html', posts=posts)

# =============== ADMIN: blog bewerken ===============
@app.route('/admin/blog/bewerk/<int:post_id>', methods=['GET', 'POST'], endpoint='blog_bewerken')
@login_required
def blog_bewerken_v2(post_id):
    if not current_user.is_admin:
        abort(403)

    post = BlogPost.query.get_or_404(post_id)
    categorieen = Categorie.query.order_by(Categorie.naam.asc()).all()
    subcategorieen = Subcategorie.query.order_by(Subcategorie.naam.asc()).all()
    abonnementen = Abonnement.query.order_by(Abonnement.naam.asc()).all()

    if request.method == 'POST':
        post.auteur_naam = (request.form.get("auteur_naam") or "").strip() or None
        post.titel = request.form['titel'].strip()
        post.inhoud = request.form['inhoud']

        video_url = (request.form.get('video_url') or '').strip()
        if video_url and 'watch?v=' in video_url:
            video_url = video_url.replace('watch?v=', 'embed/')
        post.video_url = video_url

        afbeelding = request.files.get('afbeelding')
        if afbeelding and allowed_file(afbeelding.filename):
            filename = secure_filename(afbeelding.filename)
            pad = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            afbeelding.save(pad)
            post.afbeelding = filename

        # Koppelingen updaten
        cat_ids = [int(x) for x in request.form.getlist('categorie_ids')]
        sub_ids = [int(x) for x in request.form.getlist('subcategorie_ids')]
        abo_ids = [int(x) for x in request.form.getlist('abonnement_ids')]

        post.categorieen = Categorie.query.filter(Categorie.id.in_(cat_ids)).all() if cat_ids else []
        post.subcategorieen = Subcategorie.query.filter(Subcategorie.id.in_(sub_ids)).all() if sub_ids else []
        post.abonnementen = Abonnement.query.filter(Abonnement.id.in_(abo_ids)).all() if abo_ids else []

        db.session.commit()
        flash("Blog bijgewerkt", "success")
        return redirect(url_for('admin_blog_overzicht'))

    return render_template(
        'blog_formulier.html',
        post=post,
        categorieen=categorieen,
        subcategorieen=subcategorieen,
        abonnementen=abonnementen
    )

# =============== ADMIN: blog verwijderen ===============
@app.route('/admin/blog/verwijder/<int:post_id>', methods=['POST'], endpoint='blog_verwijderen')
@login_required
def blog_verwijderen_v2(post_id):
    if not current_user.is_admin:
        abort(403)
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Blog verwijderd", "success")
    return redirect(url_for('admin_blog_overzicht'))

# =============== BLOG OVERZICHT: cascaderende filters ===============
@app.route('/blog', endpoint='blog_overzicht', strict_slashes=False)
def blog_overzicht():
    """
    Filters (via URL-params, optioneel):
      ?categorie=<categorie-slug>
      ?subcategorie=<subcategorie-slug>
      ?abonnement=<abonnement-slug>
    Cascadering (server-side voor URL-filters):
      - categorie => ook posts gekoppeld aan subcategorieën & abonnementen onder die categorie
      - subcategorie => ook posts gekoppeld aan abonnementen onder die subcategorie (en evt. categorie)
      - abonnement => evt. ook posts die aan de bijbehorende sub/categorie hangen

    Let op: op de pagina zelf werkt de sidebar-filter client-side (snel, zonder requests).
    """
    cat_slug = request.args.get('categorie')
    sub_slug = request.args.get('subcategorie')
    abo_slug = request.args.get('abonnement')

    q = BlogPost.query.order_by(BlogPost.datum.desc())

    if abo_slug:
        abo = Abonnement.query.filter_by(slug=abo_slug).first()
        if abo:
            q = q.filter(
                or_(
                    BlogPost.abonnementen.any(Abonnement.id == abo.id),
                    BlogPost.subcategorieen.any(Subcategorie.id == abo.subcategorie_id),
                    BlogPost.categorieen.any(Categorie.id == abo.subcategorie.categorie_id)
                )
            )

    elif sub_slug:
        sub = Subcategorie.query.filter_by(slug=sub_slug).first()
        if sub:
            abo_ids = [a.id for a in Abonnement.query.filter_by(subcategorie_id=sub.id).all()]
            q = q.filter(
                or_(
                    BlogPost.subcategorieen.any(Subcategorie.id == sub.id),
                    BlogPost.abonnementen.any(Abonnement.id.in_(abo_ids)),
                    BlogPost.categorieen.any(Categorie.id == sub.categorie_id)
                )
            )

    elif cat_slug:
        cat = Categorie.query.filter_by(slug=cat_slug).first()
        if cat:
            sub_ids = [s.id for s in Subcategorie.query.filter_by(categorie_id=cat.id).all()]
            abo_ids = [a.id for a in Abonnement.query.filter(Abonnement.subcategorie_id.in_(sub_ids)).all()]
            q = q.filter(
                or_(
                    BlogPost.categorieen.any(Categorie.id == cat.id),
                    BlogPost.subcategorieen.any(Subcategorie.id.in_(sub_ids)),
                    BlogPost.abonnementen.any(Abonnement.id.in_(abo_ids))
                )
            )

    posts = q.all()

    # Lijsten voor de sidebar-filter (client-side cascade)
    categorieen = Categorie.query.order_by(Categorie.naam.asc()).all()
    subcategorieen = Subcategorie.query.order_by(Subcategorie.naam.asc()).all()
    abonnementen = Abonnement.query.order_by(Abonnement.naam.asc()).all()

    return render_template(
        'blog_overzicht.html',
        posts=posts,
        categorieen=categorieen,
        subcategorieen=subcategorieen,
        abonnementen=abonnementen
    )

# =============== BLOG DETAIL ===============
@app.route('/blog/<slug>', endpoint='blog_detail', strict_slashes=False)
@app.route('/blog/<slug>/', strict_slashes=False)
def blog_detail_v2(slug):
    post = BlogPost.query.filter_by(slug=slug).first_or_404()

    related_posts = (
        BlogPost.query
        .filter(BlogPost.id != post.id)
        .order_by(BlogPost.datum.desc())
        .limit(3)
        .all()
    )
    return render_template('blog_detail.html', post=post, related_posts=related_posts)

# ---------------------------------------
# Routes: Abonnementen vergelijken (publiek)
# ---------------------------------------
# ---- helpers ----
def _normalize_combo(slugs):
    """Sorteer en plak slugs als a-vs-b[-vs-c]."""
    return "-vs-".join(sorted(s.strip() for s in slugs if s and s.strip()))

def slug_leaf(s: str) -> str:
    return s.strip('/').split('/')[-1]

def _normalize_combo(slugs):
    return "-vs-".join(sorted(s.strip() for s in slugs if s and s.strip()))


@app.route('/vergelijk')
def vergelijk():
    slugs_string = request.args.get('abonnementen', '')
    slugs = [s for s in slugs_string.split(',') if s.strip()]
    if slugs:
        abs_ = Abonnement.query.filter(Abonnement.slug.in_(slugs)).all()
        if len(abs_) >= 2:
            cat_ids = {a.subcategorie.categorie_id for a in abs_ if a.subcategorie and a.subcategorie.categorie_id}
            if len(cat_ids) == 1:
                combo = _normalize_combo([slug_leaf(a.slug) for a in abs_])
                return redirect(url_for('vergelijk_flat', combo=combo), code=301)
            else:
                flash("Je kunt alleen abonnementen binnen dezelfde categorie vergelijken.", "error")
                return render_template('vergelijk.html',
                                       abonnementen=[],
                                       categorie=None,
                                       indexable=False,
                                       canonical=url_for('vergelijk', _external=True)), 200

    # Lege of 1 item
    flash("Selecteer minimaal 2 abonnementen om te vergelijken.", "warning")
    return render_template('vergelijk.html',
                           abonnementen=[],
                           categorie=None,
                           indexable=False,
                           canonical=url_for('vergelijk', _external=True)), 200

# ---- pretty URL: /vergelijk/<subcat>/<slug1>-vs-<slug2>[-vs-...]/
@app.route('/vergelijk/<path:combo>/')
def vergelijk_flat(combo):
    leaves = [slug_leaf(x) for x in combo.strip('/').split('-vs-') if x]
    if not leaves:
        flash("Selecteer minimaal 2 abonnementen om te vergelijken.", "warning")
        return render_template('vergelijk.html',
                               abonnementen=[],
                               categorie=None,
                               indexable=False,
                               canonical=url_for('vergelijk', _external=True)), 200

    abs_all = Abonnement.query.all()
    leaf_map = {slug_leaf(a.slug): a for a in abs_all}
    abonnementen = [leaf_map[l] for l in leaves if l in leaf_map]

    # => VALIDATIE: zelfde CATEGORIE
    cat_ids = {a.subcategorie.categorie_id for a in abonnementen if a.subcategorie and a.subcategorie.categorie_id} if abonnementen else set()
    valid = len(abonnementen) >= 2 and len(cat_ids) == 1

    if not valid:
        flash("Je kunt alleen abonnementen binnen dezelfde categorie vergelijken.", "error")
        return render_template('vergelijk.html',
                               abonnementen=[],
                               categorie=None,
                               indexable=False,
                               canonical=url_for('vergelijk', _external=True)), 200

    categorie = Categorie.query.get(next(iter(cat_ids)))
    normalized_combo = _normalize_combo([slug_leaf(a.slug) for a in abonnementen])

    if combo != normalized_combo:
        return redirect(url_for('vergelijk_flat', combo=normalized_combo), code=301)

    canonical = url_for('vergelijk_flat', combo=normalized_combo, _external=True)
    return render_template('vergelijk.html',
                           abonnementen=abonnementen,
                           categorie=categorie,
                           indexable=True,
                           canonical=canonical), 200

@app.route('/update_comparison', methods=['POST'])
def update_comparison():
    data = request.get_json()
    abonnement_ids = data.get('abonnement_ids', [])
    
    # Zet de ID's als een komma-gescheiden string in een cookie
    response = jsonify({"message": "Comparison list updated!"})
    response.set_cookie('comparison_ids', ','.join(map(str, abonnement_ids)), max_age=60*60*24*7)  # 7 dagen geldig
    return response

@app.route('/clear_comparison', methods=['POST'])
def clear_comparison():
    if request.method == 'POST':
        response = redirect(url_for('index'))  # Stuur gebruiker terug naar de hoofdpagina
        response.set_cookie('comparison_ids', '', expires=0)  # Verwijder de cookie
        flash("Vergelijking gewist!", "success")  # Optioneel: melding tonen
        return response
    else:
        return "Ongeldige aanvraag", 400  # Beveiliging tegen verkeerde methodes

# ---------------------------------------
# Routes: publiek toevoegen / bewerken
# ---------------------------------------

@app.route('/verwijder/<int:id>', methods=['POST'])
def verwijder(id):
    """Publieke route om een abonnement te verwijderen."""
    abonnement = Abonnement.query.get_or_404(id)
    if abonnement.logo:
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], abonnement.logo)
        if os.path.exists(logo_path):
            os.remove(logo_path)
    db.session.delete(abonnement)
    db.session.commit()
    return redirect(url_for('abonnementen'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        naam = request.form['naam']
        email = request.form['email']
        bericht = request.form['bericht']
        
        # Opslaan in de database
        nieuw_bericht = ContactBericht(naam=naam, email=email, bericht=bericht)
        db.session.add(nieuw_bericht)
        db.session.commit()
        
        flash("Je bericht is succesvol verzonden!", "success")
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/berichten')
def berichten():
    alle_berichten = ContactBericht.query.order_by(ContactBericht.datum.desc()).all()
    return render_template('berichten.html', berichten=alle_berichten)

@app.route('/bericht/verwijder/<int:id>', methods=['POST'])
def verwijder_bericht(id):
    bericht = ContactBericht.query.get_or_404(id)  # Zoek het bericht op basis van ID
    db.session.delete(bericht)  # Verwijder het bericht uit de database
    db.session.commit()  # Voer de wijziging door in de database
    flash("Het bericht is succesvol verwijderd.", "success")
    return redirect(url_for('berichten'))  # Keer terug naar de berichtenpagina

# ---------------------------------------
# Routes: Categorieën en Subcategorieën
# ---------------------------------------

@app.route('/categorieen', methods=['GET', 'POST'])
def categorieen():
    if request.method == 'POST':
        # Toevoegen van een categorie
        if 'categorie_naam' in request.form and 'categorie_id' not in request.form:
            nieuwe_naam = request.form['categorie_naam'].strip()
            beschrijving = request.form.get('categorie_beschrijving', '').strip()

            if nieuwe_naam:
                nieuwe_categorie = Categorie(naam=nieuwe_naam, beschrijving=beschrijving)
                db.session.add(nieuwe_categorie)
                db.session.commit()

        # Toevoegen van een subcategorie
        elif 'subcategorie_naam' in request.form and 'categorie_id' in request.form:
            subcategorie_naam = request.form['subcategorie_naam'].strip()
            subcategorie_beschrijving = request.form.get('subcategorie_beschrijving', '').strip()
            categorie_id = request.form['categorie_id']

            if subcategorie_naam and categorie_id:
                nieuwe_subcategorie = Subcategorie(
                    naam=subcategorie_naam,
                    categorie_id=categorie_id,
                    beschrijving=subcategorie_beschrijving
                )
                db.session.add(nieuwe_subcategorie)
                db.session.commit()

        return redirect(url_for('categorieen'))

    categorieen = Categorie.query.all()
    return render_template('categorieen_beheren.html', categorieen=categorieen)

@app.route('/verwijder_categorie/<int:id>', methods=['POST'])
def verwijder_categorie(id):
    categorie = Categorie.query.get_or_404(id)
    db.session.delete(categorie)
    db.session.commit()
    return redirect(url_for('categorieen'))

@app.route('/categorie/<int:id>/update_volgorde', methods=['POST'])
def update_categorie_volgorde(id):
    categorie = Categorie.query.get_or_404(id)
    nieuwe_volgorde = request.form.get('volgorde', type=int)
    if nieuwe_volgorde is not None:
        categorie.volgorde = nieuwe_volgorde
        db.session.commit()
        flash("Categorievolgorde bijgewerkt!", "success")
    return redirect(url_for('categorieen'))

@app.route('/verwijder_subcategorie/<int:id>', methods=['POST'])
def verwijder_subcategorie(id):
    subcategorie = Subcategorie.query.get_or_404(id)
    db.session.delete(subcategorie)
    db.session.commit()
    return redirect(url_for('categorieen'))

@app.route('/bewerk_categorie/<int:id>', methods=['GET', 'POST'])
def bewerk_categorie(id):
    categorie = Categorie.query.get_or_404(id)
    if request.method == 'POST':
        nieuwe_naam = request.form['categorie_naam'].strip()
        nieuwe_beschrijving = request.form.get('categorie_beschrijving', '').strip()

        if nieuwe_naam:
            categorie.naam = nieuwe_naam
            categorie.beschrijving = nieuwe_beschrijving  # ✅ sla beschrijving op
            db.session.commit()
            flash("Categorie succesvol bijgewerkt!", "success")

        return redirect(url_for('categorieen'))

    return render_template('bewerk_categorie.html', categorie=categorie)


@app.route('/bewerk_subcategorie/<int:id>', methods=['POST'])
def bewerk_subcategorie(id):
    subcategorie = Subcategorie.query.get_or_404(id)

    nieuwe_naam = request.form['subcategorie_naam'].strip()
    nieuwe_beschrijving = request.form.get('subcategorie_beschrijving', '').strip()

    if nieuwe_naam:
        subcategorie.naam = nieuwe_naam
        subcategorie.beschrijving = nieuwe_beschrijving
        db.session.commit()
        flash("Subcategorie bijgewerkt", "success")

    return redirect(url_for('categorieen'))


# Route voor de chatbot training pagina
@app.route("/admin/chatbot-training", methods=["GET", "POST"])
def admin_train_chatbot():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == "POST":
        # Lees de lijsten met IDs, vragen en antwoorden uit het formulier
        id_list = request.form.getlist("id")
        vraag_list = request.form.getlist("vraag")
        antwoord_list = request.form.getlist("antwoord")
        
        for record_id, vraag, antwoord in zip(id_list, vraag_list, antwoord_list):
            cursor.execute(
                "UPDATE chatbot_logs SET vraag = ?, antwoord = ? WHERE rowid = ?",
                (vraag, antwoord, record_id)
            )
        conn.commit()
        conn.close()
        
        # Roep de trainingsfunctie aan (met de alias)
        train_chatbot_model()
        # Controleer of het een AJAX-request is
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=True)
        else:
            flash("Chatbot getraind en wijzigingen opgeslagen!")
            return redirect(url_for("admin_train_chatbot"))
    else:
        cursor.execute("SELECT rowid AS id, vraag, antwoord FROM chatbot_logs ORDER BY rowid ASC")
        logs = cursor.fetchall()
        conn.close()
        return render_template("admin_chatbot_training.html", logs=logs)

@app.route('/admin/chatbot-metrics', methods=['GET'])
def chatbot_metrics():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT vraag, antwoord FROM chatbot_logs")
            data = cursor.fetchall()
        
        if not data:
            return jsonify({"accuracy": "N/A", "f1": "N/A"})
        
        # Haal de vragen en antwoorden uit de data
        vragen, antwoorden = zip(*data)
        
        # Als er te weinig data is, retourneren we een melding
        if len(vragen) < 5:
            return jsonify({"accuracy": "Te weinig data", "f1": "Te weinig data"})
        
        # Splits de data in training en test (80/20)
        X_train, X_test, y_train, y_test = train_test_split(vragen, antwoorden, test_size=0.2, random_state=42)
        
        # Maak een pipeline aan en train deze op de trainingsdata
        pipeline = make_pipeline(TfidfVectorizer(), MultinomialNB())
        pipeline.fit(X_train, y_train)
        
        # Voorspel de antwoorden voor de testdata
        predictions = pipeline.predict(X_test)
        
        # Bereken de accuraatheid en F1-score (weighted gemiddelde)
        acc = accuracy_score(y_test, predictions)
        f1 = f1_score(y_test, predictions, average='weighted')
        
        return jsonify({"accuracy": round(acc, 2), "f1": round(f1, 2)})
    
    except Exception as e:
        return jsonify({"accuracy": "Error", "f1": "Error", "error": str(e)})

# Route voor het verwijderen van een chatbot-log (DELETE)
@app.route('/admin/chatbot-delete/<int:id>', methods=['DELETE'])
def delete_chatbot_log(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chatbot_logs WHERE rowid = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

# ---------------------------------------
# Database aanmaken
# ---------------------------------------

@app.route('/admin/generate-category-slugs')
def generate_category_slugs():
    from slugify import slugify

    for cat in Categorie.query.all():
        cat.slug = slugify(cat.naam)
    for sub in Subcategorie.query.all():
        sub.slug = slugify(sub.naam)
    
    db.session.commit()
    return "✅ Slugs gegenereerd voor categorieën en subcategorieën"

# ---------------------------------------
# Google optimalisatie
# ---------------------------------------
@app.before_request
def enforce_trailing_slash():
    # Alleen voor blog-sectie
    if request.path.startswith("/blog") and not request.path.endswith("/"):
        # redirect naar versie met slash
        return redirect(request.path + "/", code=301)
    
@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    base_url = 'https://abbohub.nl'
    pages = []

    def slug_leaf(s: str) -> str:
        return s.strip('/').split('/')[-1]

    def _normalize_combo(slugs):
        return "-vs-".join(sorted(s.strip() for s in slugs if s and s.strip()))

    def iso_or_none(dt):
        try:
            if not dt:
                return None
            if isinstance(dt, datetime):
                # force UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt.isoformat(timespec='seconds')
            # date object -> make datetime at 00:00 UTC
            if hasattr(dt, 'isoformat') and hasattr(dt, 'year'):
                return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).isoformat(timespec='seconds')
        except Exception:
            pass
        return None

    def max_iso(*values):
        # values are ISO strings or None; return max as ISO or None
        parsed = []
        for v in values:
            if not v:
                continue
            try:
                parsed.append(datetime.fromisoformat(v.replace('Z', '+00:00')))
            except Exception:
                pass
        if not parsed:
            return None
        return max(parsed).astimezone(timezone.utc).isoformat(timespec='seconds')

    # 1) Home
    pages.append({'loc': f"{base_url}/", 'changefreq': 'weekly', 'priority': '1.0', 'lastmod': None})

    # 2) Categorieën & subcategorieën
    cats = Categorie.query.all()
    for cat in cats:
        slug = getattr(cat, 'slug', None)
        if not slug:
            continue
        pages.append({
            'loc': f"{base_url}/categorie/{slug}/",
            'changefreq': 'weekly',
            'priority': '0.8',
            'lastmod': iso_or_none(getattr(cat, 'updated_at', None))
        })

        subs = Subcategorie.query.filter_by(categorie_id=cat.id).all()
        for sub in subs:
            sub_slug = getattr(sub, 'slug', None)
            if not sub_slug:
                continue
            pages.append({
                'loc': f"{base_url}/categorie/{slug}/{sub_slug}/",
                'changefreq': 'weekly',
                'priority': '0.7',
                'lastmod': iso_or_none(getattr(sub, 'updated_at', None))
            })

    # 3) Review-detailpagina's
    abonnementen = Abonnement.query.all()
    for ab in abonnementen:
        ab_slug = getattr(ab, 'slug', None)
        if ab_slug:
            pages.append({
                'loc': f"{base_url}/review/{ab_slug}",
                'changefreq': 'monthly',
                'priority': '0.6',
                'lastmod': iso_or_none(getattr(ab, 'updated_at', None) or getattr(ab, 'published_at', None))
            })

    # 3b) Vergelijk-URL's per categorie
    seen_combos = set()
    for cat in cats:
        abs_cat = (
            Abonnement.query
            .join(Subcategorie, Abonnement.subcategorie_id == Subcategorie.id)
            .filter(Subcategorie.categorie_id == cat.id)
            .order_by(Abonnement.volgorde.asc())
            .limit(3)
            .all()
        )
        for i in range(len(abs_cat)):
            for j in range(i+1, len(abs_cat)):
                leaf_i = slug_leaf(abs_cat[i].slug or '')
                leaf_j = slug_leaf(abs_cat[j].slug or '')
                combo = _normalize_combo([leaf_i, leaf_j])
                if not combo or combo in seen_combos:
                    continue
                seen_combos.add(combo)
                lastmod_i = iso_or_none(getattr(abs_cat[i], 'updated_at', None) or getattr(abs_cat[i], 'published_at', None))
                lastmod_j = iso_or_none(getattr(abs_cat[j], 'updated_at', None) or getattr(abs_cat[j], 'published_at', None))
                pages.append({
                    'loc': f"{base_url}/vergelijk/{combo}/",
                    'changefreq': 'weekly',
                    'priority': '0.50',
                    'lastmod': max_iso(lastmod_i, lastmod_j)
                })

    # 4) Blog
    pages.append({'loc': f"{base_url}/blog/", 'changefreq': 'weekly', 'priority': '0.7', 'lastmod': None})
    try:
        blogposts = BlogPost.query.all()
        latest_blog = None
        for post in blogposts:
            pslug = getattr(post, 'slug', None)
            p_last = iso_or_none(getattr(post, 'updated_at', None) or getattr(post, 'published_at', None))
            latest_blog = max_iso(latest_blog, p_last)
            if pslug:
                pages.append({
                    'loc': f"{base_url}/blog/{pslug}/",
                    'changefreq': 'monthly',
                    'priority': '0.6',
                    'lastmod': p_last
                })
        # lastmod for blog overview = meest recente post
        if latest_blog:
            pages[ - (len(blogposts) + 1) ] = { **pages[ - (len(blogposts) + 1) ], 'lastmod': latest_blog }
    except Exception as e:
        print("Geen BlogPost model gevonden:", e)

    # XML opbouwen (escaped)
    sitemap_xml  = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for p in pages:
        loc = escape(p['loc'])
        sitemap_xml += '  <url>\n'
        sitemap_xml += f"    <loc>{loc}</loc>\n"
        if p.get('lastmod'):
            sitemap_xml += f"    <lastmod>{p['lastmod']}</lastmod>\n"
        sitemap_xml += f"    <changefreq>{p['changefreq']}</changefreq>\n"
        sitemap_xml += f"    <priority>{p['priority']}</priority>\n"
        sitemap_xml += '  </url>\n'
    sitemap_xml += '</urlset>'
    return Response(sitemap_xml, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

@app.route('/ads.txt')
def ads():
  return send_from_directory(os.path.dirname(__file__), 'ads.txt', mimetype='text/plain')

@app.route('/d2cb9643c6e6cd8.html')
def verify_daisycon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'verification'), 'd2cb9643c6e6cd8.html')

# --------user tracking---------

@app.route('/out/<int:ab_id>')
def outbound(ab_id):
    ab = Abonnement.query.get_or_404(ab_id)

    # Bepaal target
    target = ab.affiliate_url or ab.url
    if not target:
        abort(404)

    # Wanneer het een preview/bot is, niet echt redirecten (voorkom valse kliks)
    if is_headless_previewer():
        # Toon een kleine info-pagina ipv redirect
        return (
            f"<title>AbboHub – Outbound</title>"
            f"<p>Outbound klik naar: <a href='{target}' rel='nofollow noopener'>{target}</a></p>"
            f"<p>Deze weergave is gedetecteerd als bot/preview en wordt daarom niet doorgestuurd.</p>",
            200,
            {'Content-Type': 'text/html; charset=utf-8'}
        )

    # Verzamel context
    ip = get_client_ip()
    ip_h = hash_ip(ip)
    ua = request.headers.get('User-Agent', '')
    ref = request.headers.get('Referer', '')
    landing = request.args.get('from', '') or request.path  # je kunt in templates ?from={{ request.path }} meegeven
    gaid = get_ga_client_id()

    # Log click
    used_affiliate = bool(ab.affiliate_url)
    click = Click(
        abonnement_id=ab.id,
        used_affiliate=used_affiliate,
        target_url=target[:512],
        ip_hash=ip_h or None,
        user_agent=ua[:1000] if ua else None,
        referer=ref[:1000] if ref else None,
        landing_path=landing[:255] if landing else None,
        ga_client_id=gaid or None
    )
    db.session.add(click)
    db.session.commit()

    # Redirect
    return redirect(target, code=302)
@app.route('/admin/clicks')
@login_required
def admin_clicks():
    if not current_user.is_admin:
        flash("Je hebt geen toegang tot deze pagina.", "danger")
        return redirect(url_for('index'))

    # Filters
    date_from_str = request.args.get('from', '')
    date_to_str = request.args.get('to', '')
    date_from = None
    date_to = None
    try:
        if date_from_str:
            date_from = datetime.fromisoformat(date_from_str)
        if date_to_str:
            # maak 'to' exclusief einde dag als alleen datum is gegeven
            dt = datetime.fromisoformat(date_to_str)
            date_to = dt + timedelta(days=1)
    except Exception:
        pass

    # Detail-rijen (laatste 500 kliks)
    q = (
        db.session.query(
            Click.id,
            Click.created_at,
            Click.abonnement_id,
            Click.used_affiliate,
            Click.target_url,
            Click.referer,
            Click.landing_path,
            Abonnement.naam.label('ab_naam')
        )
        .join(Abonnement, Abonnement.id == Click.abonnement_id)
    )

    if date_from:
        q = q.filter(Click.created_at >= date_from)
    if date_to:
        q = q.filter(Click.created_at < date_to)

    rows = q.order_by(Click.created_at.desc()).limit(500).all()

    # Dag-aggregatie (kliks per dag per abonnement)
    agg_q = (
        db.session.query(
            func.date(Click.created_at).label('dag'),
            Abonnement.naam.label('ab_naam'),
            func.count(Click.id).label('clicks'),
            # ✅ Belangrijk: gebruik sqlalchemy.case i.p.v. func.case
            func.sum(case((Click.used_affiliate == True, 1), else_=0)).label('aff_clicks')
            # Als je oudere SQLAlchemy gebruikt:
            # func.sum(case([(Click.used_affiliate == True, 1)], else_=0)).label('aff_clicks')
        )
        .join(Abonnement, Abonnement.id == Click.abonnement_id)
    )

    if date_from:
        agg_q = agg_q.filter(Click.created_at >= date_from)
    if date_to:
        agg_q = agg_q.filter(Click.created_at < date_to)

    agg = (
        agg_q
        .group_by(func.date(Click.created_at), Abonnement.naam)
        .order_by(func.date(Click.created_at).desc())
        .all()
    )

    return render_template(
        'admin_clicks.html',
        rows=rows,
        agg=agg,
        date_from=date_from_str,
        date_to=date_to_str
    )

@app.route('/algemene-voorwaarden')
def algemene_voorwaarden():
    return render_template('algemene_voorwaarden.html')


@app.route('/admin/clicks/export.csv')
@login_required
def admin_clicks_export():
    if not current_user.is_admin:
        flash("Je hebt geen toegang tot deze pagina.", "danger")
        return redirect(url_for('index'))

    date_from_str = request.args.get('from', '')
    date_to_str = request.args.get('to', '')
    date_from = None
    date_to = None
    try:
        if date_from_str:
            date_from = datetime.fromisoformat(date_from_str)
        if date_to_str:
            dt = datetime.fromisoformat(date_to_str)
            date_to = dt + timedelta(days=1)
    except Exception:
        pass

    q = db.session.query(
        Click.created_at, Abonnement.naam.label('ab_naam'),
        Click.used_affiliate, Click.target_url,
        Click.referer, Click.landing_path
    ).join(Abonnement, Abonnement.id == Click.abonnement_id)

    if date_from:
        q = q.filter(Click.created_at >= date_from)
    if date_to:
        q = q.filter(Click.created_at < date_to)

    q = q.order_by(Click.created_at.desc())

    si = StringIO()
    w = csv.writer(si)
    w.writerow(["created_at","abonnement","used_affiliate","target_url","referer","landing_path"])
    for r in q.all():
        w.writerow([r.created_at, r.ab_naam, int(r.used_affiliate), r.target_url, r.referer or "", r.landing_path or ""])

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=clicks_export.csv"}
    )


# ---------------------------------------
# Start de app (development)
# ---------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
