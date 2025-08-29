# 1. Bedrijfsinformatie
class Bedrijf(db.Model):
    __tablename__ = 'bedrijf'
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(150), nullable=False, unique=True)
    website_url = db.Column(db.String(255), nullable=False)
    logo = db.Column(db.String(200), nullable=True)
    contact_email = db.Column(db.String(120), nullable=True)
    telefoon = db.Column(db.String(50), nullable=True)
    kvk_nummer = db.Column(db.String(50), nullable=True)
    abonnementen = db.relationship('Abonnement', back_populates='bedrijf')

# 2. Algemene abonnementsinformatie + plannen + prijzen
class Abonnement(db.Model):
    __tablename__ = 'abonnement'
    id = db.Column(db.Integer, primary_key=True)
    bedrijf_id = db.Column(db.Integer, db.ForeignKey('bedrijf.id'), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    naam = db.Column(db.String(150), nullable=False)
    beschrijving_kort = db.Column(db.String(140), nullable=True)
    prijs_vanaf = db.Column(db.Numeric(10,2), nullable=True)
    prijs_tot = db.Column(db.Numeric(10,2), nullable=True)
    contractduur_maanden = db.Column(db.Integer, nullable=True)
    frequentie_bezorging = db.Column(db.Enum('wekelijks','2-wekelijks','maandelijks','kwartaal','jaarlijks', name='freq_enum'), nullable=True)
    gemiddelde_score = db.Column(db.Float, nullable=True)
    aantal_reviews = db.Column(db.Integer, nullable=True)

    bedrijf = db.relationship('Bedrijf', back_populates='abonnementen')
    beschrijvingen = db.relationship('AbonnementBeschrijving', back_populates='abonnement', uselist=False)
    plannen = db.relationship('AbonnementPlan', back_populates='abonnement')
    categorie_filters = db.relationship('AbonnementCategorieFilter', back_populates='abonnement')
    subcategorie_filters = db.relationship('AbonnementSubcategorieFilter', back_populates='abonnement')
    reviews = db.relationship('Review', back_populates='abonnement')

class AbonnementPlan(db.Model):
    __tablename__ = 'abonnement_plan'
    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False)
    naam = db.Column(db.String(100), nullable=False)
    beschrijving = db.Column(db.Text, nullable=True)
    prijs_standaard = db.Column(db.Numeric(10,2), nullable=True)
    contract_maanden = db.Column(db.Integer, nullable=True)
    trial_dagen = db.Column(db.Integer, nullable=True)
    pauze_max_weken = db.Column(db.Integer, nullable=True)

    abonnement = db.relationship('Abonnement', back_populates='plannen')
    prijzen = db.relationship('Prijs', back_populates='plan')
    features = db.relationship('AbonnementPlanFeature', back_populates='plan')

class Prijs(db.Model):
    __tablename__ = 'prijs'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('abonnement_plan.id'), nullable=False)
    bedrag = db.Column(db.Numeric(10,2), nullable=False)
    valuta = db.Column(db.String(3), nullable=False, default='EUR')
    start_datum = db.Column(db.Date, nullable=False, default=date.today)
    eind_datum = db.Column(db.Date, nullable=True)
    type = db.Column(db.Enum('standaard','actie','trial', name='prijs_type'), nullable=False, default='standaard')

    plan = db.relationship('AbonnementPlan', back_populates='prijzen')

# 3. Tekstuele beschrijvingen
class AbonnementBeschrijving(db.Model):
    __tablename__ = 'abonnement_beschrijving'
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), primary_key=True)
    wat_is_het_abonnement = db.Column(db.Text, nullable=True)
    waarom_kiezen = db.Column(db.Text, nullable=True)
    hoe_werkt_het = db.Column(db.Text, nullable=True)
    past_dit_bij_jou = db.Column(db.Text, nullable=True)
    voordelen = db.Column(db.Text, nullable=True)
    annuleringsvoorwaarden = db.Column(db.Text, nullable=True)

    abonnement = db.relationship('Abonnement', back_populates='beschrijvingen')

# 4. Categorie‐filters
types = ('number','boolean','enum','text')
class CategorieFilter(db.Model):
    __tablename__ = 'categorie_filter'
    id = db.Column(db.Integer, primary_key=True)
    categorie_id = db.Column(db.Integer, db.ForeignKey('categorie.id'), nullable=False)
    naam = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(*types, name='filter_type'), nullable=False)
    opties = db.Column(db.JSON, nullable=True)

    categorie = db.relationship('Categorie')
    abonnement_filters = db.relationship('AbonnementCategorieFilter', back_populates='filter')

class AbonnementCategorieFilter(db.Model):
    __tablename__ = 'abonnement_categorie_filter'
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), primary_key=True)
    filter_id = db.Column(db.Integer, db.ForeignKey('categorie_filter.id'), primary_key=True)
    waarde = db.Column(db.String(100), nullable=True)

    abonnement = db.relationship('Abonnement', back_populates='categorie_filters')
    filter = db.relationship('CategorieFilter', back_populates='abonnement_filters')

# 5. Subcategorie‐filters
class SubcategorieFilter(db.Model):
    __tablename__ = 'subcategorie_filter'
    id = db.Column(db.Integer, primary_key=True)
    subcategorie_id = db.Column(db.Integer, db.ForeignKey('subcategorie.id'), nullable=False)
    naam = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(*types, name='subfilter_type'), nullable=False)
    opties = db.Column(db.JSON, nullable=True)

    subcategorie = db.relationship('Subcategorie')
    abonnement_filters = db.relationship('AbonnementSubcategorieFilter', back_populates='filter')

class AbonnementSubcategorieFilter(db.Model):
    __tablename__ = 'abonnement_subcategorie_filter'
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), primary_key=True)
    filter_id = db.Column(db.Integer, db.ForeignKey('subcategorie_filter.id'), primary_key=True)
    waarde = db.Column(db.String(100), nullable=True)

    abonnement = db.relationship('Abonnement', back_populates='subcategorie_filters')
    filter = db.relationship('SubcategorieFilter', back_populates='abonnement_filters')

# 6. Features & voorraad
class Feature(db.Model):
    __tablename__ = 'feature'
    id = db.Column(db.Integer, primary_key=True)
    naam = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Enum(*types, name='feature_type'), nullable=False)
    eenheid = db.Column(db.String(50), nullable=True)
    plan_features = db.relationship('AbonnementPlanFeature', back_populates='feature')

class AbonnementPlanFeature(db.Model):
    __tablename__ = 'abonnement_plan_feature'
    plan_id = db.Column(db.Integer, db.ForeignKey('abonnement_plan.id'), primary_key=True)
    feature_id = db.Column(db.Integer, db.ForeignKey('feature.id'), primary_key=True)
    hoeveelheid = db.Column(db.Float, nullable=True)

    plan = db.relationship('AbonnementPlan', back_populates='features')
    feature = db.relationship('Feature', back_populates='plan_features')

class Voorraad(db.Model):
    __tablename__ = 'voorraad'
    product_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), primary_key=True)
    regio = db.Column(db.String(100), primary_key=True)
    hoeveelheid = db.Column(db.Integer, nullable=False)
    leverdatum_min = db.Column(db.Date, nullable=True)
    leverdatum_max = db.Column(db.Date, nullable=True)

# 7. Reviews & lifecycle
class Review(db.Model):
    __tablename__ = 'review'
    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False)
    naam = db.Column(db.String(255), nullable=False)
    score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    verified_purchase = db.Column(db.Boolean, default=False)

    abonnement = db.relationship('Abonnement', back_populates='reviews')

class SubscriptionLifecycle(db.Model):
    __tablename__ = 'subscription_lifecycle'
    id = db.Column(db.Integer, primary_key=True)
    abonnement_id = db.Column(db.Integer, db.ForeignKey('abonnement.id'), nullable=False)
    status = db.Column(db.Enum('actief','gepauzeerd','opgezegd','hersteld', name='lifecycle_status'), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())

    abonnement = db.relationship('Abonnement')