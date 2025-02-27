from flask_sqlalchemy import SQLAlchemy

# Initialiseer de database
db = SQLAlchemy()

# Definieer het User-model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

# Definieer het Log-model
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=db.func.now())
