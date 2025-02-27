from app import app, db

# Maak de database aan
with app.app_context():
    db.create_all()
