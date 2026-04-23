from flask import Blueprint, render_template, request, redirect, jsonify
import sqlite3
import random
import string

main = Blueprint('main', __name__)

# ------------------ DATABASE SETUP ------------------

def init_db():
    conn = sqlite3.connect('/tmp/database.db')
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS urls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original TEXT UNIQUE,
        short TEXT UNIQUE,
        clicks INTEGER DEFAULT 0
    )
    ''')

    conn.commit()
    conn.close()

init_db()

# ------------------ SHORT CODE GENERATOR ------------------

def generate_short():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


# ------------------ HOME (UI) ------------------

@main.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        user_url = request.form['url']

        conn = sqlite3.connect('/tmp/database.db')
        c = conn.cursor()

        # Check duplicate
        c.execute("SELECT short FROM urls WHERE original=?", (user_url,))
        existing = c.fetchone()

        if existing:
            short_code = existing[0]
        else:
            short_code = generate_short()

            # Ensure unique short code
            while True:
                c.execute("SELECT * FROM urls WHERE short=?", (short_code,))
                if not c.fetchone():
                    break
                short_code = generate_short()

            c.execute(
                "INSERT INTO urls (original, short) VALUES (?, ?)",
                (user_url, short_code)
            )
            conn.commit()

        conn.close()

        short_url = request.host_url + short_code
        return render_template('index.html', short_url=short_url)

    return render_template('index.html')


# ------------------ REDIRECT + CLICK TRACKING ------------------

@main.route('/<short>')
def redirect_url(short):
    conn = sqlite3.connect('/tmp/database.db')
    c = conn.cursor()

    # Increment clicks
    c.execute("UPDATE urls SET clicks = clicks + 1 WHERE short=?", (short,))

    c.execute("SELECT original FROM urls WHERE short=?", (short,))
    result = c.fetchone()

    conn.commit()
    conn.close()

    if result:
        return redirect(result[0])
    return "URL not found"


# ------------------ ANALYTICS (UI) ------------------

@main.route('/stats/<short>')
def stats(short):
    conn = sqlite3.connect('/tmp/database.db')
    c = conn.cursor()

    c.execute("SELECT original, clicks FROM urls WHERE short=?", (short,))
    result = c.fetchone()

    conn.close()

    if result:
        return f"""
        <h3>Analytics</h3>
        <p><b>Original URL:</b> {result[0]}</p>
        <p><b>Clicks:</b> {result[1]}</p>
        """
    return "No data found"


# ------------------ API: SHORTEN ------------------

@main.route('/api/shorten', methods=['POST'])
def api_shorten():
    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({"error": "No URL provided"}), 400

    user_url = data['url']

    conn = sqlite3.connect('/tmp/database.db')
    c = conn.cursor()

    c.execute("SELECT short FROM urls WHERE original=?", (user_url,))
    existing = c.fetchone()

    if existing:
        short_code = existing[0]
    else:
        short_code = generate_short()

        while True:
            c.execute("SELECT * FROM urls WHERE short=?", (short_code,))
            if not c.fetchone():
                break
            short_code = generate_short()

        c.execute(
            "INSERT INTO urls (original, short) VALUES (?, ?)",
            (user_url, short_code)
        )
        conn.commit()

    conn.close()

    return jsonify({
        "short_url": request.host_url + short_code
    })


# ------------------ API: STATS ------------------

@main.route('/api/stats/<short>', methods=['GET'])
def api_stats(short):
    conn = sqlite3.connect('/tmp/database.db')
    c = conn.cursor()

    c.execute("SELECT original, clicks FROM urls WHERE short=?", (short,))
    result = c.fetchone()

    conn.close()

    if result:
        return jsonify({
            "original_url": result[0],
            "clicks": result[1]
        })

    return jsonify({"error": "Not found"}), 404