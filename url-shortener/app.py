"""URL Shortening Service for DGX Spark local deployment."""

import hashlib
import os
import sqlite3
import string
import time
from contextlib import contextmanager
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, redirect, request

app = Flask(__name__)

DATABASE = os.environ.get("URL_SHORTENER_DB", "urls.db")
BASE_URL = os.environ.get("URL_SHORTENER_BASE_URL", "http://localhost:5000")
SHORT_CODE_LENGTH = int(os.environ.get("URL_SHORTENER_CODE_LENGTH", "6"))

ALPHABET = string.ascii_letters + string.digits


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at REAL NOT NULL,
                click_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_short_code ON urls(short_code)
        """)


def generate_short_code(url: str) -> str:
    """Generate a short code from URL using hash-based approach."""
    hash_input = f"{url}{time.time()}".encode()
    hash_hex = hashlib.sha256(hash_input).hexdigest()
    code = ""
    num = int(hash_hex[:12], 16)
    for _ in range(SHORT_CODE_LENGTH):
        code += ALPHABET[num % len(ALPHABET)]
        num //= len(ALPHABET)
    return code


def is_valid_url(url: str) -> bool:
    """Validate that the given string is a proper URL."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


@app.route("/", methods=["GET"])
def index():
    """Simple landing page."""
    return jsonify({
        "service": "URL Shortener",
        "version": "1.0.0",
        "endpoints": {
            "POST /shorten": "Create a short URL",
            "GET /<code>": "Redirect to original URL",
            "GET /stats/<code>": "Get URL statistics",
            "GET /api/urls": "List all URLs",
        }
    })


@app.route("/shorten", methods=["POST"])
def shorten():
    """Create a shortened URL."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' field"}), 400

    original_url = data["url"].strip()
    if not is_valid_url(original_url):
        return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400

    custom_code = data.get("custom_code", "").strip()

    with get_db() as conn:
        # Check if URL already shortened
        existing = conn.execute(
            "SELECT short_code FROM urls WHERE original_url = ?", (original_url,)
        ).fetchone()
        if existing and not custom_code:
            short_code = existing["short_code"]
            return jsonify({
                "short_url": f"{BASE_URL}/{short_code}",
                "short_code": short_code,
                "original_url": original_url,
                "existing": True,
            })

        if custom_code:
            if len(custom_code) < 2 or len(custom_code) > 20:
                return jsonify({"error": "Custom code must be 2-20 characters"}), 400
            if not all(c in ALPHABET + "-_" for c in custom_code):
                return jsonify({"error": "Custom code can only contain letters, digits, hyphens, underscores"}), 400
            conflict = conn.execute(
                "SELECT id FROM urls WHERE short_code = ?", (custom_code,)
            ).fetchone()
            if conflict:
                return jsonify({"error": "Custom code already in use"}), 409
            short_code = custom_code
        else:
            short_code = generate_short_code(original_url)
            # Handle collision
            while conn.execute("SELECT id FROM urls WHERE short_code = ?", (short_code,)).fetchone():
                short_code = generate_short_code(original_url)

        conn.execute(
            "INSERT INTO urls (short_code, original_url, created_at) VALUES (?, ?, ?)",
            (short_code, original_url, time.time()),
        )

    return jsonify({
        "short_url": f"{BASE_URL}/{short_code}",
        "short_code": short_code,
        "original_url": original_url,
    }), 201


@app.route("/stats/<code>", methods=["GET"])
def stats(code):
    """Get statistics for a shortened URL."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT short_code, original_url, created_at, click_count FROM urls WHERE short_code = ?",
            (code,),
        ).fetchone()
    if not row:
        return jsonify({"error": "Short URL not found"}), 404
    return jsonify({
        "short_code": row["short_code"],
        "short_url": f"{BASE_URL}/{row['short_code']}",
        "original_url": row["original_url"],
        "created_at": row["created_at"],
        "click_count": row["click_count"],
    })


@app.route("/api/urls", methods=["GET"])
def list_urls():
    """List all shortened URLs."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT short_code, original_url, created_at, click_count FROM urls ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return jsonify([
        {
            "short_code": r["short_code"],
            "short_url": f"{BASE_URL}/{r['short_code']}",
            "original_url": r["original_url"],
            "created_at": r["created_at"],
            "click_count": r["click_count"],
        }
        for r in rows
    ])


@app.route("/api/urls/<code>", methods=["DELETE"])
def delete_url(code):
    """Delete a shortened URL."""
    with get_db() as conn:
        result = conn.execute("DELETE FROM urls WHERE short_code = ?", (code,))
        if result.rowcount == 0:
            return jsonify({"error": "Short URL not found"}), 404
    return jsonify({"message": "Deleted successfully"})


@app.route("/<code>", methods=["GET"])
def redirect_url(code):
    """Redirect short code to original URL."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT original_url FROM urls WHERE short_code = ?", (code,)
        ).fetchone()
        if not row:
            abort(404)
        conn.execute(
            "UPDATE urls SET click_count = click_count + 1 WHERE short_code = ?",
            (code,),
        )
    return redirect(row["original_url"], code=302)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=os.environ.get("DEBUG", "false").lower() == "true")
