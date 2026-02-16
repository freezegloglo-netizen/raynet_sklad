print("APP FILE LOADED")

from fastapi import FastAPI, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
import psycopg2, os, io, json, datetime
from openpyxl import Workbook

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

PASSWORD = "morava"


# ================= DB =================
def get_conn():
    return psycopg2.connect(DATABASE_URL)


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

    cur.close()
    conn.close()

    html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
    body{{background:#111;color:#eee;font-family:Arial;margin:0;padding:20px}}
    .card{{background:#1b1b1b;padding:15px;border-radius:14px;margin-bottom:15px}}
    button{{background:#333;color:white;border:none;padding:6px 12px;border-radius:8px}}
    </style>
    </head>

    <body>

    <div class="card">
    📦 {total_products} | ⚠ {low_products} | 📈 {today_moves} | 🏭 {manufacturers}
    </div>

    <canvas id="bar"></canvas>

    <h3>Historie podle výrobce</h3>
    <select id="man"></select>
    <canvas id="line"></canvas>

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
        data.forEach(m=>{{let o=document.createElement('option');o.value=m;o.textContent=m;s.appendChild(o);}});
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

    <br>
    <a href="/all"><button>Produkty</button></a>
    <a href="/low"><button>Nízký stav</button></a>
    <a href="/history"><button>Historie</button></a>

    </body></html>
    """

    return HTMLResponse(html)


# ================= API =================
@app.get("/api/manufacturers")
def api_man():
    conn=get_conn()
    cur=conn.cursor()
    cur.execute("SELECT DISTINCT manufacturer FROM products ORDER BY manufacturer")
    data=[m[0] or "Neznámý" for m in cur.fetchall()]
    cur.close();conn.close()
    return data


@app.get("/api/history/{manufacturer}")
def api_hist(manufacturer:str):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute("""
    SELECT code,change,created_at FROM movements
    WHERE code IN (SELECT code FROM products WHERE manufacturer=%s)
    ORDER BY created_at
    """,(manufacturer,))
    rows=cur.fetchall()
    cur.close();conn.close()

    timeline={}
    for code,ch,ts in rows:
        timeline.setdefault(code,{"t":[],"v":[],"s":0})
        timeline[code]["s"]+=ch
        timeline[code]["t"].append(str(ts))
        timeline[code]["v"].append(timeline[code]["s"])
    return timeline


# ================= PRODUCTS =================
@app.get("/all", response_class=HTMLResponse)
def all_products(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn=get_conn()
    cur=conn.cursor()
    cur.execute("SELECT code,name,manufacturer,quantity,min_limit FROM products ORDER BY manufacturer,name")
    rows=cur.fetchall()
    cur.close();conn.close()

    html="<html><body style='background:#111;color:#eee;font-family:Arial'>"
    html+="<h2>Produkty</h2><a href='/'>Zpět</a><table border=1 width=100%>"
    html+="<tr><th>Kód</th><th>Název</th><th>Výrobce</th><th>Množství</th></tr>"

    for r in rows:
        html+=f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"

    html+="</table></body></html>"
    return HTMLResponse(html)


# ================= LOW =================
@app.get("/low", response_class=HTMLResponse)
def low(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn=get_conn()
    cur=conn.cursor()
    cur.execute("SELECT code,name,manufacturer,quantity FROM products WHERE quantity<=min_limit")
    rows=cur.fetchall()
    cur.close();conn.close()

    html="<html><body style='background:#111;color:#eee;font-family:Arial'>"
    html+="<h2>Nízký stav</h2><a href='/'>Zpět</a><table border=1 width=100%>"
    html+="<tr><th>Kód</th><th>Název</th><th>Výrobce</th><th>Množství</th></tr>"

    for r in rows:
        html+=f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td style='color:red'>{r[3]}</td></tr>"

    html+="</table></body></html>"
    return HTMLResponse(html)


# ================= HISTORY =================
@app.get("/history", response_class=HTMLResponse)
def history(auth: str = Cookie(default=None)):
    if auth != "ok":
        return RedirectResponse("/login", status_code=303)

    conn=get_conn()
    cur=conn.cursor()
    cur.execute("SELECT code,change,created_at FROM movements ORDER BY created_at DESC LIMIT 200")
    rows=cur.fetchall()
    cur.close();conn.close()

    html="<html><body style='background:#111;color:#eee;font-family:Arial'>"
    html+="<h2>Historie</h2><a href='/'>Zpět</a><table border=1 width=100%>"
    html+="<tr><th>Kód</th><th>Změna</th><th>Datum</th></tr>"

    for r in rows:
        col="lime" if r[1]>0 else "red"
        html+=f"<tr><td>{r[0]}</td><td style='color:{col}'>{r[1]}</td><td>{r[2]}</td></tr>"

    html+="</table></body></html>"
    return HTMLResponse(html)
