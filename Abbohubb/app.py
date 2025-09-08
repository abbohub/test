# app.py
from flask import Flask
import os
import uuid
from datetime import datetime
from sqlalchemy.schema import UniqueConstraint  # zorg dat dit bovenin staat
from flask import Response
from PIL import Image
from flask import current_app
from sqlalchemy import func, case
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from flask import Response


# Alleen nodig als je environment variables gebruikt
# (Bijvoorbeeld SECRET_KEY uit .env)
from dotenv import load_dotenv

from flask import (
    render_template, request, redirect, url_for, flash, current_app
)
from flask import jsonify, request, redirect, url_for, flash, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired
from sqlalchemy.orm import joinedload
from flask_wtf.csrf import CSRFProtect
from flask import send_from_directory
from flask import Flask, render_template, request, redirect, url_for, flash
from flask import flash, Response, render_template, redirect, request, url_for
from flask import abort
import sqlite3
import os
import hashlib
import csv
from io import StringIO
from urllib.parse import urlparse
from flask import request
from datetime import datetime, timedelta
from sqlalchemy import func
from chatbot import train_chatbot as train_chatbot_model  # Zorg dat je de train_chatbot functie importeert uit chatbot.py
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from slugify import slugify
from flask import redirect, url_for, abort
from flask import redirect, request
from flask import Flask

app = Flask(__name__)
app.url_map.strict_slashes = False   # zet dit meteen na je app = Flask(...)


# Maak de Flask-app aan
app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'jouw_geheime_sleutel'

# Activeer CSRF-bescherming
csrf = CSRFProtect(app)

# Laad .env-variabelen (optioneel)
load_dotenv()

# ---------------------------------------
# Configuratie
# ---------------------------------------
# Haal SECRET_KEY op uit de environment, met fallback
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///abonnementen.db'
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
# Database-modellen
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

class Subcategorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False)
    categorie_id = db.Column(db.Integer, db.ForeignKey('categorie.id'), nullable=False)
    abonnementen = db.relationship('Abonnement', backref='subcategorie', lazy=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    beschrijving = db.Column(db.Text, nullable=True)
    

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
    id = db.Column(db.Integer, primary_key=True)
    bedrijf_id       = db.Column(db.Integer, db.ForeignKey('bedrijf.id'), nullable=True)
    naam = db.Column(db.String(100), nullable=False)
    beschrijving = db.Column(db.String(140), nullable=True)
    filter_optie = db.Column(db.String(20), nullable=False)
    logo = db.Column(db.String(200), nullable=True)
    subcategorie_id = db.Column(db.Integer, db.ForeignKey('subcategorie.id'), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    affiliate_url = db.Column(db.String(255), nullable=True)
    prijs = db.Column(db.String(50), nullable=True)
    contractduur = db.Column(db.String(20), nullable=True)
    aanbiedingen = db.Column(db.String(200), nullable=True)
    annuleringsvoorwaarden = db.Column(db.Text, nullable=True)
    voordelen = db.Column(db.Text, nullable=True)
    beoordelingen = db.Column(db.Float, nullable=True)
    volgorde = db.Column(db.Integer, nullable=False, default=0)

    # SEO
    slug = db.Column(db.String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint('slug', name='uq_abonnement_slug'),
    )

    # Nieuwe velden
    frequentie_bezorging = db.Column(db.String(50), nullable=True)
    prijs_vanaf = db.Column(db.Float, nullable=True)
    prijs_tot = db.Column(db.Float, nullable=True)
    wat_is_het_abonnement = db.Column(db.Text, nullable=True)
    waarom_kiezen = db.Column(db.Text, nullable=True)
    hoe_werkt_het = db.Column(db.Text, nullable=True)
    past_dit_bij_jou = db.Column(db.Text, nullable=True)

    # Nieuwe velden voor media
    youtube_url = db.Column(db.String(255), nullable=True)  # 🔹 Standaard YouTube-link
    fotos = db.relationship('AbonnementFoto', back_populates='abonnement', cascade="all, delete-orphan")

    # Relaties
    doelgroepen = db.relationship('Doelgroep', secondary='abonnement_doelgroep', back_populates='abonnementen')
    tags = db.relationship('Tag', secondary='abonnement_tag', back_populates='abonnementen')
    reviews = db.relationship("Review", back_populates="abonnement", lazy=True)
    bedrijf = db.relationship('Bedrijf', back_populates='abonnementen')

    def get_average_score(self):
        """Bereken het gemiddelde van alle reviews voor dit abonnement."""
        if not self.reviews:
            return 0.0
        total = sum(review.score for review in self.reviews)
        return round(total / len(self.reviews), 1)


class AbonnementFoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False)
    bestandsnaam = db.Column(db.String(255), nullable=False)

    abonnement = db.relationship('Abonnement', back_populates='fotos')

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    inhoud = db.Column(db.Text, nullable=False)
    afbeelding = db.Column(db.String(255), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)
    datum = db.Column(db.DateTime, default=db.func.now())
    auteur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    auteur = db.relationship('User', backref='blogposts')

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
@app.route('/')
def index():
    zoekterm = request.args.get('zoekterm', '').strip()
    geselecteerde_categorie = request.args.get('categorie', '').strip()
    geselecteerde_subcategorie = request.args.get('subcategorie', '').strip()

    # 🔁 Redirect op basis van categorie- en/of subcategorie-ID
    if geselecteerde_categorie:
        categorie = Categorie.query.get(int(geselecteerde_categorie))
        if not categorie:
            abort(404)

        if geselecteerde_subcategorie:
            subcategorie = Subcategorie.query.get(int(geselecteerde_subcategorie))
            if not subcategorie or subcategorie.categorie_id != categorie.id:
                abort(404)

            return redirect(
                url_for('abonnement_overzicht', categorie_slug=categorie.slug, subcategorie_slug=subcategorie.slug),
                code=301
            )
        else:
            return redirect(
                url_for('abonnement_overzicht', categorie_slug=categorie.slug),
                code=301
            )

    # 🔍 Zoekfunctionaliteit blijft op de homepage werken
    abonnementen_query = Abonnement.query.join(
        Subcategorie, Abonnement.subcategorie_id == Subcategorie.id
    ).join(
        Categorie, Subcategorie.categorie_id == Categorie.id
    ).options(
        db.contains_eager(Abonnement.subcategorie).contains_eager(Subcategorie.categorie)
    )

    if zoekterm:
        abonnementen_query = abonnementen_query.filter(Abonnement.naam.ilike(f'%{zoekterm}%'))

    abonnementen = abonnementen_query.order_by(Abonnement.volgorde.asc()).all()

    # Dynamisch de juiste categorieën ophalen
    if zoekterm:
        categorieën = list(set([ab.subcategorie.categorie for ab in abonnementen]))
        subcategorieën = list(set([ab.subcategorie for ab in abonnementen]))
    else:
        categorieën = Categorie.query.order_by(Categorie.volgorde.asc()).all()
        subcategorieën = Subcategorie.query.all()

    # Opbouw voor template: abonnementen per categorie
    abonnementen_per_categorie = {}
    for categorie in categorieën:
        abonnementen_per_categorie[categorie.id] = [
            ab for ab in abonnementen if ab.subcategorie and ab.subcategorie.categorie.id == categorie.id
        ]

    return render_template(
        'index.html',
        abonnementen=abonnementen,
        abonnementen_per_categorie=abonnementen_per_categorie,
        unieke_categorieën=categorieën,
        unieke_subcategorieën=subcategorieën,
        geselecteerde_categorie='',
        geselecteerde_subcategorie='',
        zoekterm=zoekterm
    )

@app.route('/categorie/<categorie_slug>/')
@app.route('/categorie/<categorie_slug>/<subcategorie_slug>/')
def abonnement_overzicht(categorie_slug, subcategorie_slug=None):
    # Zoek categorie op slug
    categorie = Categorie.query.filter_by(slug=categorie_slug).first_or_404()
    subcategorie = None

    # Zoek subcategorie op slug (indien meegegeven)
    if subcategorie_slug:
        subcategorie = Subcategorie.query.filter_by(slug=subcategorie_slug, categorie_id=categorie.id).first_or_404()

    # Filter op categorie of subcategorie
    query = Abonnement.query.join(Subcategorie).filter(Subcategorie.categorie_id == categorie.id)
    if subcategorie:
        query = query.filter(Subcategorie.id == subcategorie.id)

    abonnementen = query.order_by(Abonnement.volgorde.asc()).all()
    categorieen = Categorie.query.order_by(Categorie.volgorde.asc()).all()
    subcategorieen = Subcategorie.query.filter_by(categorie_id=categorie.id).all()

    # SEO-titel & beschrijving dynamisch bepalen
    if subcategorie:
        page_title = f"{subcategorie.naam} abonnementen vergelijken | {categorie.naam} | AbboHub"
        page_description = f"Bekijk en vergelijk eenvoudig {subcategorie.naam}-abonnementen binnen de categorie {categorie.naam} op AbboHub."
    else:
        page_title = f"Abonnementen in {categorie.naam} vergelijken | AbboHub"
        page_description = f"Ontdek alle abonnementen binnen de categorie {categorie.naam} en vergelijk eenvoudig prijzen en voordelen."

    return render_template(
        'index.html',
        abonnementen=abonnementen,
        abonnementen_per_categorie={categorie.id: abonnementen},
        unieke_categorieën=categorieen,
        unieke_subcategorieën=subcategorieen,
        geselecteerde_categorie=str(categorie.id),
        geselecteerde_subcategorie=str(subcategorie.id) if subcategorie else '',
        zoekterm='',
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
    """
    Toon de reviews van een specifiek abonnement en bied een formulier aan om een review toe te voegen.
    Beheerders kunnen reviews modereren (verwijderen).
    """
    abonnement = Abonnement.query.filter_by(slug=slug).first_or_404()
    is_admin = current_user.is_authenticated and current_user.is_admin

    if request.method == 'POST':
        # Admin actie: review verwijderen
        if is_admin and 'delete_review_id' in request.form:
            review_id = request.form.get('delete_review_id')
            review = Review.query.get(review_id)
            if review:
                db.session.delete(review)
                db.session.commit()
                flash("Review succesvol verwijderd.", "success")
            else:
                flash("Review niet gevonden.", "danger")
            return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

        # Gebruikeractie: nieuwe review toevoegen
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

        if score < 1 or score > 5:
            flash("Score moet tussen 1 en 5 liggen!", "danger")
            return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

        new_review = Review(abonnement_id=abonnement.id, naam=naam, score=score, comment=comment)
        db.session.add(new_review)
        db.session.commit()

        flash("Bedankt voor je review!", "success")
        return redirect(url_for('abonnement_reviews', slug=abonnement.slug))

    # Gemiddelde score berekenen
    reviews = abonnement.reviews
    scores = [review.score for review in reviews]
    gemiddelde_score = round(sum(scores) / len(scores), 1) if scores else None

    # SEO
    page_title = f"{abonnement.naam} abonnement review & ervaringen | AbboHub"
    page_description = f"Lees gebruikerservaringen en ontdek wat {abonnement.naam} jou te bieden heeft. Vergelijk nu prijzen, voordelen en meer."

    # Andere abonnementen in dezelfde subcategorie (voor vergelijkingssidebar)
    andere_abonnementen = Abonnement.query.filter(
        Abonnement.subcategorie_id == abonnement.subcategorie_id,
        Abonnement.id != abonnement.id
    ).order_by(Abonnement.volgorde.asc()).all()

    return render_template(
        'abonnement_reviews.html',
        abonnement=abonnement,
        is_admin=is_admin,
        gemiddelde_score=gemiddelde_score,
        andere_abonnementen=andere_abonnementen,
        page_title=page_title,
        page_description=page_description
    )

@app.route('/blog', strict_slashes=False)
@app.route('/blog/', strict_slashes=False)
def blog_overzicht():
    posts = BlogPost.query.order_by(BlogPost.datum.desc()).all()
    return render_template('blog_overzicht.html', posts=posts)

@app.route('/blog/<slug>', strict_slashes=False)
@app.route('/blog/<slug>/', strict_slashes=False)
def blog_detail(slug):
    post = BlogPost.query.filter_by(slug=slug).first_or_404()
    return render_template('blog_detail.html', post=post)


@app.route('/user_dashboard')
@login_required
def user_dashboard():
    """Voorbeeld van een user-dashboard, na inloggen."""
    # In een echte app zou je hier user-specifieke data tonen
    return render_template('user_dashboard.html')

# ---------------------------------------
# Routes: Admin
# ---------------------------------------
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Je hebt geen toegang tot deze pagina.", "danger")
        return redirect(url_for('index'))

    # Laad abonnementen met gerelateerde subcategorieën en categorieën
    abonnementen = Abonnement.query.options(
        joinedload(Abonnement.subcategorie).joinedload(Subcategorie.categorie)
    ).all()
    
    # Laad alle categorieën
    categorieen = Categorie.query.all()

    # Geef zowel 'abonnementen' als 'categorieen' door aan de template
    return render_template('admin_dashboard.html',
                           abonnementen=abonnementen,
                           categorieen=categorieen)
@app.route('/update_abonnementen_volgorde', methods=['POST'])
@login_required
def update_abonnementen_volgorde():
    if not current_user.is_admin:
        return jsonify({'error': 'Geen toegang'}), 403

    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': 'Ongeldige data'}), 400

    for index, abonnement_id in enumerate(data['order']):
        abonnement = Abonnement.query.get(abonnement_id)
        if abonnement:
            abonnement.volgorde = index + 1
    db.session.commit()

    return jsonify({'success': True})
    
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_subscription():
    """Pagina voor abonnementen toevoegen (met provider/bedrijf, doelgroepen, tags, extra informatie, foto's en video)."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 1) Basisvelden
        naam                  = request.form.get('naam', '').strip()
        beschrijving          = request.form.get('beschrijving', '').strip()
        filter_optie          = request.form.get('filter_optie', '').strip()
        prijs                 = request.form.get('prijs', '').strip()
        contractduur          = request.form.get('contractduur', '').strip()
        aanbiedingen          = request.form.get('aanbiedingen', '').strip()
        annuleringsvoorwaarden= request.form.get('annuleringsvoorwaarden', '').strip()
        voordelen             = request.form.get('voordelen', '').strip()
        beoordelingen         = request.form.get('beoordelingen', '').strip()
        url                   = request.form.get('url', '').strip()
        affiliate_url = request.form.get('affiliate_url', '').strip()
        subcategorie_id       = request.form.get('subcategorie_id')

        # 2) Extra velden
        bedrijf_naam          = request.form.get('bedrijf_naam', '').strip()
        frequentie_bezorging  = request.form.get('frequentie_bezorging', '').strip()
        prijs_vanaf           = request.form.get('prijs_vanaf', '').strip()
        prijs_tot             = request.form.get('prijs_tot', '').strip()
        wat_is_het_abonnement = request.form.get('wat_is_het_abonnement', '').strip()
        waarom_kiezen         = request.form.get('waarom_kiezen', '').strip()
        hoe_werkt_het         = request.form.get('hoe_werkt_het', '').strip()
        past_dit_bij_jou      = request.form.get('past_dit_bij_jou', '').strip()
        youtube_url           = request.form.get('youtube_url', '').strip()  # 🔹 Nieuw veld

        geselecteerde_doelgroepen = request.form.getlist('doelgroepen')
        geselecteerde_tags        = request.form.getlist('tags')

        # 3) Validatie
        if not (naam and filter_optie and subcategorie_id and url and bedrijf_naam):
            flash("Vul alle verplichte velden in!", "danger")
            return redirect(url_for('add_subscription'))
        if not url.startswith(('http://', 'https://')):
            flash("De URL moet beginnen met http:// of https://.", "danger")
            return redirect(url_for('add_subscription'))

        # 4) Slug genereren
        subcat = Subcategorie.query.get(int(subcategorie_id))
        cat    = Categorie.query.get(subcat.categorie_id) if subcat else None
        categorie_slug    = slugify(cat.naam) if cat else "categorie"
        subcategorie_slug = slugify(subcat.naam) if subcat else "subcategorie"
        naam_slug         = slugify(naam)
        full_slug         = f"{categorie_slug}/{subcategorie_slug}/{naam_slug}"
        if Abonnement.query.filter_by(slug=full_slug).first():
            flash("Er bestaat al een abonnement met deze naam in dezelfde categorie/subcategorie.", "danger")
            return redirect(url_for('add_subscription'))

        # 5) Logo upload & verwerking
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

        # 6) Provider / Bedrijf aanmaken of ophalen
        bedrijf = Bedrijf.query.filter_by(naam=bedrijf_naam).first()
        if not bedrijf:
            bedrijf = Bedrijf(naam=bedrijf_naam)
            db.session.add(bedrijf)
            db.session.flush()

        # 7) Nieuwe Abonnement-instance
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
            beoordelingen=float(beoordelingen) if beoordelingen else 0.0,
            url=url,
            affiliate_url=affiliate_url if affiliate_url else None,
            subcategorie_id=int(subcategorie_id),
            logo=logo_filename,
            frequentie_bezorging=frequentie_bezorging,
            prijs_vanaf=float(prijs_vanaf) if prijs_vanaf else None,
            prijs_tot=float(prijs_tot) if prijs_tot else None,
            wat_is_het_abonnement=wat_is_het_abonnement,
            waarom_kiezen=waarom_kiezen,
            hoe_werkt_het=hoe_werkt_het,
            past_dit_bij_jou=past_dit_bij_jou,
            youtube_url=youtube_url,  # 🔹 Nieuw veld
            bedrijf_id=bedrijf.id
        )

        db.session.add(new_abonnement)
        db.session.flush()  # Abonnement-ID beschikbaar voor foto's

        # 8) Productfoto's verwerken (max 10)
        foto_bestanden = request.files.getlist('product_fotos')
        for foto in foto_bestanden[:10]:
            if foto and allowed_file(foto.filename):
                foto_filename = secure_filename(foto.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                foto_path = os.path.join(upload_folder, foto_filename)
                foto.save(foto_path)

                nieuwe_foto = AbonnementFoto(
                    abonnement_id=new_abonnement.id,
                    bestandsnaam=foto_filename
                )
                db.session.add(nieuwe_foto)

        # 9) Relaties Doelgroepen & Tags
        for dg_id in geselecteerde_doelgroepen:
            dg = Doelgroep.query.get(int(dg_id))
            if dg:
                new_abonnement.doelgroepen.append(dg)
        for tag_id in geselecteerde_tags:
            tg = Tag.query.get(int(tag_id))
            if tg:
                new_abonnement.tags.append(tg)

        # 10) Opslaan & redirect
        db.session.commit()
        flash("Abonnement succesvol toegevoegd!", "success")
        return redirect(url_for('admin_dashboard'))

    # GET: toon het formulier
    bedrijven      = Bedrijf.query.order_by(Bedrijf.naam).all()
    categorieen    = Categorie.query.all()
    subcategorieen = Subcategorie.query.all()
    doelgroepen    = Doelgroep.query.all()
    tags           = Tag.query.all()
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
    """Beheer van abonnementen bewerken (met subcategorie, doelgroepen, tags, bedrijven en extra velden)."""
    if not current_user.is_admin:
        return redirect(url_for('index'))

    abonnement = Abonnement.query.get_or_404(id)

    bedrijven      = Bedrijf.query.order_by(Bedrijf.naam).all()
    categorieen    = Categorie.query.all()
    subcategorieen = Subcategorie.query.filter_by(
        categorie_id=abonnement.subcategorie.categorie_id
    ).all()
    doelgroepen    = Doelgroep.query.all()
    tags           = Tag.query.all()

    if request.method == 'POST':
        # --- Algemene velden ---
        abonnement.naam = request.form.get('naam', '').strip()
        abonnement.beschrijving = request.form.get('beschrijving', '').strip()
        abonnement.filter_optie = request.form.get('filter_optie', '').strip()
        abonnement.prijs = request.form.get('prijs', '').strip()
        abonnement.contractduur = request.form.get('contractduur', '').strip()
        abonnement.aanbiedingen = request.form.get('aanbiedingen', '').strip()
        abonnement.annuleringsvoorwaarden = request.form.get('annuleringsvoorwaarden', '').strip()
        abonnement.voordelen = request.form.get('voordelen', '').strip()

        # --- Bedrijf ---
        bedrijf_id = request.form.get('bedrijf_id')
        abonnement.bedrijf_id = int(bedrijf_id) if bedrijf_id else None

        # --- Extra velden ---
        abonnement.frequentie_bezorging = request.form.get('frequentie_bezorging', '').strip()
        prijs_vanaf = request.form.get('prijs_vanaf', '').strip()
        abonnement.prijs_vanaf = float(prijs_vanaf) if prijs_vanaf else None
        prijs_tot = request.form.get('prijs_tot', '').strip()
        abonnement.prijs_tot = float(prijs_tot) if prijs_tot else None
        abonnement.wat_is_het_abonnement = request.form.get('wat_is_het_abonnement', '').strip()
        abonnement.waarom_kiezen = request.form.get('waarom_kiezen', '').strip()
        abonnement.hoe_werkt_het = request.form.get('hoe_werkt_het', '').strip()
        abonnement.past_dit_bij_jou = request.form.get('past_dit_bij_jou', '').strip()

        # --- Nieuw: YouTube-link ---
        abonnement.youtube_url = request.form.get('youtube_url', '').strip()

        # --- Beoordelingen ---
        beoordelingen = request.form.get('beoordelingen', '').strip()
        if beoordelingen:
            try:
                abonnement.beoordelingen = float(beoordelingen)
            except ValueError:
                flash("Beoordelingen moet een numerieke waarde zijn!", "danger")
                return redirect(url_for('edit_subscription', id=abonnement.id))

        # --- URL & Subcategorie ---
        abonnement.url = request.form.get('url', '').strip()
        abonnement.affiliate_url = request.form.get('affiliate_url', '').strip() or None
        abonnement.subcategorie_id = int(request.form.get('subcategorie_id'))

        # --- Slug her-genereren ---
        subcat = Subcategorie.query.get(abonnement.subcategorie_id)
        cat = Categorie.query.get(subcat.categorie_id) if subcat else None
        categorie_slug = slugify(cat.naam) if cat else "categorie"
        subcategorie_slug = slugify(subcat.naam) if subcat else "subcategorie"
        naam_slug = slugify(abonnement.naam)
        abonnement.slug = f"{categorie_slug}/{subcategorie_slug}/{naam_slug}"

        # --- Doelgroepen & Tags ---
        abonnement.doelgroepen = Doelgroep.query.filter(
            Doelgroep.id.in_(request.form.getlist('doelgroepen'))
        ).all()
        abonnement.tags = Tag.query.filter(
            Tag.id.in_(request.form.getlist('tags'))
        ).all()

        # --- Logo upload ---
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and allowed_file(logo_file.filename):
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

        # --- Nieuw: Foto’s uploaden ---
        foto_bestanden = request.files.getlist('product_fotos')
        for foto in foto_bestanden[:10]:
            if foto and allowed_file(foto.filename):
                filename = secure_filename(foto.filename)
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                foto.save(save_path)
                nieuwe_foto = AbonnementFoto(abonnement_id=abonnement.id, bestandsnaam=filename)
                db.session.add(nieuwe_foto)

        # --- Nieuw: Foto’s verwijderen ---
        delete_fotos_ids = request.form.getlist('delete_fotos')
        if delete_fotos_ids:
            fotos_to_delete = AbonnementFoto.query.filter(
                AbonnementFoto.id.in_(delete_fotos_ids)
            ).all()
            for foto in fotos_to_delete:
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], foto.bestandsnaam)
                if os.path.exists(file_path):
                    os.remove(file_path)
                db.session.delete(foto)

        db.session.commit()
        flash("Abonnement succesvol bijgewerkt!", 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template(
        'edit_subscription.html',
        abonnement=abonnement,
        bedrijven=bedrijven,
        categorieen=categorieen,
        subcategorieen=subcategorieen,
        doelgroepen=doelgroepen,
        tags=tags
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


@app.route('/admin/abonnementen', methods=['GET', 'POST'])
@login_required
def manage_subscriptions():
    """Overzicht van alle abonnementen met zoek- en filteropties (admin)."""
    if not current_user.is_admin:
        flash("Je hebt geen toegang tot deze pagina.", "danger")
        return redirect(url_for('index'))

    # Haal zoekterm en filters op
    zoekterm = request.args.get('zoekterm', '').strip()
    categorie_id = request.args.get('categorie_id', '').strip()

    query = Abonnement.query.join(Subcategorie).join(Categorie)

    if zoekterm:
        query = query.filter(Abonnement.naam.ilike(f'%{zoekterm}%'))

    # Filter enkel als categorie_id een getal is
    if categorie_id.isdigit():
        query = query.filter(Categorie.id == int(categorie_id))

    abonnementen = query.all()
    categorieen = Categorie.query.all()

    return render_template(
        'manage_subscriptions.html',
        abonnementen=abonnementen,
        categorieen=categorieen,
        zoekterm=zoekterm,
        geselecteerde_categorie=categorie_id
    )

@app.route('/admin/blog/nieuw', methods=['GET', 'POST'])
@login_required
def blog_toevoegen():
    if not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        titel = request.form['titel']
        inhoud = request.form['inhoud']
        video_url = request.form.get('video_url')
        afbeelding = request.files.get('afbeelding')
        slug = slugify(titel)

        bestandsnaam = None
        if afbeelding and allowed_file(afbeelding.filename):
            bestandsnaam = secure_filename(afbeelding.filename)
            pad = os.path.join(app.config['UPLOAD_FOLDER'], bestandsnaam)
            afbeelding.save(pad)

        nieuw = BlogPost(
            titel=titel,
            slug=slug,
            inhoud=inhoud,
            afbeelding=bestandsnaam,
            video_url=video_url,
            auteur=current_user
        )
        db.session.add(nieuw)
        db.session.commit()
        flash("Blogbericht geplaatst!", "success")
        return redirect(url_for('blog_overzicht'))

    return render_template('blog_formulier.html')

@app.route('/admin/blog')
@login_required
def admin_blog_overzicht():
    if not current_user.is_admin:
        abort(403)
    posts = BlogPost.query.order_by(BlogPost.datum.desc()).all()
    return render_template('admin_blog_overzicht.html', posts=posts)
@app.route('/admin/blog/bewerk/<int:post_id>', methods=['GET', 'POST'])
@login_required
def blog_bewerken(post_id):
    if not current_user.is_admin:
        abort(403)
    post = BlogPost.query.get_or_404(post_id)

    if request.method == 'POST':
        post.titel = request.form['titel']
        post.inhoud = request.form['inhoud']
        post.video_url = request.form['video_url']

        afbeelding = request.files.get('afbeelding')
        if afbeelding and allowed_file(afbeelding.filename):
            filename = secure_filename(afbeelding.filename)
            pad = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            afbeelding.save(pad)
            post.afbeelding = filename

        db.session.commit()
        flash("Blog bijgewerkt", "success")
        return redirect(url_for('admin_blog_overzicht'))

    return render_template('blog_formulier.html', post=post)

@app.route('/admin/blog/verwijder/<int:post_id>', methods=['POST'])
@login_required
def blog_verwijderen(post_id):
    if not current_user.is_admin:
        abort(403)
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Blog verwijderd", "success")
    return redirect(url_for('admin_blog_overzicht'))


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
with app.app_context():
    db.create_all()

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
