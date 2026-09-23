from functools import wraps

from flask import Blueprint, jsonify, request, session
from psycopg.errors import UniqueViolation
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


auth = Blueprint("auth", __name__)


def _error(message, status):
    return jsonify({"error": message}), status


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None

    user = get_db().execute(
        "SELECT id, username, email FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()
    if user is None:
        session.clear()
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return _error("Authentication required", 401)
        return view(*args, **kwargs)

    return wrapped


@auth.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not username or not email or not isinstance(password, str):
        return _error("username, email, and password are required", 400)
    if len(username) > 50 or len(email) > 255:
        return _error("username or email is too long", 400)
    if len(password) < 8:
        return _error("password must be at least 8 characters", 400)

    try:
        user = get_db().execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id, username, email
            """,
            (username, email, generate_password_hash(password)),
        ).fetchone()
        get_db().commit()
    except UniqueViolation:
        get_db().rollback()
        return _error("username or email is already registered", 409)

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": dict(user)}), 201


@auth.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not username or not isinstance(password, str):
        return _error("username and password are required", 400)

    user = get_db().execute(
        "SELECT id, username, email, password_hash FROM users WHERE username = %s",
        (username,),
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return _error("invalid credentials", 401)

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": {"id": user["id"], "username": user["username"], "email": user["email"]}})


@auth.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "logged out"})