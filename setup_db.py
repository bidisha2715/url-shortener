import sqlite3

conn = sqlite3.connect("database.db")
conn.execute("DROP TABLE IF EXISTS urls")
conn.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY AUTOINCREMENT, original TEXT UNIQUE, short TEXT UNIQUE, clicks INTEGER DEFAULT 0)")
conn.commit()
conn.close()
print("Database table created successfully!")