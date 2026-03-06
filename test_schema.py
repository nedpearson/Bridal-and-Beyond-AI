import sqlite3
import pprint

conn = sqlite3.connect('C:/Users/nedpe/.gemini/antigravity/scratch/Bridal-and-Beyond-AI/app/bridal_beyond.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(pickups)")
pprint.pprint(cursor.fetchall())
