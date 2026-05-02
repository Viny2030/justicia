import sqlite3

conn = sqlite3.connect('justicia_local.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tablas = cursor.fetchall()

for tabla in tablas:
    nombre = tabla[0]
    print(f"\n=== {nombre} ===")
    cursor2 = conn.cursor()
    cursor2.execute(f"PRAGMA table_info({nombre})")
    for col in cursor2.fetchall():
        print(f"  {col[1]} ({col[2]})")

conn.close()