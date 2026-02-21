print("APP FILE LOADED v2")

from fastapi import FastAPI, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
import psycopg2, os, io, json, datetime
from openpyxl import Workbook
from psycopg2.pool import SimpleConnectionPool

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None


def safe_close(conn, cur=None):
    try:
        if cur:
            cur.close()
    except:
        pass

    try:
        if conn:
            db_pool.putconn(conn, close=False)
    except:
        pass

@app.on_event("startup")
def startup():
    global db_pool
    print("INIT DB POOL...")

    try:
        db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=DATABASE_URL + "?sslmode=require"   # Supabase potřebuje SSL
        )

        print("DB POOL READY")
        init_db()

    except Exception as e:
        print("DB INIT FAILED:", e)
        db_pool = None

@app.on_event("shutdown")
def shutdown():
    global db_pool
    if db_pool:
        db_pool.closeall()


PASSWORD = "morava"

USERS = [
    ("Lukas", "Lukáš"),
    ("Jirka", "Jirka"),
    ("Milan", "Milan"),
]

# ================= DB =================

db_pool = None

def get_conn():
    if db_pool is None:
        raise Exception("DB NOT CONNECTED")

    return db_pool.getconn()


def safe_close(conn, cur=None):
    try:
        if cur:
            cur.close()
    except:
        pass

    try:
        if conn:
            db_pool.putconn(conn)
    except:
        pass

def init_db():
    conn = None
    cur = None
    try:
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
            user_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS car_stock (
            id SERIAL PRIMARY KEY,
            user_name TEXT,
            code TEXT,
            quantity INTEGER DEFAULT 0,
            UNIQUE(user_name, code)
        );
        """)

        conn.commit()

    except Exception as e:
        print("DB INIT FAILED:", e)

    finally:
        safe_close(conn, cur)

@app.on_event("startup")
def startup():
    global db_pool
    print("INIT DB POOL...")

    db_pool = SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=DATABASE_URL + "?sslmode=require"
    )

    print("DB POOL READY")
    init_db()


@app.on_event("shutdown")
def shutdown():
    global db_pool
    if db_pool:
        db_pool.closeall()

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
        user_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS car_stock (
        id SERIAL PRIMARY KEY,
        user_name TEXT,
        code TEXT,
        quantity INTEGER DEFAULT 0,
        UNIQUE(user_name, code)
    );
    """)

    conn.commit()
    safe_close(conn, cur)
# ================= LOGIN =================
@app.get("/login", response_class=HTMLResponse)
def login_page():
    return """
    <html><body style="background:#111;color:#eee;font-family:Arial;text-align:center;margin-top:100px">
    <h2>🔐 Přihlášení</h2>
    <form method="post">
    <input type="password" name="password">
    <button>Přihlásit</button>
    </form>
    </body></html>
    """


@app.post("/login")
def login(password: str = Form(...)):
    if password == PASSWORD:
        r = RedirectResponse("/select_user", status_code=303)
        r.set_cookie("auth", "ok")
        return r
    return RedirectResponse("/login", status_code=303)

# ================= USER SELECT =================
@app.get("/select_user", response_class=HTMLResponse)
def select_user(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    html = """
    <html><body style="background:#111;color:#eee;font-family:Arial;
    display:flex;justify-content:center;align-items:center;height:100vh">

    <div style="text-align:center">
    <h2>Vyber uživatele</h2>
    """

    for key, label in USERS:
        html += f"""
        <form method="post" action="/set_user" style="margin:10px">
            <input type="hidden" name="user" value="{key}">
            <button style="padding:15px 40px;font-size:18px">{label}</button>
    </form>
    """

    # 👇 TLAČÍTKO SKLAD
    html += """
    <form method="post" action="/set_sklad" style="margin-top:20px">
        <button style="padding:15px 40px;font-size:18px;background:#2b5">
            📦 Přehled / Úprava skladu
        </button>
    </form>
    """

    html += "</div></body></html>"
    return HTMLResponse(html)


import urllib.parse

@app.post("/set_user")
def set_user(user: str = Form(...)):
    r = RedirectResponse("/", status_code=303)

    import urllib.parse
    safe_user = urllib.parse.quote(user)

    r.set_cookie("user", safe_user)
    r.set_cookie("mode", "driver")

    return r

@app.post("/set_sklad")
def set_sklad():
    r = RedirectResponse("/", status_code=303)
    r.set_cookie("user", "Sklad")
    r.set_cookie("mode", "sklad")
    return r

# ================= DASHBOARD =================
@app.get("/", response_class=HTMLResponse)
def home(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn=None
    cur=None
    
    try:
        conn = get_conn()
        cur = conn.cursor()

        # sloupcový graf
        cur.execute("SELECT manufacturer, SUM(quantity) FROM products GROUP BY manufacturer ORDER BY manufacturer")
        data = cur.fetchall()
        labels = [d[0] or "Neznámý" for d in data]
        values = [int(d[1]) for d in data]

        # statistiky
        cur.execute("SELECT COUNT(*) FROM products")
        total_products = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM products WHERE quantity <= min_limit")
        low_products = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM movements WHERE DATE(created_at)=CURRENT_DATE")
        today_moves = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT manufacturer) FROM products")
        manufacturers = cur.fetchone()[0]

    except Exception as e:
        print("HOME ERROR:", e)

    finally:
        safe_close(conn, cur)

    html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
    body{{background:#111;color:#eee;font-family:Arial;margin:0}}

    .topbar{{
        position:sticky;
        top:0;
        background:#0f1115;
        padding:12px;
        display:flex;
        gap:10px;
        border-bottom:1px solid #222;
        z-index:999;
    }}

    .topbar button{{
        background:#1f2a3a;
        padding:8px 14px;
        border-radius:10px;
        border:none;
        color:white;
        font-weight:600;
        cursor:pointer;
    }}

    .topbar button:hover{{
        background:#2d3b52;
    }}

    .content{{padding:20px}}

    .card{{
        background:#1b1b1b;
        padding:15px;
        border-radius:14px;
        margin-bottom:15px;
    }}
    </style>
    </head>

    <body>

    <!-- TOP MENU -->
    <div class="topbar">
        <a href="/"><button>Dashboard</button></a>
        <a href="/all"><button>Sklad-Kancl</button></a>
        <a href="/car"><button>Auto</button></a>
        <a href="/low"><button>Nízký stav</button></a>
        <a href="/history"><button>Historie</button></a>
        <a href="/cars"><button>Všechna auta</button></a>
    </div>

    <div class="content">

    <div style="display:flex;gap:10px">

    <div class="card">📦<br>{total_products}<br>Produkty</div>
    <div class="card">⚠<br>{low_products}<br>Nízký stav</div>
    <div class="card">📈<br>{today_moves}<br>Dnes pohyby</div>
    <div class="card">🏭<br>{manufacturers}<br>Výrobci</div>

    </div>


    <canvas id="bar"></canvas>

    <h3>Historie podle výrobce</h3>
    <select id="man"></select>
    <canvas id="line"></canvas>

    </div>

    <script>
    const labels={json.dumps(labels)};
    const values={json.dumps(values)};

    new Chart(document.getElementById('bar'),{{
        type:'bar',
        data:{{labels:labels,datasets:[{{data:values}}]}}
    }});

    async function loadMan(){{
        const r=await fetch('/api/manufacturers');
        const data=await r.json();
        let s=document.getElementById('man');
        data.forEach(m=>{{
            let o=document.createElement('option');
            o.value=m;
            o.textContent=m;
            s.appendChild(o);
        }});
        if(data.length)loadGraph(data[0]);
    }}

    async function loadGraph(m){{
        const r=await fetch('/api/history/'+m);
        const j=await r.json();
        let labels=[],datasets=[];
        Object.keys(j).forEach((k,i)=>{{
            if(labels.length==0)labels=j[k].t;
            datasets.push({{label:k,data:j[k].v,fill:false}});
        }});
        if(window.l)window.l.destroy();
        window.l=new Chart(document.getElementById('line'),{{type:'line',data:{{labels:labels,datasets:datasets}}}});
    }}

    document.getElementById('man').onchange=e=>loadGraph(e.target.value);
    loadMan();
    </script>

    </body>
    </html>
    """
        
    return HTMLResponse(html)



# ================= API =================
@app.get("/api/manufacturers")
def api_man():
    conn=get_conn()
    cur=conn.cursor()
    cur.execute("SELECT DISTINCT manufacturer FROM products ORDER BY manufacturer")
    data=[m[0] or "Neznámý" for m in cur.fetchall()]
    safe_close(conn, cur)
    return data

@app.get("/car", response_class=HTMLResponse)
def car(auth: str = Cookie(default=None), user: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    import urllib.parse
    if user:
        user = urllib.parse.unquote(user)

    if not user:
        return RedirectResponse("/select_user", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT code, quantity FROM car_stock
        WHERE user_name=%s
        ORDER BY code
    """, (user,))
    rows = cur.fetchall()

    html = f"<html><body style='background:#111;color:#eee;font-family:Arial'>"
    html += f"<h2>Auto — {user}</h2><a href='/'>Zpět</a><table border=1 width=100%>"
    html += "<tr><th>Kód</th><th>Množství</th></tr>"

    if not rows:
        html += "<tr><td colspan=2 style='color:#777'>Prázdné auto</td></tr>"
    else:
        for r in rows:
            html += f"<tr><td>{r[0]}</td><td>{r[1]}</td></tr>"

    html += "</table></body></html>"

    
    safe_close(conn, cur)

    return HTMLResponse(html)



@app.get("/cars", response_class=HTMLResponse)
def cars(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    html = """
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    body{background:#0f1115;color:#eee;font-family:Arial;margin:0;padding:20px}
    .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}
    .card{background:#151922;border-radius:14px;padding:15px}
    table{width:100%;border-collapse:collapse}
    th,td{padding:8px;border-bottom:1px solid #222;text-align:left}
    h3{margin-top:0}
    </style>
    </head>
    <body>

    <a href="/"><button>Zpět</button></a>
    <h2>🚐 Všechna auta</h2>

    <div class="grid">
    """

    for key, label in USERS:

        html += f"<div class='card'><h3>{label}</h3>"
        html += "<table>"
        html += "<tr><th>Kód</th><th>Množství</th></tr>"

        cur.execute("""
            SELECT code, quantity
            FROM car_stock
            WHERE user_name=%s
            ORDER BY code
        """, (key,))


        rows = cur.fetchall()

        if not rows:
            html += "<tr><td colspan=2 style='color:#777'>Prázdné auto</td></tr>"
        else:
            for code, qty in rows:
                html += f"<tr><td>{code}</td><td>{qty}</td></tr>"

        html += "</table></div>"

    html += """
    </div>
    </body>
    </html>
    """

    safe_close(conn, cur)
    return HTMLResponse(html)


@app.get("/api/history/{manufacturer}")
def api_hist(manufacturer:str):
    conn=None
    cur=None
    try:
        conn=get_conn()
        cur=conn.cursor()
        cur.execute("""
        SELECT code,change,created_at FROM movements
        WHERE code IN (SELECT code FROM products WHERE manufacturer=%s)
        ORDER BY created_at
        """,(manufacturer,))
        rows=cur.fetchall()

    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

    timeline={}
    for code,ch,ts in rows:
        timeline.setdefault(code,{"t":[],"v":[],"s":0})
        timeline[code]["s"]+=ch
        timeline[code]["t"].append(str(ts))
        timeline[code]["v"].append(timeline[code]["s"])
    return timeline

@app.post("/add")
def add(
    code: str = Form(...),
    name: str = Form(...),
    manufacturer: str = Form(...),
    quantity: int = Form(0),
    min_limit: int = Form(5)
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products(code,name,manufacturer,quantity,min_limit)
        VALUES(%s,%s,%s,%s,%s)
    """, (code,name,manufacturer,quantity,min_limit))
    conn.commit()
    safe_close(conn, cur)
    return RedirectResponse("/all", status_code=303)


@app.post("/change")
def change(code: str = Form(...), type: str = Form(...), user: str = Cookie(default=None)):
    import urllib.parse

    if user:
        user = urllib.parse.unquote(user)

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT quantity FROM products WHERE code=%s", (code,))
        row = cur.fetchone()
        if not row:
            return RedirectResponse("/all", status_code=303)

        qty = row[0]

        if type == "add":
            qty += 1
            change_val = 1
        else:
            qty = max(0, qty - 1)
            change_val = -1

        cur.execute("UPDATE products SET quantity=%s WHERE code=%s", (qty, code))

        cur.execute(
            "INSERT INTO movements(code, change, user_name) VALUES(%s,%s,%s)",
            (code, change_val, user or "Unknown")
        )

        conn.commit()

    except Exception as e:
        print("CHANGE ERROR:", e)
        if conn:
            conn.rollback()
        return HTMLResponse(f"<h1>DB ERROR</h1><pre>{e}</pre>", status_code=500)

    finally:
        if cur:
            cur.close()
        if conn:
            db_pool.putconn(conn)

    return RedirectResponse("/all", status_code=303)

@app.post("/delete_by_code")
def delete_by_code(code: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE code=%s", (code,))
    conn.commit()
    safe_close(conn, cur)
    return RedirectResponse("/all", status_code=303)

@app.post("/to_car")
def to_car(code: str = Form(...), user: str = Cookie(default=None)):
    import urllib.parse

    if user:
        user = urllib.parse.unquote(user)

    if not user:
        return RedirectResponse("/select_user", status_code=303)

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE products
            SET quantity = quantity - 1
            WHERE code=%s AND quantity > 0
            RETURNING quantity
        """, (code,))

        if cur.fetchone() is None:
            conn.commit()
            return RedirectResponse("/all", status_code=303)

        cur.execute("""
            INSERT INTO car_stock(user_name, code, quantity)
            VALUES(%s,%s,1)
            ON CONFLICT (user_name, code)
            DO UPDATE SET quantity = car_stock.quantity + 1
        """, (user, code))

        conn.commit()

    except Exception as e:
        print("TO_CAR ERROR:", e)
        if conn:
            conn.rollback()
        return HTMLResponse(f"<h1>DB ERROR</h1><pre>{e}</pre>", status_code=500)

    finally:
        safe_close(conn, cur)

    return RedirectResponse("/all", status_code=303)



# ================= PRODUCTS =================
@app.get("/all", response_class=HTMLResponse)
def all_products(auth: str = Cookie(default=None), q: str = None):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()
    if q:
        cur.execute("""
            SELECT code,name,manufacturer,quantity,min_limit
            FROM products
            WHERE code ILIKE %s
            OR manufacturer ILIKE %s
            ORDER BY manufacturer,name
        """, (f"%{q}%", f"%{q}%"))
    else:
        cur.execute("""
            SELECT code,name,manufacturer,quantity,min_limit
            FROM products
            ORDER BY manufacturer,name
        """)
    rows = cur.fetchall()

    safe_close(conn, cur)
    from collections import defaultdict

    grouped = defaultdict(list)
    for row in rows:
        grouped[row[2]].append(row)   # row[2] = manufacturer


    html = """
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    body{background:#0f1115;color:#eee;font-family:Inter;margin:0;padding:20px}
    .top{display:flex;gap:10px;margin-bottom:15px}
    button{background:#2b3445;color:#fff;border:none;padding:6px 12px;border-radius:8px;cursor:pointer}
    button:hover{background:#3b4760}
    table{width:100%;border-collapse:collapse}
    th,td{padding:10px;border-bottom:1px solid #222}
    .card{background:#151922;border-radius:14px;padding:15px;margin-bottom:15px}
    </style>
    </head>
    <body>

    <div class="top">
        <a href="/"><button>Dashboard</button></a>
        <a href="/low"><button>Nízký stav</button></a>
        <a href="/car"><button>Auto</button></a>
        <a href="/history"><button>Historie</button></a>
        <a href="/cars"><button>Všechna auta</button></a>
    </div>

        <div class="card">
    <h3>Přidat produkt</h3>
    <form method="post" action="/add">
        Kód <input name="code" required>
        Název <input name="name" required>
        Výrobce <input name="manufacturer" required>
        Množství <input type="number" name="quantity" value="0">
        Min <input type="number" name="min_limit" value="5">
        <button type="submit">Přidat</button>
    </form>
    </div>

    <div class="card">
    <h3>Vyhledávání</h3>
    <form method="get" action="/all" style="display:flex;gap:10px">
        <input name="q" placeholder="Hledáš něco ?" value="{q or ''}">
        <button type="submit">Hledat</button>
        <a href="/all"><button type="button">Vyčistit filtr</button></a>
    </form>
    </div>
    """


    for man in sorted(grouped):

        html += f"<h3>🏭 {man}</h3>"
        html += "<table>"
        html += "<tr><th>Kód</th><th>Název</th><th>Množství</th><th>Akce</th></tr>"

        for code, name, manufacturer, qty, minl in grouped[man]:

            html += f"""
            <tr>
                <td>{code}</td>
                <td>{name}</td>
                <td>{qty}</td>
                <td>

                <form method="post" action="/change" style="display:inline">
                    <input type="hidden" name="code" value="{code}">
                    <button name="type" value="add">＋</button>
                    <button name="type" value="sub">－</button>
                </form>

                <form method="post" action="/to_car" style="display:inline">
                    <input type="hidden" name="code" value="{code}">
                    <button style="background:#205080">Auto</button>
                </form>

                <form method="post" action="/delete_by_code" style="display:inline"
                onsubmit="return confirm('Opravdu chceš smazat produkt?');">
                    <input type="hidden" name="code" value="{code}">
                    <button style="background:#802020">Smazat</button>
                </form>

                </td>
            </tr>
            """

        html += "</table>"

    html += "</body></html>"
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
    safe_close(conn, cur)

    html = "<html><body style='background:#111;color:#eee;font-family:Arial'>"
    html += "<h2>Nízký stav</h2><a href='/'>Zpět</a><table border=1 width=100%>"
    html += "<tr><th>Kód</th><th>Název</th><th>Výrobce</th><th>Množství</th></tr>"

    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td style='color:red'>{r[3]}</td></tr>"

    html += "</table></body></html>"
    return HTMLResponse(html)



# ================= HISTORY =================
@app.get("/history", response_class=HTMLResponse)
def history(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT code, change, created_at, COALESCE(user_name, 'Unknown')
            FROM movements
            ORDER BY created_at DESC
            LIMIT 200
        """)
        rows = cur.fetchall()

    except Exception as e:
        print("HISTORY ERROR:", e)
        return HTMLResponse(f"<h1>DB ERROR</h1><pre>{e}</pre>", status_code=500)

    finally:
        safe_close(conn, cur)

    html="<html><body style='background:#111;color:#eee;font-family:Arial'>"
    html+="<h2>Historie</h2><a href='/'>Zpět</a><table border=1 width=100%>"
    html+="<tr><th>Kód</th><th>Změna</th><th>Datum</th><th>Uživatel</th></tr>"

    for r in rows:
        col="lime" if r[1]>0 else "red"
        html+=f"<tr><td>{r[0]}</td><td style='color:{col}'>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"

    html+="</table></body></html>"
    return HTMLResponse(html)
