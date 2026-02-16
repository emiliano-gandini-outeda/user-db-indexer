from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from typing import List
import pickle
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "usuarios.db")
INDEX_FILE = os.path.join(BASE_DIR, "search_index.pkl")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_index():
    if os.path.exists(INDEX_FILE):
        print(f"Cargando índice desde {INDEX_FILE}...")
        with open(INDEX_FILE, "rb") as f:
            return pickle.load(f)

    print("Índice no encontrado, cargando usuarios...")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, apellido FROM usuarios")
    users = cursor.fetchall()
    conn.close()

    docs = [
        {"id": str(row["id"]), "nombre": row["nombre"], "apellido": row["apellido"]}
        for row in users
    ]

    print(f"Construyendo índice con {len(docs)} documentos...")
    INDEX = minsearch.Index(text_fields=["nombre", "apellido"], keyword_fields=["id"])
    INDEX.fit(docs)
    return INDEX


INDEX = None
INDEX_READY = False
INDEX_PROGRESS = 0


@app.on_event("startup")
async def startup():
    global INDEX, INDEX_READY, INDEX_PROGRESS

    INDEX_PROGRESS = 10
    INDEX = load_index()
    INDEX_PROGRESS = 100
    INDEX_READY = True
    print("Índice listo")


@app.get("/")
def root():
    return {
        "message": "API de búsqueda de usuarios",
        "index_ready": INDEX_READY,
        "index_progress": INDEX_PROGRESS,
    }


@app.get("/search", response_model=List[dict])
def search(
    nombre: str = Query("", description="Buscar por nombre"),
    apellido: str = Query("", description="Buscar por apellido"),
    id: str = Query("", description="Buscar por ID"),
    limit: int = Query(20, ge=1, le=100),
):
    if not INDEX_READY:
        return {
            "error": "Índice aún cargando",
            "loading": True,
            "progress": INDEX_PROGRESS,
        }

    if id.strip():
        conn = get_db_connection()
        cursor = conn.cursor()

        # Try exact match first
        try:
            cursor.execute(
                "SELECT id, nombre, apellido FROM usuarios WHERE id = ?",
                (int(id.strip()),),
            )
            user = cursor.fetchone()
            if user:
                conn.close()
                return [
                    {
                        "id": user["id"],
                        "nombre": user["nombre"],
                        "apellido": user["apellido"],
                    }
                ]
        except ValueError:
            pass

        # Try partial match
        id_pattern = f"{id.strip()}%"
        cursor.execute(
            "SELECT id, nombre, apellido FROM usuarios WHERE CAST(id AS TEXT) LIKE ? LIMIT ?",
            (id_pattern, limit),
        )
        users = cursor.fetchall()
        conn.close()

        if users:
            return [
                {"id": u["id"], "nombre": u["nombre"], "apellido": u["apellido"]}
                for u in users
            ]
        return []

    # First: exact match (both nombre AND apellido match the query)
    exact_results = []
    if nombre.strip() and apellido.strip():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, nombre, apellido FROM usuarios WHERE LOWER(nombre) = LOWER(?) AND LOWER(apellido) LIKE LOWER(?) LIMIT ?",
            (nombre.strip(), f"%{apellido.strip()}%", limit),
        )
        exact_results = [
            {
                "id": u["id"],
                "nombre": u["nombre"],
                "apellido": u["apellido"],
                "_exact": True,
            }
            for u in cursor.fetchall()
        ]
        conn.close()

    # Second: fuzzy search with minisearch
    boost = {}
    query_parts = []

    if nombre.strip():
        query_parts.append(nombre.strip())
        boost["nombre"] = 10.0

    if apellido.strip():
        query_parts.append(apellido.strip())
        boost["apellido"] = 1.0

    if not query_parts:
        return exact_results[:limit]

    query_str = " ".join(query_parts)
    fuzzy_results = INDEX.search(query_str, boost_dict=boost, num_results=limit * 3)

    # Filter out exact matches from fuzzy results and add them with priority
    final_results = exact_results.copy()
    seen_ids = {r["id"] for r in exact_results}

    for r in fuzzy_results:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            final_results.append(r)

    return final_results[:limit]


@app.get("/user/{user_id}")
def get_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, apellido FROM usuarios WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {
            "id": user["id"],
            "nombre": user["nombre"],
            "apellido": user["apellido"],
        }
    return {"error": "Usuario no encontrado"}
