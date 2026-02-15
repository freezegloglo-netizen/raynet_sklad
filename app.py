print("APP FILE LOADED")

from fastapi import FastAPI, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import psycopg2
import os


app = FastAPI()

from fastapi.responses import JSONResponse


DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres.pphpcjlojcclwiwnxojp:servismorava123@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"

PASSWORD = "morava"

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY, 
    code TEXT,
    name TEXT,
    manufacturer TEXT,
    quantity INTEGER,
    min_limit INTEGER DEFAULT 5
    );
    """)

cursor.execute("""
CREATE TABLE IF NOT EXISTS movements (
    id SERIAL PRIMARY KEY,
    code TEXT,
    change INTEGER,    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()

from openpyxl import Workbook
from fastapi.responses import StreamingResponse
import io

@app.get("/manifest.json")
def manifest():
    return JSONResponse({
        "name": "Raynet Sklad",
        "short_name": "Sklad",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#141414",
        "theme_color": "#141414",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/3081/3081559.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@app.get("/sw.js")
def sw():
    js = "self.addEventListener('install', e => self.skipWaiting());\nself.addEventListener('fetch', event => {});"
    return HTMLResponse(js, media_type="application/javascript")


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <html>
    <head><meta charset="utf-8"><title>Přihlášení</title></head>
    <body style="background:#1e1e1e;color:#ddd;font-family:Arial;text-align:center;margin-top:100px;">
        <h2>🔐 Přihlášení do skladu</h2>
        <form method="post" action="/login">
            Heslo: <input type="password" name="password">
            <button type="submit">Přihlásit</button>
        </form>
    </body>
    </html>
    """

@app.post("/login")
def login(password: str = Form(...)):
    if password == PASSWORD:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie("auth", "ok")
        return response
    return RedirectResponse(url="/login", status_code=303)

from openpyxl import Workbook
from fastapi.responses import StreamingResponse
import io

@app.get("/export_low_stock")
def export_low_stock():
    cursor.execute("""
        SELECT code, name, manufacturer, quantity, min_limit
        FROM products
        WHERE quantity <= min_limit
        ORDER BY manufacturer, name
    """)
    rows = cursor.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Nízký stav"

    ws.append(["Kód", "Název", "Výrobce", "Množství", "Min limit"])

    for r in rows:
        ws.append(r)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=nizky_stav.xlsx"}
    )


    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>Sklad</title>

    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">

    <style>

    body {
        margin:0;
        font-family:'Inter', sans-serif;
        background:linear-gradient(135deg,#141414,#1c1c1c);
        color:#e6e6e6;
    }

    /* TOP BAR */
    .topbar {
        position:sticky;
        top:0;
        background:rgba(20,20,20,0.9);
        backdrop-filter: blur(8px);
        padding:12px;
        border-bottom:1px solid #2a2a2a;
    }

    button {
        background:#2a2a2a;
        color:#fff;
        border:none;
        padding:7px 12px;
        border-radius:10px;
        cursor:pointer;
    }

    button:hover {
        background:#333;
    }

    .card {
        background:#1f1f1f;
        border-radius:16px;
        padding:14px;
        margin:14px;
    }

    </style>
    </head>

    <body>

    <div class="topbar">
        <a href="/"><button>🏠 Dashboard</button></a>
        <a href="/all"><button>📦 Produkty</button></a>
        <a href="/low"><button>⚠ Nízký stav</button></a>
        <a href="/history"><button>📈 Historie</button></a>
    </div>

    <div class="card">
    <p>Produkty v databázi: """ + str(len(products)) + """</p>
    </div>

    </body>
    </html>
    """    

    # ===== DATA PRO GRAF =====
    cursor.execute("""
        SELECT manufacturer, SUM(quantity)
        FROM products
        GROUP BY manufacturer
        ORDER BY manufacturer
    """)
    data = cursor.fetchall()

    labels = [d[0] if d[0] else "Neznámý" for d in data]
    values = [d[1] for d in data]

    import json
    html = html.replace("{{ labels }}", json.dumps(labels))
    html = html.replace("{{ values }}", json.dumps(values))

    # ===== DASHBOARD STATISTIKY =====
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products WHERE quantity <= min_limit")
    low_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM movements WHERE DATE(created_at)=CURRENT_DATE")
    today_moves = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT manufacturer) FROM products")
    manufacturers = cursor.fetchone()[0]

    html = html.replace("{{total_products}}", str(total_products))
    html = html.replace("{{low_products}}", str(low_products))
    html = html.replace("{{today_moves}}", str(today_moves))
    html = html.replace("{{manufacturers}}", str(manufacturers))
    # ================================

# ================= HOME / DASHBOARD =================
@app.get("/", response_class=HTMLResponse)
def home(request: Request, auth: str = Cookie(default=None)):

    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        # ====== DATA PRO GRAF SLOUPCOVÝ ======
        cursor.execute("""
            SELECT manufacturer, SUM(quantity)
            FROM products
            GROUP BY manufacturer
            ORDER BY manufacturer
        """)
        data = cursor.fetchall()

        labels = [d[0] if d[0] else "Neznámý" for d in data]
        values = [int(d[1]) for d in data]

        # ===== DASHBOARD STATISTIKY =====
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM products WHERE quantity <= min_limit")
        low_products = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM movements WHERE DATE(created_at)=CURRENT_DATE")
        today_moves = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT manufacturer) FROM products")
        manufacturers = cursor.fetchone()[0]

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return HTMLResponse(f"<h1>DB ERROR</h1><pre>{e}</pre>")

    cursor.close()
    conn.close()

    import json

    html = """
    <html>
    <head>
    <meta charset="utf-8">
    <title>Sklad</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>

    <body style="background:#111;color:#eee;font-family:Arial">

    <div>
        <b>📦 Produkty:</b> {{total_products}} |
        <b>⚠ Nízký stav:</b> {{low_products}} |
        <b>📈 Pohyby dnes:</b> {{today_moves}} |
        <b>🏭 Výrobci:</b> {{manufacturers}}
    </div>

    <hr>

    <h2>Množství podle výrobců</h2>
    <canvas id="barChart"></canvas>

    <h2>Historie podle výrobce</h2>
    <select id="manSelect"></select>
    <canvas id="lineChart"></canvas>

    <script>

    const labels = {{labels}};
    const values = {{values}};

    new Chart(document.getElementById('barChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Množství',
                data: values
            }]
        }
    });

    async function loadManufacturers() {
        const res = await fetch('/api/manufacturers');
        const data = await res.json();
        const sel = document.getElementById('manSelect');
        sel.innerHTML = "";

        data.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            sel.appendChild(opt);
        });

        if (data.length > 0) loadGraph(data[0]);
    }

    async function loadGraph(man) {
        const res = await fetch(`/api/history/${man}`);
        const json = await res.json();

        let labels = [];
        const datasets = [];

        const keys = Object.keys(json);
        if (keys.length === 0) return;

        keys.forEach((code, i) => {
            const item = json[code];
            if (labels.length === 0) labels = item.t;

            datasets.push({
                label: code,
                data: item.v,
                borderWidth: 2,
                fill: false
            });
        });

        if (window.lineChart) window.lineChart.destroy();

        window.lineChart = new Chart(document.getElementById('lineChart'), {
            type: 'line',
            data: { labels: labels, datasets: datasets }
        });
    }

    document.getElementById('manSelect').addEventListener('change', e => {
        loadGraph(e.target.value);
    });

    loadManufacturers();
    </script>

    </body>
    </html>
    """

    html = html.replace("{{labels}}", json.dumps(labels))
    html = html.replace("{{values}}", json.dumps(values))
    html = html.replace("{{total_products}}", str(total_products))
    html = html.replace("{{low_products}}", str(low_products))
    html = html.replace("{{today_moves}}", str(today_moves))
    html = html.replace("{{manufacturers}}", str(manufacturers))

    return HTMLResponse(html)

@app.get("/all", response_class=HTMLResponse)
def all_products(request: Request, auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)
    q = request.query_params.get("q")

    html = """
    <html>
    <head>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <meta charset="utf-8">
    <title>Seznam dílů</title>
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

    body{
        margin:0;
        font-family:'Inter',sans-serif;
        background:linear-gradient(135deg,#0f1115,#181c22);
        color:#e8e8e8;
    }

    /* ===== TOP BAR ===== */
    .topbar{
        position:sticky;
        top:0;
        display:flex;
        gap:8px;
        padding:14px;
        background:rgba(15,17,21,0.85);
        backdrop-filter:blur(8px);
        border-bottom:1px solid #262a33;
        z-index:10;
    }

    /* ===== BUTTON ===== */
    button{
        background:#222833;
        color:#fff;
        border:none;
        padding:8px 14px;
        border-radius:10px;
        cursor:pointer;
        transition:0.15s;
        font-weight:500;
    }

    button:hover{
        background:#2d3442;
        transform:translateY(-1px);
        box-shadow:0 4px 14px rgba(0,0,0,0.35);
    }

    /* ===== DASHBOARD GRID ===== */
    .grid{
        display:grid;
        grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
        gap:14px;
        margin-bottom:14px;
    }

    /* ===== CARD ===== */
    .card{
        background:#171b22;
        border-radius:16px;
        padding:16px;
        box-shadow:0 8px 24px rgba(0,0,0,0.45);
        border:1px solid #262a33;
    }

    /* ===== STAT NUMBER ===== */
    .stat{
        font-size:26px;
        font-weight:600;
    }

    /* ===== TABLE ===== */
    table{
        width:100%;
        border-collapse:collapse;
        border-radius:12px;
        overflow:hidden;
    }

    th{
        background:#202631;
        font-weight:600;
    }

    td,th{
        padding:9px;
        border-bottom:1px solid #262a33;
    }

    tr:hover{
        background:#1c212b;
    }

    /* ===== STATUS COLORS ===== */
    .ok{color:#4cff88;font-weight:600;}
    .low{color:#ffcc66;font-weight:600;}
    .critical{color:#ff5c5c;font-weight:600;}

    /* ===== MOBILE ===== */
    @media(max-width:700px){
        h1{font-size:20px}
        table{font-size:13px}
    }
    </style>

    </head>
    <body>

    <div class="navbar">
        <a href="/"><button class="navbtn">🏠 Domů</button></a>
        <a href="/all"><button class="navbtn">📦 Seznam dílů</button></a>
        <a href="/low"><button class="navbtn">⚠ Nízký stav</button></a>
        <a href="/history"><button class="navbtn">🕘 Historie</button></a>
    </div>

    <h1>📦 Seznam podle výrobců</h1>
    
    <form method="get" action="/all" style="margin-bottom:10px;">
        <input name="q" placeholder="Hledat kód / název">
        <button>Hledat</button>
    </form>

    <h3>Přidat nový produkt</h3>

    <form method="post" action="/add" style="margin-bottom:20px;">
        Kód: <input name="code" required>
        Název: <input name="name" required>
        Výrobce: <input name="manufacturer" required>
        Množství: <input name="quantity" type="number" value="0">
        Min limit: <input name="min_limit" type="number" value="5">
    <button>Přidat</button>
    </form>
    <hr>
    """

    if q:
        cursor.execute("""
            SELECT DISTINCT manufacturer
            FROM products
            WHERE code ILIKE %s
               OR name ILIKE %s
               OR manufacturer ILIKE %s
            ORDER BY manufacturer
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        cursor.execute("SELECT DISTINCT manufacturer FROM products ORDER BY manufacturer")

    manufacturers = [m[0] for m in cursor.fetchall()]


    for man in manufacturers:

        html += f"<h2>🏭 {man}</h2>"
        html += """
        <table>
        <tr>
            <th>Kód</th>
            <th>Název</th>
            <th>Množství</th>
            <th>Min</th>
            <th>Akce</th>
        </tr>
        """

        if q:
            cursor.execute("""
                SELECT code, name, quantity, min_limit
                FROM products
                WHERE manufacturer=%s
                AND (
                    code ILIKE %s
                    OR name ILIKE %s
                    OR manufacturer ILIKE %s
                )
                ORDER BY name
            """, (man, f"%{q}%", f"%{q}%", f"%{q}%"))
        else:
            cursor.execute("""
                SELECT code, name, quantity, min_limit
                FROM products
                WHERE manufacturer=%s
                ORDER BY name
            """, (man,))

        rows = cursor.fetchall()

        for r in rows:
            html += f"""
            <tr>
                <td>{r[0]}</td>
                <td>{r[1] if r[1] else "(bez názvu)"}</td>
                <td class="{ 'low' if r[2] <= r[3] else 'ok' }">{r[2]}</td>
                <td>{r[3]}</td>
                <td>
                    <form method="post" action="/change" style="display:inline;">
                        <input type="hidden" name="code" value="{r[0]}">
                        <button name="type" value="add">+</button>
                        <button name="type" value="sub">-</button>
                    </form>

                    <form method="post" action="/delete_by_code" style="display:inline;"
                          onsubmit="return confirm('Opravdu smazat {r[1]}?');">
                        <input type="hidden" name="code" value="{r[0]}">
                        <button style="color:red;">Smazat</button>
                    </form>
                </td>
            </tr>
            """

        html += "</table>"

    html += "</body></html>"
    return HTMLResponse(html)


@app.get("/low", response_class=HTMLResponse)
def all_products(request: Request, auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)
    q = request.query_params.get("q")


    cursor.execute("""
        SELECT code, name, manufacturer, quantity
        FROM products
        WHERE quantity <= 5
        ORDER BY manufacturer, name
    """)
    rows = cursor.fetchall()

    html = """
    <html><body style="background:#1e1e1e;color:#ddd;font-family:Arial;">
    <h1>⚠ Nízký stav — objednat</h1>
    <a href="/"><button>Zpět</button></a>
    <table border="1" style="border-collapse:collapse;width:100%;">
    <tr><th>Kód</th><th>Název</th><th>Výrobce</th><th>Množství</th></tr>
    """

    for r in rows:
        html += f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td>{r[2]}</td>
            <td style="color:red;font-weight:bold;">{r[3]}</td>
        </tr>
        """

    html += "</table></body></html>"
    return HTMLResponse(html)

from fastapi.responses import JSONResponse

@app.get("/api/history/{manufacturer}")
def history_graph(manufacturer: str):

    cursor.execute("""
        SELECT m.code, m.change, m.created_at
        FROM movements m
        LEFT JOIN products p ON LOWER(TRIM(p.code)) = LOWER(TRIM(m.code))
        WHERE p.manufacturer = ?
        ORDER BY m.created_at
    """, (manufacturer,))

    rows = cursor.fetchall()

    timeline = {}
    for code, change, ts in rows:
        timeline.setdefault(code, {"t": [], "v": [], "sum": 0})
        timeline[code]["sum"] += change
        timeline[code]["t"].append(ts)
        timeline[code]["v"].append(timeline[code]["sum"])

    return JSONResponse(timeline)

@app.get("/history", response_class=HTMLResponse)
def history(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    cursor.execute("""
        SELECT code, change, created_at
        FROM movements
        ORDER BY created_at DESC
        LIMIT 200
    """)
    rows = cursor.fetchall()

    html = """
    <html><body style="background:#1e1e1e;color:#ddd;font-family:Arial;">
    <h1>🕘 Historie pohybů</h1>
    <a href="/"><button>Zpět</button></a>
    <table border="1" style="border-collapse:collapse;width:100%;">
    <tr><th>Kód</th><th>Změna</th><th>Datum</th></tr>
    """

    for r in rows:
        color = "lime" if r[1] > 0 else "red"
        html += f"""
        <tr>
            <td>{r[0]}</td>
            <td style="color:{color};font-weight:bold;">{r[1]}</td>
            <td>{r[2]}</td>
        </tr>
        """

    html += "</table></body></html>"
    return HTMLResponse(html)


# ================= ADD =================
@app.post("/add")
def add_product(
    code: str = Form(""),
    name: str = Form(""),
    manufacturer: str = Form(""),
    quantity: int = Form(0),
    min_limit: int = Form(5)
):
    cursor.execute(
        "INSERT INTO products (code, name, manufacturer, quantity, min_limit) VALUES (?, ?, ?, ?, ?)",
        (code, name, manufacturer, quantity, min_limit)
    )
    conn.commit()
    return RedirectResponse("/all", status_code=303)


# ================= CHANGE =================
@app.post("/change")
def change(code: str = Form(...), type: str = Form(...)):

    # vezmeme skutečný code z DB
    cursor.execute("SELECT code, quantity FROM products WHERE code=?", (code,))
    row = cursor.fetchone()
    if not row:
        return RedirectResponse("/all", status_code=303)

    real_code, q = row

    if type == "add":
        q += 1
        change_val = 1
    else:
        q = max(0, q - 1)
        change_val = -1

    cursor.execute("UPDATE products SET quantity=? WHERE code=?", (q, real_code))

    # ukládáme správný code
    cursor.execute("""
        INSERT INTO movements (code, change, created_at)
        VALUES (?, ?, ?)
    """, (
        real_code,
        change_val,
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    return RedirectResponse("/all", status_code=303)
    

# ================= DELETE =================
@app.post("/delete")
def delete_product(id: int = Form(...)):
    cursor.execute("DELETE FROM products WHERE id=?", (id,))
    conn.commit()
    return RedirectResponse(url="/", status_code=303)

from openpyxl import Workbook
import io
from fastapi.responses import StreamingResponse

from fastapi import Request

@app.post("/delete_by_code")
async def delete_by_code(request: Request):

    form = await request.form()
    code = form.get("code")

    if not code:
        return RedirectResponse("/all", status_code=303)

    cursor.execute("DELETE FROM products WHERE code=?", (code,))
    conn.commit()

    return RedirectResponse("/all", status_code=303)


@app.get("/export_excel")
def export_excel():

    cursor.execute("""
        SELECT code, name, manufacturer, quantity, min_limit
        FROM products
        ORDER BY manufacturer, name
    """)
    rows = cursor.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Sklad"

    ws.append(["Kód", "Název", "Výrobce", "Množství", "Min limit"])

    for r in rows:
        ws.append(r)

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=sklad.xlsx"}
    )

@app.post("/set_min")
def set_min(code: str = Form(...), min_limit: int = Form(...)):
    cursor.execute(
        "UPDATE products SET min_limit=? WHERE code=?",
        (min_limit, code)
    )
    conn.commit()
    return RedirectResponse("/all", status_code=303)

from fastapi.responses import JSONResponse

# ===== API seznam výrobců =====
@app.get("/api/manufacturers")
def api_manufacturers():
    cursor.execute("SELECT DISTINCT manufacturer FROM products ORDER BY manufacturer")
    return [m[0] if m[0] else "Neznámý" for m in cursor.fetchall()]


# ===== API historie podle výrobce =====
@app.get("/api/history/{manufacturer}")
def api_history(manufacturer: str):

    # vezmeme všechny movements pro produkty daného výrobce
    cursor.execute("""
        SELECT m.code, m.change, m.created_at
        FROM movements m
        WHERE LOWER(TRIM(m.code)) IN (
            SELECT LOWER(TRIM(code))
            FROM products
            WHERE LOWER(TRIM(manufacturer)) = LOWER(TRIM(?))
        )
        ORDER BY m.created_at
    """, (manufacturer,))

    rows = cursor.fetchall()

    if not rows:
        return JSONResponse({})

    timeline = {}
    for code, change, ts in rows:
        timeline.setdefault(code, {"t": [], "v": [], "sum": 0})
        timeline[code]["sum"] += change
        timeline[code]["t"].append(ts)
        timeline[code]["v"].append(timeline[code]["sum"])

    return JSONResponse(timeline)

import threading, time, datetime, os

def backup_loop():
    while True:
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            filename = f"/tmp/backup_{ts}.sql"

            os.system(f'pg_dump "{DATABASE_URL}" > {filename}')
            print("BACKUP OK", filename)

        except Exception as e:
            print("BACKUP ERROR", e)

        time.sleep(3600)

threading.Thread(target=backup_loop, daemon=True).start()

import threading, time, json

def backup_loop():
    while True:
        try:
            cursor.execute("SELECT code, name, manufacturer, quantity, min_limit FROM products")
            rows = cursor.fetchall()

            data = json.dumps(rows)

            cursor.execute(
                "INSERT INTO backups (data) VALUES (%s)",
                (data,)
            )
            conn.commit()

            print("BACKUP OK")

        except Exception as e:
            print("BACKUP ERROR:", e)

        time.sleep(3600)   # každou hodinu

threading.Thread(target=backup_loop, daemon=True).start()

import os

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )

