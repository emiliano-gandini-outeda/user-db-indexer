import csv
import sqlite3
import os
from pathlib import Path

DB_PATH = "usuarios.db"
IDS_DIR = "ids"
INDEX_FILE = "search_index.pkl"


def create_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Base de datos eliminada: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nombre ON usuarios(nombre)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_apellido ON usuarios(apellido)")

    conn.commit()
    return conn


def parse_csv_value(value):
    return value.strip().strip('"')


def get_total_lines():
    total = 0
    for f in Path(IDS_DIR).glob("*.csv"):
        with open(f) as file:
            total += sum(1 for _ in file)
    return total


def import_csv_files(conn):
    cursor = conn.cursor()

    ids_dir = Path(IDS_DIR)
    csv_files = sorted(ids_dir.glob("*.csv"))

    total_imported = 0
    total_lines = get_total_lines()

    for csv_file in csv_files:
        print(f"Importando {csv_file.name}...")

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)

            batch = []
            for row in reader:
                if len(row) >= 3:
                    try:
                        user_id = int(parse_csv_value(row[0]))
                        nombre = parse_csv_value(row[1])
                        apellido = parse_csv_value(row[2])
                        batch.append((user_id, nombre, apellido))
                    except ValueError:
                        continue

                    if len(batch) >= 1000:
                        cursor.executemany(
                            "INSERT OR REPLACE INTO usuarios (id, nombre, apellido) VALUES (?, ?, ?)",
                            batch,
                        )
                        conn.commit()
                        total_imported += len(batch)
                        pct = int((total_imported / total_lines) * 50)
                        print(f"  [{pct}%] {total_imported:,} registros...")
                        batch = []

            if batch:
                cursor.executemany(
                    "INSERT OR REPLACE INTO usuarios (id, nombre, apellido) VALUES (?, ?, ?)",
                    batch,
                )
                conn.commit()
                total_imported += len(batch)

    return total_imported, total_lines


def build_and_save_index(conn):
    import minsearch

    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, apellido FROM usuarios")
    users = cursor.fetchall()
    total = len(users)
    print(f"Construyendo índice ({total:,} usuarios)...")

    docs = []
    for i, row in enumerate(users):
        docs.append({"id": str(row[0]), "nombre": row[1], "apellido": row[2]})
        if (i + 1) % 500000 == 0:
            pct = 50 + int(((i + 1) / total) * 50)
            print(f"  [{pct}%] Indexando...")

    print("  [75%] Creando índice minsearch...")
    INDEX = minsearch.Index(text_fields=["nombre", "apellido"], keyword_fields=["id"])
    INDEX.fit(docs)

    print("  [90%] Guardando índice...")
    import pickle

    with open(INDEX_FILE, "wb") as f:
        pickle.dump(INDEX, f)

    print(f"  [100%] Índice guardado en {INDEX_FILE}")
    return total


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = create_database()
    print("Base de datos creada")

    imported, total_lines = import_csv_files(conn)

    build_and_save_index(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    total_db = cursor.fetchone()[0]

    print(f"\nTotal registros: {total_db:,}")

    cursor.execute("SELECT id, nombre, apellido FROM usuarios LIMIT 5")
    print("\nEjemplos:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} {row[2]}")

    conn.close()
    print(f"\nCompletado!")


if __name__ == "__main__":
    main()
