from app import app, db

# Open een applicatiecontext
with app.app_context():
    # Verwijder de tijdelijke tabel
    with db.engine.connect() as connection:
        connection.execute("DROP TABLE IF EXISTS _alembic_tmp_abonnement")
    print("Tabel _alembic_tmp_abonnement verwijderd.")
