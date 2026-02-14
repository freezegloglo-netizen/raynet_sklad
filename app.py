print("APP FILE LOADED")

from fastapi import FastAPI, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import os
import psycopg2

app = FastAPI()

from fastapi.responses import JSONResponse


DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres.pphpcjlojcclwiwnxojp:servismorava123@aws-1-eu-west-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()



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
        js = """
    self.addEventListener('install', e => self.skipWaiting());
    self.addEventListener('fetch', event => {});
    """
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


# ================= HOME =================
@app.get("/", response_class=HTMLResponse)
def home(request: Request, auth: str = Cookie(default=None)):

   
    if auth != "ok":
        return RedirectResponse(url="/login", status_code=303)


    q = request.query_params.get("q")

    if q:
        cursor.execute("""
            SELECT id, code, name, manufacturer, quantity, min_limit
            FROM products
            WHERE code LIKE ? OR name LIKE ? OR manufacturer LIKE ?
            ORDER BY manufacturer, name
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        cursor.execute("""
            SELECT id, code, name, manufacturer, quantity, min_limit
            FROM products
            ORDER BY manufacturer, name
        """)

    products = cursor.fetchall()
    html = """<!DOCTYPE html>

    <html>
    <head>
    <meta charset="utf-8">
    <title>Sklad</title>
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');

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
        z-index:10;
    }

    .topbar button {
        margin-right:6px;
    }

    /* BUTTON */
    button {
        background:#2a2a2a;
        color:#fff;
        border:none;
        padding:7px 12px;
        border-radius:10px;
        cursor:pointer;
        transition:.15s;
    }

    button:hover {
        transform:translateY(-1px);
        background:#333;
        box-shadow:0 4px 12px rgba(0,0,0,0.4);
    }

    /* CARD */
    .card {
        background:#1f1f1f;
        border-radius:16px;
        padding:14px;
        margin-bottom:14px;
        box-shadow:0 6px 22px rgba(0,0,0,0.45);
    }

    /* TABLE */
    table {
        width:100%;
        border-collapse:collapse;
        overflow:hidden;
        border-radius:12px;
    }

    th {
        background:#2b2b2b;
        font-weight:600;
    }

    td, th {
        padding:8px;
        border-bottom:1px solid #333;
    }

    tr:hover {
        background:#262626;
    }

    /* BADGE */
    .badge {
        padding:2px 8px;
        border-radius:6px;
        font-size:12px;
    }

    .ok { background:#163d1d; color:#6dff8e; }
    .low { background:#3d2a16; color:#ffcc66; }
    .critical { background:#3d1616; color:#ff6b6b; }

    /* MOBILE */
    @media (max-width:700px) {
        table { font-size:13px; }
        h1 { font-size:20px; }
    }
    </style>

    </head>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#141414">

    <body>
    <div class="topbar">
        <a href="/"><button>🏠 Dashboard</button></a>
        <a href="/all"><button>📦 Seznam dílů</button></a>
        <a href="/low"><button>⚠ Nízký stav</button></a>
        <a href="/history"><button>📈 Historie</button></a>
    <div class="card">
    <h2>🏭 {{manufacturer}}</h2>
    
    <script>
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js');
    }
    </script>

    </div>

    <hr>


    <h1>Sklad</h1>

    <form method="get" action="/">
        🔎 <input name="q" placeholder="kód / název / výrobce">
        <button type="submit">Hledat</button>
    </form>

    <br>

    <a href="/export_excel"><button>📊 Export Excel</button></a>
    <br><br>

    <a href="/export_low_stock">
    <button>Excel - nízký stav</button>
    </a>

    <br><br>

    <hr>

    <h2>📊 Množství podle výrobců</h2>
    <canvas id="chart" height="120"></canvas>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
    const labels = {{ labels }};
    const data = {{ values }};

    const colors = labels.map((_, i) =>
        `hsl(${(i * 360 / labels.length)}, 70%, 50%)`
    );

    new Chart(document.getElementById('chart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
            label: 'Množství',
            data: data,
            backgroundColor: colors
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
        }
    });
    </script>
    <h3>Historie podle výrobce</h3>

    <select id="manSelect"></select>
    <canvas id="lineChart" height="120"></canvas>

    <script>
    window.addEventListener("DOMContentLoaded", async () => {

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

            if (data.length > 0) {
                loadGraph(data[0]);
            }
        }

        async function loadGraph(manufacturer) {
            const res = await fetch(`/api/history/${manufacturer}`);
            const json = await res.json();

            let labels = [];
            const datasets = [];

            const keys = Object.keys(json);
            if (keys.length === 0) return;
 
            keys.forEach((code, i) => {
                const item = json[code];

                if (labels.length === 0) {
                    labels = item.t;
                }

                datasets.push({
                    label: code,
                    data: item.v,
                    borderColor: `hsl(${i * 360 / keys.length}, 70%, 50%)`,
                    fill: false,
                    tension: 0.25,
                    pointRadius: 0
                });
            });

            if (window.lineChart && typeof window.lineChart.destroy === "function") {
                window.lineChart.destroy();
            }

            const ctx = document.getElementById('lineChart').getContext('2d');

            window.lineChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    animation: false,
                    interaction: {
                         mode: 'index',
                         intersect: false
                    },
                    plugins: {
                        legend: { display: true }
                    },
                    scales: {
                        x: { ticks: { maxTicksLimit: 10 }},
                        y: { beginAtZero: true }
                    }
                }
            });
        }

    document.getElementById('manSelect').addEventListener('change', e => {
        loadGraph(e.target.value);
    });

    loadManufacturers();
});
</script>


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


  
    return HTMLResponse(html)

@app.get("/all", response_class=HTMLResponse)
def all_products(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    html = """
    <html>
    <head>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <meta charset="utf-8">
    <title>Seznam dílů</title>
    <style>
    body {
    background:#0f1218;
    color:#e6e6e6;
    font-family: 'Inter', sans-serif;
    }

    /* ===== MENU ===== */
    .topbar {
        background: rgba(20,25,35,0.7);
        backdrop-filter: blur(6px);
        border-radius: 12px;
        padding: 10px;
        margin-bottom: 15px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.35);
    }

    /* ===== TABULKY ===== */
    table {
        border-collapse: collapse;
        width:100%;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 6px 18px rgba(0,0,0,0.35);
    }

    th {
        background: #1c2230;
    }

    td, th {
        padding: 8px;
        border-bottom: 1px solid #2a3244;
    }

    /* ===== BUTTON ===== */
    button {
        background: #1c2230;
        border: none;
        padding: 6px 12px;
        border-radius: 8px;
        color: #ddd;
        transition: 0.15s;
    }

    button:hover {
        background: #2b3447;
        transform: translateY(-1px);
    }

    /* ===== INPUT ===== */
    input {
        background: #1c2230;
        border: 1px solid #2a3244;
        color: #ddd;
        padding: 5px;
        border-radius: 6px;
    }


    /* ===== KARTY ===== */
    .cards {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 14px;
        margin-top: 10px;
    }

    .card {
        background: #151922;
        border-radius: 14px;
        padding: 14px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.35);
        transition: 0.2s;
    }

    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 22px rgba(0,0,0,0.45);
    }

    .card-title {
        font-weight: 600;
        margin-bottom: 4px;
    }

    .card-code {
        font-size: 12px;
        opacity: 0.7;
    }

    .card-qty {
        font-size: 18px;
        font-weight: 600;
        margin: 6px 0;
    }

    .card-actions {
        margin-top: 8px;
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

        cursor.execute("""
            SELECT code, name, quantity, min_limit
            FROM products
            WHERE manufacturer=?
            ORDER BY name
        """, (man,))
        rows = cursor.fetchall()

        for r in rows:
            color = "red" if r[2] <= r[3] else "lime"

            html += f"""
            <tr>
                <td>{r[0]}</td>
                <td>{r[1] if r[1] else "(bez názvu)"}</td>
                <td class="{ 'qty-low' if r[2] <= r[3] else 'qty-ok' }">{r[2]}</td>
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
def low_products(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

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
    return RedirectResponse(url="/", status_code=303)


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


