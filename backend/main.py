from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from typing import List
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
import os
import jwt
from jwt import InvalidTokenError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import URLError, HTTPError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

app = FastAPI()

AUTH_REDIRECT_URL = os.getenv("UTILS_LOGIN_URL", "http://localhost:3002/login")
UTILS_VERIFY_URL = os.getenv("UTILS_VERIFY_URL", "http://localhost:3002/auth/verify")
INTERNAL_AUTH_SECRET = os.getenv("INTERNAL_AUTH_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")


def get_token(request: Request):
    token = request.cookies.get("ego_token")
    if token:
        return token

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth.replace("Bearer ", "", 1)

    return request.query_params.get("token")


def clean_path_without_token(request: Request):
    params = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key != "token"
    ]
    if not params:
        return request.url.path
    return f"{request.url.path}?{urlencode(params)}"


def is_token_active(token: str):
    if not UTILS_VERIFY_URL or not INTERNAL_AUTH_SECRET:
        return False

    req = UrlRequest(
        UTILS_VERIFY_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "x-internal-auth": INTERNAL_AUTH_SECRET,
        },
        method="GET",
    )

    try:
        with urlopen(req, timeout=2) as response:
            return response.status == 200
    except (URLError, HTTPError):
        return False


@app.middleware("http")
async def require_auth(request: Request, call_next):
    token = get_token(request)
    if not token:
        return RedirectResponse(AUTH_REDIRECT_URL, status_code=307)

    if not JWT_SECRET:
        return JSONResponse({"error": "JWT_SECRET is not configured"}, status_code=500)

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        request.state.user = {"username": payload.get("sub")}
    except InvalidTokenError:
        return RedirectResponse(AUTH_REDIRECT_URL, status_code=307)

    if not is_token_active(token):
        return RedirectResponse(AUTH_REDIRECT_URL, status_code=307)

    if request.query_params.get("token"):
        response = RedirectResponse(clean_path_without_token(request), status_code=307)
        response.set_cookie("ego_token", token, httponly=True, samesite="strict")
        return response

    return await call_next(request)


app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
    name="assets",
)


@app.get("/")
def serve_spa():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


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
