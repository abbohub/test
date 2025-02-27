from app import db
from models import Subcategorie

# Voeg standaard subcategorie toe
default_subcategorie = Subcategorie(naam='Standaard', categorie_id=1)  # Zorg dat categorie_id geldig is
db.session.add(default_subcategorie)
db.session.commit()

print("Standaard subcategorie toegevoegd.")
