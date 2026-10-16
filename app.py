from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3, os
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
DB_PATH = os.path.join(os.path.dirname(__file__), "coffee_shop.db")
ADMIN_USER = os.environ.get("SHOP_ADMIN_USER", "owner")
ADMIN_PASSWORD = os.environ.get("SHOP_ADMIN_PASSWORD", "change-me-now")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Coffee',
            price REAL NOT NULL CHECK(price >= 0), stock INTEGER NOT NULL DEFAULT 0,
            sku TEXT UNIQUE, active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL DEFAULT 'Walk-in customer',
            payment_method TEXT NOT NULL DEFAULT 'Cash',
            subtotal REAL NOT NULL, tax REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Completed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name TEXT NOT NULL, quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL, line_total REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'General',
            amount REAL NOT NULL CHECK(amount >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        count = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            sample = [
                ("Velvet Cappuccino","Coffee",160,34,"CF-001"),
                ("Oat Milk Latte","Coffee",190,28,"CF-002"),
                ("Cold Brew","Iced",175,22,"IC-001"),
                ("Caramel Macchiato","Coffee",210,18,"CF-003"),
                ("Matcha Cloud","Tea",220,14,"TE-001"),
                ("Butter Croissant","Bakery",110,20,"BK-001"),
                ("Blueberry Muffin","Bakery",125,16,"BK-002"),
                ("Classic Espresso","Coffee",120,40,"CF-004")
            ]
            con.executemany("INSERT INTO products(name,category,price,stock,sku) VALUES(?,?,?,?,?)", sample)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error":"Please sign in again."}), 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        if username == ADMIN_USER and password == ADMIN_PASSWORD:
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        error = "Incorrect username or password."
    return render_template("login.html", error=error)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username","owner"))

@app.get("/api/stats")
@login_required
def stats():
    today = date.today().isoformat()
    with db() as con:
        sales = con.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE date(created_at)=?", (today,)).fetchone()[0]
        orders = con.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=?", (today,)).fetchone()[0]
        items = con.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
        low = con.execute("SELECT COUNT(*) FROM products WHERE active=1 AND stock<=5").fetchone()[0]
        month_sales = con.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now','localtime')").fetchone()[0]
        costs = con.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now','localtime')").fetchone()[0]
        recent = con.execute("SELECT id,customer,total,payment_method,status,created_at FROM orders ORDER BY id DESC LIMIT 7").fetchall()
        best = con.execute("""SELECT product_name, SUM(quantity) qty FROM order_items
                              GROUP BY product_name ORDER BY qty DESC LIMIT 5""").fetchall()
        week = con.execute("""SELECT date(created_at) day, SUM(total) total FROM orders
                              WHERE date(created_at)>=date('now','localtime','-6 days')
                              GROUP BY date(created_at) ORDER BY day""").fetchall()
    return jsonify({"today_sales":sales,"today_orders":orders,"products":items,"low_stock":low,
                    "month_sales":month_sales,"month_expenses":costs,
                    "recent":[dict(x) for x in recent],"best":[dict(x) for x in best],
                    "week":[dict(x) for x in week]})

@app.get("/api/products")
@login_required
def products():
    with db() as con:
        rows = con.execute("SELECT * FROM products WHERE active=1 ORDER BY category,name").fetchall()
    return jsonify([dict(x) for x in rows])

@app.post("/api/products")
@login_required
def add_product():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name","")).strip()
    category = str(data.get("category","Coffee")).strip() or "Coffee"
    sku = str(data.get("sku","")).strip() or None
    try:
        price, stock = float(data.get("price",0)), int(data.get("stock",0))
        if not name or price < 0 or stock < 0: raise ValueError()
        with db() as con:
            cur = con.execute("INSERT INTO products(name,category,price,stock,sku) VALUES(?,?,?,?,?)",
                              (name,category,price,stock,sku))
            pid = cur.lastrowid
            row = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        return jsonify(dict(row)), 201
    except sqlite3.IntegrityError:
        return jsonify({"error":"That SKU already exists. Use a unique SKU."}), 400
    except (ValueError, TypeError):
        return jsonify({"error":"Enter a product name, valid price and whole-number stock."}), 400

@app.put("/api/products/<int:pid>")
@login_required
def update_product(pid):
    data = request.get_json(silent=True) or {}
    try:
        with db() as con:
            old = con.execute("SELECT * FROM products WHERE id=? AND active=1",(pid,)).fetchone()
            if not old: return jsonify({"error":"Product not found."}),404
            name = str(data.get("name",old["name"])).strip()
            category = str(data.get("category",old["category"])).strip()
            price = float(data.get("price",old["price"]))
            stock = int(data.get("stock",old["stock"]))
            sku = str(data.get("sku",old["sku"] or "")).strip() or None
            if not name or price < 0 or stock < 0: raise ValueError()
            con.execute("UPDATE products SET name=?,category=?,price=?,stock=?,sku=? WHERE id=?",
                        (name,category,price,stock,sku,pid))
            row = con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
        return jsonify(dict(row))
    except sqlite3.IntegrityError:
        return jsonify({"error":"That SKU already exists."}),400
    except (ValueError,TypeError):
        return jsonify({"error":"Check the product details and try again."}),400

@app.delete("/api/products/<int:pid>")
@login_required
def delete_product(pid):
    with db() as con:
        cur = con.execute("UPDATE products SET active=0 WHERE id=?",(pid,))
        if not cur.rowcount: return jsonify({"error":"Product not found."}),404
    return jsonify({"ok":True})

@app.post("/api/orders")
@login_required
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    customer = str(data.get("customer","Walk-in customer")).strip() or "Walk-in customer"
    payment = str(data.get("payment_method","Cash"))
    if payment not in ("Cash","UPI","Card"): return jsonify({"error":"Invalid payment method."}),400
    if not isinstance(items,list) or not items: return jsonify({"error":"Add at least one item."}),400
    try:
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            resolved, subtotal = [], 0
            for item in items:
                pid, qty = int(item["product_id"]), int(item["quantity"])
                if qty < 1: raise ValueError("Quantity must be at least one.")
                p = con.execute("SELECT * FROM products WHERE id=? AND active=1",(pid,)).fetchone()
                if not p: raise ValueError("A selected product is no longer available.")
                if p["stock"] < qty: raise ValueError(f"Not enough stock for {p['name']}.")
                line = p["price"] * qty
                subtotal += line
                resolved.append((p,qty,line))
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            cur = con.execute("INSERT INTO orders(customer,payment_method,subtotal,tax,total) VALUES(?,?,?,?,?)",
                              (customer,payment,subtotal,tax,total))
            oid = cur.lastrowid
            for p,qty,line in resolved:
                con.execute("INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)",
                            (oid,p["id"],p["name"],qty,p["price"],line))
                con.execute("UPDATE products SET stock=stock-? WHERE id=?",(qty,p["id"]))
        return jsonify({"ok":True,"order_id":oid,"subtotal":round(subtotal,2),"tax":tax,"total":total}),201
    except (ValueError,KeyError,TypeError) as e:
        return jsonify({"error":str(e) or "Invalid order."}),400

@app.get("/api/orders")
@login_required
def list_orders():
    with db() as con:
        rows = con.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(x) for x in rows])

@app.get("/api/orders/<int:oid>")
@login_required
def order_detail(oid):
    with db() as con:
        order = con.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
        if not order: return jsonify({"error":"Order not found."}),404
        items = con.execute("SELECT * FROM order_items WHERE order_id=?",(oid,)).fetchall()
    return jsonify({"order":dict(order),"items":[dict(x) for x in items]})

@app.get("/api/expenses")
@login_required
def list_expenses():
    with db() as con:
        rows = con.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(x) for x in rows])

@app.post("/api/expenses")
@login_required
def add_expense():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title","")).strip()
    category = str(data.get("category","General")).strip() or "General"
    try:
        amount = float(data.get("amount",0))
        if not title or amount <= 0: raise ValueError()
        with db() as con:
            cur = con.execute("INSERT INTO expenses(title,category,amount) VALUES(?,?,?)",(title,category,amount))
            row = con.execute("SELECT * FROM expenses WHERE id=?",(cur.lastrowid,)).fetchone()
        return jsonify(dict(row)),201
    except (ValueError,TypeError):
        return jsonify({"error":"Enter an expense title and amount greater than zero."}),400

@app.get("/api/export/orders.csv")
@login_required
def export_orders():
    from flask import Response
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID","Date","Customer","Payment","Subtotal","Tax","Total","Status"])
    with db() as con:
        rows = con.execute("SELECT id,created_at,customer,payment_method,subtotal,tax,total,status FROM orders ORDER BY id DESC").fetchall()
    for row in rows: writer.writerow(list(row))
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=coffee-shop-orders.csv"})

init_db()
if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT",5000)))
