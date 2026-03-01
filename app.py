print("APP FILE LOADED v2")

from fastapi import FastAPI, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
import psycopg2, os, io, json, datetime
from openpyxl import Workbook
from psycopg2.pool import SimpleConnectionPool
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from io import BytesIO

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None


def safe_close(conn, cur=None):
    try:
        if cur:
            cur.close()
    except Exception:
        pass

    try:
        if conn:
            db_pool.putconn(conn, close=False)
    except Exception:
        pass

@app.on_event("shutdown")
def shutdown():
    global db_pool
    try:
        if db_pool:
            db_pool.closeall()
            db_pool = None
    except:
        pass


PASSWORD = "morava"

USERS = [
    ("Lukas", "Lukáš"),
    ("Jirka", "Jirka"),
    ("Milan", "Milan"),
]

# ================= DB =================


def get_conn():
    if db_pool is None:
        raise Exception("DB NOT CONNECTED")

    return db_pool.getconn()

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

    try:
        db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL + "?sslmode=require"
        )

        print("DB POOL READY")

        init_db()  # ← TADY se vytvoří tabulky

    except Exception as e:
        print("DB INIT FAILED:", e)
        db_pool = None# 

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

@app.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie("user")
    r.delete_cookie("mode")
    r.delete_cookie("auth")
    return r

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
def home(request: Request, auth: str = Cookie(default=None)):
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
    body{{background:#0f1115;color:#e6e6e6;font-family:Inter,Arial;margin:0}}

    .topbar{{
        position:sticky;
        top:0;
        background:#0b0e13;
        padding:10px 16px;
        display:flex;
        justify-content:space-between;
        align-items:center;
        border-bottom:1px solid #1f2633;
        z-index:1000;
    }}

    .menu{{
        display:flex;
        gap:8px;
        padding:10px 16px;
        border-bottom:1px solid #1f2633;
        background:#0f1115;
    }}

    .btn{{
        background:#1c2330;
        border:none;
        color:#fff;
        padding:7px 14px;
        border-radius:8px;
        cursor:pointer;
        font-weight:600;
        transition:0.15s;
    }}

    .btn:hover{{background:#2a3446}}

    .content{{padding:18px}}

    .cards{{display:flex;gap:10px;margin-bottom:15px}}

    .card{{
        background:#151a23;
        padding:14px;
        border-radius:12px;
        min-width:120px;
        text-align:center;
        box-shadow:0 0 0 1px #1f2633;
    }}

    .title-small{{color:#9aa4b2;font-size:12px;margin-bottom:4px}}
    .value-big{{font-size:20px;font-weight:700}}

    </style>
    </head>

    <body>
    """

    # ===== HORNÍ BAR =====
    user = request.cookies.get("user", "Neznámý")
    mode = request.cookies.get("mode", "driver")
    mode_label = "SKLAD" if mode == "sklad" else "ŘIDIČ"

    html += f"""
    <div class="topbar">

        <div>
            👤 <b>{user}</b> &nbsp; | &nbsp; Režim: <b>{mode_label}</b>
        </div>

        <div>
            <a href="/logout">
                <button class="btn">Přepnout uživatele</button>
            </a>
        </div>

    </div>
    """

     # ===== MENU =====
    html += '<div class="menu">'
    html += '<a href="/"><button class="btn">Dashboard</button></a>'
    html += '<a href="/all"><button class="btn">Sklad-Kancl</button></a>'
    html += '<a href="/low"><button class="btn">Nízký stav</button></a>'
    html += '<a href="/export/products"><button class="btn">Excel Produkty</button></a>'
    html += '<a href="/export/low"><button class="btn">Excel Nízký stav</button></a>'

    if mode == "driver":
        html += '<a href="/car"><button class="btn">Auto</button></a>'

    html += '<a href="/history"><button class="btn">Historie</button></a>'
    html += '<a href="/cars"><button class="btn">Všechna auta</button></a>'
    html += '</div>'

    html += '<div class="content">'

    # ===== KARTY =====
    html += f"""
    <div class="cards">

        <div class="card">
            <div class="title-small">Produkty</div>
            <div class="value-big">{total_products}</div>
        </div>

        <div class="card">
            <div class="title-small">Nízký stav</div>
            <div class="value-big">{low_products}</div>
        </div>

        <div class="card">
            <div class="title-small">Dnes pohyby</div>
            <div class="value-big">{today_moves}</div>
        </div>

        <div class="card">
            <div class="title-small">Výrobci</div>
            <div class="value-big">{manufacturers}</div>
        </div>

    </div>
    """

    html += """
    <canvas id="bar"></canvas>

    <h3>Historie podle výrobce</h3>
    <select id="man"></select>
    <canvas id="line"></canvas>

    </div>

    <script>
    const labels=%s;
    const values=%s;

    new Chart(document.getElementById('bar'),{
        type:'bar',
        data:{labels:labels,datasets:[{data:values}]}
    });

    async function loadMan(){
        const r=await fetch('/api/manufacturers');
        const data=await r.json();
        let s=document.getElementById('man');
        data.forEach(m=>{
            let o=document.createElement('option');
            o.value=m;
            o.textContent=m;
            s.appendChild(o);
        });
        if(data.length)loadGraph(data[0]);
    }

    async function loadGraph(m){
        const r=await fetch('/api/history/'+m);
        const j=await r.json();
        let labels=[],datasets=[];
        Object.keys(j).forEach((k,i)=>{
            if(labels.length==0)labels=j[k].t;
            datasets.push({label:k,data:j[k].v,fill:false});
        });
        if(window.l)window.l.destroy();
        window.l=new Chart(document.getElementById('line'),{type:'line',data:{labels:labels,datasets:datasets}});
    }

    document.getElementById('man').onchange=e=>loadGraph(e.target.value);
    loadMan();
    </script>

    </body>
    </html>
    """ % (json.dumps(labels), json.dumps(values))        
   
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
def car(request: Request, auth: str = Cookie(default=None), user: str = Cookie(default=None)):
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
        SELECT c.code, p.name, c.quantity
        FROM car_stock c
        JOIN products p ON p.code = c.code
        WHERE c.user_name=%s
        ORDER BY c.code
    """, (user,))
    rows = cur.fetchall()

    html = """
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    body{background:#0f1115;color:#eee;font-family:Arial;margin:0;padding:20px}
    table{width:100%;border-collapse:collapse}
    th,td{padding:10px;border-bottom:1px solid #222}
    button{background:#2b3445;color:#fff;border:none;padding:6px 10px;border-radius:6px;cursor:pointer}
    button:hover{background:#3b4760}
    </style>
    </head>
    <body>
    """

    # ===== HLAVIČKA =====
    mode = request.cookies.get("mode", "driver")
    mode_label = "SKLAD" if mode == "sklad" else "ŘIDIČ"

    html += f"""
    <div style="margin-bottom:15px">
        👤 <b>{user}</b> | Režim: <b>{mode_label}</b>
    </div>

    <a href="/"><button>Zpět</button></a>

    <h2>Auto — {user}</h2>

    <table>
    <tr><th>Kód</th><th>Název</th><th>Množství</th><th>Akce</th></tr>
    """

    if not rows:
        html += "<tr><td colspan=3 style='color:#777'>Prázdné auto</td></tr>"
    else:
        for code, name, qty in rows:
            html += f"""
            <tr>
                <td>{code}</td>
                <td>{name}</td>
                <td>{qty}</td>
                <td>
                    <form method="post" action="/use_from_car" style="display:inline">
                        <input type="hidden" name="code" value="{code}">
                        <button>Použito</button>
                    </form>
                </td>
            </tr>
            """

    html += """
    </table>
    </body>
    </html>
    """

    safe_close(conn, cur)
    return HTMLResponse(html)

@app.get("/cars", response_class=HTMLResponse)
def cars(request: Request, auth: str = Cookie(default=None)):
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
    """

    # ===== HLAVIČKA =====
    user = request.cookies.get("user", "Neznámý")
    mode = request.cookies.get("mode", "driver")
    mode_label = "SKLAD" if mode == "sklad" else "ŘIDIČ"

    html += f"""
    <div style="
    position:sticky;
    top:0;
    background:#0f1115;
    padding:6px 12px;
    border-bottom:1px solid #222;
    display:flex;
    justify-content:space-between;
    align-items:center;
    font-size:13px;
    ">
 
    <div>
    Uživatel: <b>{user}</b> | Režim: <b>{mode_label}</b>
    </div>

    <div>
    <a href="/logout">
    <button style="
    background:#1f2937;
    color:#fff;
    border:none;
    padding:6px 12px;
    border-radius:8px;
    font-size:12px;
    cursor:pointer;
    ">
    Přepnout uživatele
    </button>
    </a>
    </div>

    </div>

    <a href="/"><button>Zpět</button></a>
    <h2>🚗 Všechna auta</h2>

    <div class="grid">
    """

    for key, label in USERS:

        html += f"<div class='card'><h3>{label}</h3>"
        html += "<table>"
        html += "<tr><th>Kód</th><th>Název</th><th>Množství</th></tr>"

        cur.execute("""
            SELECT c.code, p.name, c.quantity
            FROM car_stock c
            JOIN products p ON p.code = c.code
            WHERE c.user_name=%s
            ORDER BY c.code
        """, (key,))


        rows = cur.fetchall()

        if not rows:
            html += "<tr><td colspan=2 style='color:#777'>Prázdné auto</td></tr>"
        else:
            for code, name, qty in rows:
                html += f"<tr><td>{code}</td><td>{name}</td><td>{qty}</td></tr>"

        html += "</table></div>"

    html += """
    </div>
    </body>
    </html>
    """

    safe_close(conn, cur)
    return HTMLResponse(html)

@app.get("/export/products")
def export_products(auth: str = Cookie(default=None)):

    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT code, name, manufacturer, quantity, min_limit
        FROM products
        ORDER BY manufacturer, name
    """)
    rows = cur.fetchall()
    safe_close(conn, cur)

    wb = Workbook()
    wb.remove(wb.active)

    sheets = {}

    for code, name, manufacturer, qty, minl in rows:

        man = manufacturer or "Neznámý"

        if man not in sheets:
            ws = wb.create_sheet(title=man[:31])
            ws.append(["Kód", "Název", "Množství", "Min. limit"])
            sheets[man] = ws

        sheets[man].append([code, name, qty, minl])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=produkty.xlsx"}
    )

@app.get("/export/low")
def export_low(auth: str = Cookie(default=None)):

    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT code, name, manufacturer, quantity, min_limit
        FROM products
        WHERE quantity <= min_limit
        ORDER BY manufacturer, name
    """)
    rows = cur.fetchall()
    safe_close(conn, cur)

    wb = Workbook()
    wb.remove(wb.active)

    sheets = {}

    for code, name, manufacturer, qty, minl in rows:

        man = manufacturer or "Neznámý"

        if man not in sheets:
            ws = wb.create_sheet(title=man[:31])
            ws.append(["Kód", "Název", "Množství", "Min. limit"])
            sheets[man] = ws

        sheets[man].append([code, name, qty, minl])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=nizky_stav.xlsx"}
    )

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

@app.post("/use_from_car")
def use_from_car(code: str = Form(...),
                 user: str = Cookie(default=None),
                 auth: str = Cookie(default=None)):

    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE car_stock
        SET quantity = quantity - 1
        WHERE user_name=%s AND code=%s AND quantity > 0
    """, (user, code))

    cur.execute("""
        DELETE FROM car_stock
        WHERE user_name=%s AND code=%s AND quantity <= 0
    """, (user, code))

    conn.commit()
    safe_close(conn, cur)

    return RedirectResponse("/car", status_code=303)

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

@app.post("/choose_car")
def choose_car(code: str = Form(...), auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    html = """
    <html><head><meta charset="utf-8">
    <style>
    body{background:#111;color:#eee;font-family:Arial;text-align:center;padding:40px}
    button{padding:10px 20px;margin:10px;border:none;border-radius:8px;background:#2b5;color:#fff;font-size:16px}
    </style>
    </head><body>
    <h2>Vyber auto</h2>
    """

    for key, label in USERS:
        html += f"""
        <form method="post" action="/to_car">
            <input type="hidden" name="code" value="{code}">
            <input type="hidden" name="user" value="{key}">
            <button>{label}</button>
        </form>
        """

    html += "</body></html>"
    return HTMLResponse(html)

@app.post("/use_from_car")
def use_from_car(code: str = Form(...), user: str = Cookie(default=None)):
    import urllib.parse

    if user:
        user = urllib.parse.unquote(user)

    if not user:
        return RedirectResponse("/login", status_code=303)

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        # odečti z auta
        cur.execute("""
            UPDATE car_stock
            SET quantity = quantity - 1
            WHERE user_name=%s AND code=%s AND quantity > 0
            RETURNING quantity
        """, (user, code))

        if cur.fetchone() is None:
            conn.commit()
            return RedirectResponse("/car", status_code=303)

        # log pohybu
        cur.execute("""
            INSERT INTO movements(code, change, user_name)
            VALUES(%s, %s, %s)
        """, (code, -1, user))

        conn.commit()

    finally:
        safe_close(conn, cur)

    return RedirectResponse("/car", status_code=303)

@app.post("/to_car")
def to_car(code: str = Form(...),
           user: str = Form(None),
           cookie_user: str = Cookie(default=None),
           auth: str = Cookie(default=None)):

    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    import urllib.parse

    final_user = None

    if user:
        final_user = urllib.parse.unquote(user)
    elif cookie_user:
        final_user = urllib.parse.unquote(cookie_user)

    if not final_user:
        return RedirectResponse("/all", status_code=303)
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
        """, (final_user, code))

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        return HTMLResponse(f"<h1>DB ERROR</h1><pre>{e}</pre>", status_code=500)

    finally:
        safe_close(conn, cur)

    return RedirectResponse("/all", status_code=303)



# ================= PRODUCTS =================
@app.get("/all", response_class=HTMLResponse)
def all_products(request: Request,
                 auth: str = Cookie(default=None),
                 mode: str = Cookie(default="driver"),
                 q: str = None):

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
        grouped[row[2]].append(row)

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
    """

    # ===== HLAVIČKA =====
    user = request.cookies.get("user", "Neznámý")
    mode_label = "SKLAD" if mode == "sklad" else "ŘIDIČ"

    html += f"""
    <div style="position:sticky;top:0;background:#0f1115;
    padding:6px 12px;border-bottom:1px solid #222;
    display:flex;justify-content:space-between;align-items:center;font-size:13px;">

        <div>Uživatel: <b>{user}</b> | Režim: <b>{mode_label}</b></div>

        <div>
            <a href="/login">
                <button style="background:#333;padding:4px 10px;border-radius:6px">
                Přepnout uživatele
                </button>
            </a>
        </div>
    </div>
    """

    # ===== MENU =====
    html += '<div class="top">'
    html += '<a href="/"><button>Dashboard</button></a>'
    html += '<a href="/low"><button>Nízký stav</button></a>'

    if mode == "driver":
        html += '<a href="/car"><button>Auto</button></a>'

    html += '<a href="/history"><button>Historie</button></a>'
    html += '<a href="/cars"><button>Všechna auta</button></a>'
    html += '</div>'

    # ===== FORMULÁŘE =====
    html += f"""
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
        <input name="q" placeholder="Hledáš něco?" value="{q if q else ''}">
        <button type="submit">Hledat</button>
        <a href="/all"><button type="button">Vyčistit filtr</button></a>
    </form>
    </div>
    """

    html += """
    <div style="margin-bottom:15px">

        <a href="/export/products">
            <button>Export vše</button>
        </a>

        <a href="/export/low">
            <button style="background:#802020">Export nízký stav</button>
        </a>

    </div>
    """

    # ===== TABULKY =====
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
            """

            # ===== SKLAD =====
            if mode == "sklad":

                # + / -
                html += f"""
                <form method="post" action="/change" style="display:inline">
                    <input type="hidden" name="code" value="{code}">
                    <button name="type" value="add">+</button>
                    <button name="type" value="sub">-</button>
                </form>
                """

                # SMAZAT
                html += f"""
                <form method="post" action="/delete_by_code" style="display:inline"
                onsubmit="return confirm('Opravdu smazat produkt?');">
                    <input type="hidden" name="code" value="{code}">
                    <button style="background:#802020">Smazat</button>
                </form>
                """

                # POPUP výběr auta
                html += f"""
                <div style="display:inline;position:relative">

                    <button onclick="togglePopup('p{code}')" style="background:#205080">
                        Auto
                    </button>

                    <div id="p{code}" style="
                        display:none;
                        position:absolute;
                        background:#1b1f27;
                        border:1px solid #333;
                        border-radius:8px;
                        padding:6px;
                        top:28px;
                        left:0;
                        z-index:999;
                        min-width:120px;
                    ">
                """

                for key, label in USERS:
                    html += f"""
                    <form method="post" action="/to_car" style="margin:2px">
                        <input type="hidden" name="code" value="{code}">
                        <input type="hidden" name="user" value="{key}">
                        <button style="width:100%;background:#2b3445">{label}</button>
                    </form>
                    """

                html += "</div></div>"

            # ===== ŘIDIČ =====
            elif mode == "driver":

                html += f"""
                <form method="post" action="/to_car" style="display:inline">
                    <input type="hidden" name="code" value="{code}">
                    <button style="background:#205080">Auto</button>
                </form>
                """

            html += """
                </td>
            </tr>
            """

        html += "</table>"
    # ===== SCRIPT =====
    html += """
    <script>
    function togglePopup(id){
        var el = document.getElementById(id);
        if(el.style.display === "block"){
            el.style.display = "none";
        } else {
            el.style.display = "block";
        }
    }
    </script>
    """

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
def history(request: Request, auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT m.code,
                   p.name,
                   m.change,
                   m.created_at,
                   COALESCE(m.user_name, 'Unknown')
            FROM movements m
            LEFT JOIN products p ON p.code = m.code
            ORDER BY m.created_at DESC
            LIMIT 200
        """)
        rows = cur.fetchall()

    except Exception as e:
        print("HISTORY ERROR:", e)
        return HTMLResponse(f"<h1>DB ERROR</h1><pre>{e}</pre>", status_code=500)

    finally:
        safe_close(conn, cur)

    html = """
    <html>
    <head>
    <meta charset="utf-8">
    <style>
    body{background:#0f1115;color:#eee;font-family:Inter;margin:0;padding:20px}
    table{width:100%;border-collapse:collapse}
    th,td{padding:10px;border-bottom:1px solid #222}
    th{background:#151922;text-align:left}
    button{background:#2b3445;color:#fff;border:none;padding:6px 12px;border-radius:8px;cursor:pointer}
    button:hover{background:#3b4760}
    .topbar{
        position:sticky;
        top:0;
        background:#0f1115;
        padding:6px 12px;
        border-bottom:1px solid #222;
        display:flex;
        justify-content:space-between;
        align-items:center;
        font-size:13px;
    }
    </style>
    </head>
    <body>
    """

    # horní lišta
    user = request.cookies.get("user", "Neznámý")
    mode = request.cookies.get("mode", "driver")
    mode_label = "SKLAD" if mode == "sklad" else "ŘIDIČ"

    html += f"""
    <div class="topbar">
        <div>
            👤 <b>{user}</b> | Režim: <b>{mode_label}</b>
        </div>
        <div>
            <a href="/"><button>Zpět</button></a>
        </div>
    </div>
    """

    html += "<h2 style='margin-top:20px'>📜 Posledních 200 pohybů</h2>"
    html += "<table>"
    html += "<tr><th>Kód</th><th>Název</th><th>Změna</th><th>Datum</th><th>Uživatel</th></tr>"

    for code, name, change, date, user_name in rows:

        col = "lime" if change > 0 else "red"
        name = name or "-"

        html += f"""
        <tr>
            <td>{code}</td>
            <td>{name}</td>
            <td style='color:{col};font-weight:bold'>{change}</td>
            <td>{date}</td>
            <td>{user_name}</td>
        </tr>
        """

    html += "</table></body></html>"

    return HTMLResponse(html)