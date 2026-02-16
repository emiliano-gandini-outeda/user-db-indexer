from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from typing import List
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

@app.get("/")
def serve_spa():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DB_PATH = os.path.join(BASE_DIR, "usuarios.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



@app.get("/users", response_model=List[dict])
def get_all_users(limit: int = Query(50000, ge=1, le=50000)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, apellido FROM usuarios LIMIT ?", (limit,))
    users = cursor.fetchall()
    conn.close()

    return [
        {"id": str(user["id"]), "nombre": user["nombre"], "apellido": user["apellido"]}
        for user in users
    ]


@app.get("/api/search", response_model=List[dict])
def search_users(
    q: str = Query("", description="Búsqueda general"),
    limit: int = Query(50000, ge=1, le=50000),
):
    conn = get_db_connection()
    cursor = conn.cursor()

    if q.strip():
        q_val = q.strip()

        if q_val.isdigit():
            cursor.execute(
                "SELECT id, nombre, apellido FROM usuarios WHERE id = ? LIMIT ?",
                (int(q_val), limit),
            )
        else:
            pattern = f"%{q_val}%"
            cursor.execute(
                "SELECT id, nombre, apellido FROM usuarios WHERE nombre LIKE ? OR apellido LIKE ? LIMIT ?",
                (pattern, pattern, limit),
            )
    else:
        cursor.execute("SELECT id, nombre, apellido FROM usuarios LIMIT ?", (limit,))

    users = cursor.fetchall()
    conn.close()

    return [
        {"id": str(user["id"]), "nombre": user["nombre"], "apellido": user["apellido"]}
        for user in users
    ]


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
