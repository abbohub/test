import sqlite3

# Verbind met de SQLite database
conn = sqlite3.connect(r'C:\Users\timoo\OneDrive\Bureaublad\Abbo-test\abonnementen_website_test\instance\abonnementen.db')
cursor = conn.cursor()

# Query om de tabellen in de database op te halen
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

# Print alle tabellen
print("Tabellen in de database:")
for table in tables:
    print(table[0])

# Sluit de verbinding
conn.close()
