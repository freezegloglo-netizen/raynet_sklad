print("APP FILE LOADED")

from fastapi import FastAPI, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
import psycopg2, os, io, json, datetime, threading, time
from openpyxl import Workbook

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

PASSWORD = "morava"


# ================= INIT DB =================
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        code TEXT,
        name TEXT,
        manufacturer TEXT,
        quantity INTEGER DEFAULT 0,
        min_limit INTEGER DEFAULT 5
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movements (
        id SERIAL PRIMARY KEY,
        code TEXT,
        change INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()


# ================= LOGIN =================
@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <html><body style="background:#111;color:#eee;font-family:Arial;text-align:center;margin-top:100px">
    <h2>Přihlášení</h2>
    <form method="post" action="/login">
        Heslo: <input type="password" name="password">
        <button>Přihlásit</button>
    </form>
    </body></html>
    """

@app.post("/login")
def login(password: str = Form(...)):
    if password == PASSWORD:
        r = RedirectResponse("/", status_code=303)
        r.set_cookie("auth", "ok")
        return r
    return RedirectResponse("/login", status_code=303)


# ================= DASHBOARD =================
@app.get("/", response_class=HTMLResponse)
def home(auth: str = Cookie(default=None)):

    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM products")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM products WHERE quantity <= min_limit")
    low = cur.fetchone()[0]

    cur.execute("SELECT manufacturer, SUM(quantity) FROM products GROUP BY manufacturer ORDER BY manufacturer")
    data = cur.fetchall()

    cur.close()
    conn.close()

    labels = [d[0] if d[0] else "Neznámý" for d in data]
    values = [int(d[1]) for d in data]

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
    body {{background:#0f1115;color:#eee;font-family:Arial;margin:0}}
    .nav{{padding:12px;background:#111;position:sticky;top:0}}
    .nav a{{margin-right:10px}}
    .card{{padding:15px;margin:10px;background:#181c22;border-radius:10px}}
    </style>
    </head>
    <body>

    <div class="nav">
        <a href="/"><button>Dashboard</button></a>
        <a href="/all"><button>Produkty</button></a>
        <a href="/low"><button>Nízký stav</button></a>
        <a href="/search"><button>Hledání</button></a>
        <a href="/history"><button>Historie</button></a>
    </div>

    <div class="card">Produkty: {total} | Nízký stav: {low}</div>

    <canvas id="barChart"></canvas>

    <script>
    new Chart(document.getElementById('barChart'), {{
        type: 'bar',
        data: {{
            labels: {json.dumps(labels)},
            datasets: [{{data: {json.dumps(values)}}}]
        }}
    }});
    </script>

    </body></html>
    """)


# ================= PRODUKTY =================
@app.get("/all", response_class=HTMLResponse)
def all_products(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT code,name,manufacturer,quantity,min_limit FROM products ORDER BY manufacturer,name")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    html = """
    <html><body style="background:#111;color:#eee;font-family:Arial">
    <a href="/">Zpět</a>
    <h2>Produkty</h2>
    <table border=1>
    <tr><th>Kód</th><th>Název</th><th>Výrobce</th><th>Množství</th></tr>
    """

    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"

    html += "</table></body></html>"
    return HTMLResponse(html)


# ================= SEARCH =================
@app.get("/search", response_class=HTMLResponse)
def search_page(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    return HTMLResponse("""
    <html><body style="background:#111;color:#eee;font-family:Arial">
    <a href="/">Zpět</a>
    <h2>Hledání</h2>
    <form method="post" action="/search">
        <input name="q" placeholder="Kód / Název / Výrobce">
        <button>Hledat</button>
    </form>
    </body></html>
    """)

@app.post("/search", response_class=HTMLResponse)
def search(q: str = Form(...), auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT code,name,manufacturer,quantity
        FROM products
        WHERE code ILIKE %s OR name ILIKE %s OR manufacturer ILIKE %s
    """, (f"%{q}%", f"%{q}%", f"%{q}%"))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    html = "<html><body style='background:#111;color:#eee'><a href='/search'>Zpět</a><table border=1>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"
    html += "</table></body></html>"

    return HTMLResponse(html)


# ================= LOW =================
@app.get("/low", response_class=HTMLResponse)
def low(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT code,name,manufacturer,quantity FROM products WHERE quantity<=min_limit")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    html = "<html><body style='background:#111;color:#eee'><a href='/'>Zpět</a><h2>Nízký stav</h2><table border=1>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td style='color:red'>{r[3]}</td></tr>"
    html += "</table></body></html>"

    return HTMLResponse(html)


# ================= HISTORY =================
@app.get("/history", response_class=HTMLResponse)
def history(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT code,change,created_at FROM movements ORDER BY created_at DESC LIMIT 200")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    html = "<html><body style='background:#111;color:#eee'><a href='/'>Zpět</a><table border=1>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>"
    html += "</table></body></html>"

    return HTMLResponse(html)


# ================= BACKUP (bez pádu) =================
def backup_loop():
    while True:
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            os.system(f'pg_dump "{DATABASE_URL}" > /tmp/backup_{ts}.sql')
            print("BACKUP OK")
        except Exception as e:
            print("BACKUP ERROR", e)
        time.sleep(3600)

threading.Thread(target=backup_loop, daemon=True).start()
