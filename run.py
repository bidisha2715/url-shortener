from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import string
import os

app = Flask(__name__)
app.secret_key = "secret123"

# Generate short code
def generate_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def is_valid_url(url):
    return url.startswith("http://") or url.startswith("https://")

# ---------------- AUTH ----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect('/login')
        except:
            conn.close()
            return render_template("register.html", error="User already exists")

    return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect('/')
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')


# ---------------- MAIN ----------------

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect('/login')

    short_url = None
    error = None

    if request.method == 'POST':
        original_url = request.form['url']
        custom = request.form.get('custom')

        if not is_valid_url(original_url):
            return render_template("index.html", error="Invalid URL")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        if custom:
            cursor.execute("SELECT * FROM urls WHERE short_code=?", (custom,))
            if cursor.fetchone():
                conn.close()
                return render_template("index.html", error="Alias taken")
            code = custom
        else:
            code = generate_code()

        cursor.execute(
            "INSERT INTO urls (short_code, original_url, clicks, username) VALUES (?, ?, ?, ?)",
            (code, original_url, 0, session['user'])
        )

        conn.commit()
        conn.close()

        short_url = request.host_url + code

    return render_template("index.html", short_url=short_url, error=error)


@app.route('/<code>')
def redirect_url(code):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT original_url, clicks FROM urls WHERE short_code=?", (code,))
    row = cursor.fetchone()

    if row:
        original_url, clicks = row

        cursor.execute("UPDATE urls SET clicks=? WHERE short_code=?", (clicks + 1, code))
        conn.commit()
        conn.close()

        return redirect(original_url)

    return "Not found"


# ---------------- DASHBOARD ----------------

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT short_code, original_url, clicks FROM urls WHERE username=?", (session['user'],))
    links = cursor.fetchall()

    conn.close()

    return render_template("dashboard.html", links=links)


# ---------------- ANALYTICS ----------------

@app.route('/stats/<code>')
def stats(code):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT original_url, clicks FROM urls WHERE short_code=?", (code,))
    row = cursor.fetchone()

    conn.close()

    if not row:
        return "No data"

    original_url, clicks = row
    short_url = request.host_url + code

    return render_template("analytics.html", short_url=short_url, original_url=original_url, clicks=clicks)


# ---------------- EDIT ----------------

@app.route('/edit/<code>', methods=['GET', 'POST'])
def edit(code):
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == 'POST':
        new_code = request.form['new_code']

        cursor.execute("UPDATE urls SET short_code=? WHERE short_code=?", (new_code, code))
        conn.commit()
        conn.close()

        return redirect('/dashboard')

    return render_template("edit.html", code=code)


# ---------------- DELETE ----------------

@app.route('/delete/<code>')
def delete(code):
    if 'user' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM urls WHERE short_code=?", (code,))
    conn.commit()
    conn.close()

    return redirect('/dashboard')


if __name__ == '__main__':
    app.run(debug=True)