
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify, flash
import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "fitness.db")
SECRET_KEY = "dev_secret_key_change_me"

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["DATABASE"] = DB_PATH

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    db.commit()
    # insert sample users if none
    cur = db.execute("SELECT COUNT(*) as c FROM users")
    if cur.fetchone()["c"] == 0:
        now = datetime.utcnow().isoformat()
        users = [("alice", now), ("bob", now), ("carol", now)]
        db.executemany("INSERT INTO users (username, created_at) VALUES (?, ?)", users)
        db.commit()

@app.before_first_request
def setup():
    if not os.path.exists(DB_PATH):
        init_db()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# simple "login" - choose username
@app.route("/", methods=["GET","POST"])
def index():
    db = get_db()
    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            flash("Please enter a username.")
            return redirect(url_for("index"))
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            cur = db.execute("INSERT INTO users (username, created_at) VALUES (?, ?)", (username, datetime.utcnow().isoformat()))
            db.commit()
            user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))
    users = db.execute("SELECT * FROM users ORDER BY username").fetchall()
    return render_template("index.html", users=users)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    db = get_db()
    goals = db.execute("SELECT * FROM goals WHERE user_id = ?", (user["id"],)).fetchall()
    friends = db.execute("""SELECT u.* FROM users u JOIN friends f ON ( (f.user_id = ? AND f.friend_id = u.id) OR (f.friend_id = ? AND f.user_id = u.id) )""", (user["id"], user["id"])).fetchall()
    posts = db.execute("SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id ORDER BY p.created_at DESC LIMIT 20").fetchall()
    return render_template("dashboard.html", user=user, goals=goals, friends=friends, posts=posts)

# Goals
@app.route("/goals", methods=["GET","POST"])
def goals():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name")
        target = request.form.get("target")
        notes = request.form.get("notes")
        db.execute("INSERT INTO goals (user_id, name, target, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                   (user["id"], name, target, notes, datetime.utcnow().isoformat()))
        db.commit()
        return redirect(url_for("goals"))
    goals = db.execute("SELECT * FROM goals WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)).fetchall()
    return render_template("goals.html", user=user, goals=goals)

@app.route("/goals/delete/<int:gid>", methods=["POST"])
def delete_goal(gid):
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    db = get_db()
    db.execute("DELETE FROM goals WHERE id = ? AND user_id = ?", (gid, user["id"]))
    db.commit()
    return redirect(url_for("goals"))

# Records
@app.route("/records", methods=["GET","POST"])
def records():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    db = get_db()
    if request.method == "POST":
        date = request.form.get("date") or datetime.utcnow().date().isoformat()
        activity = request.form.get("activity")
        value = request.form.get("value")
        share = request.form.get("share")  # none / friends / community
        db.execute("INSERT INTO records (user_id, date, activity, value, created_at, shared) VALUES (?, ?, ?, ?, ?, ?)",
                   (user["id"], date, activity, value, datetime.utcnow().isoformat(), share))
        db.commit()
        # if shared -> create post
        if share in ("friends", "community"):
            content = f"{user['username']} logged {activity}: {value} on {date}"
            db.execute("INSERT INTO posts (user_id, content, visibility, created_at) VALUES (?, ?, ?, ?)",
                       (user["id"], content, share, datetime.utcnow().isoformat()))
            db.commit()
        return redirect(url_for("records"))
    records = db.execute("SELECT * FROM records WHERE user_id = ? ORDER BY date DESC LIMIT 100", (user["id"],)).fetchall()
    # prepare data for chart (aggregate by activity)
    chart_data = {}
    rows = db.execute("SELECT date, activity, value FROM records WHERE user_id = ? ORDER BY date ASC", (user["id"],)).fetchall()
    for r in rows:
        act = r["activity"]
        chart_data.setdefault(act, []).append({"date": r["date"], "value": float(r["value"])})
    return render_template("records.html", user=user, records=records, chart_data=chart_data)

# API to fetch chart data (for Chart.js)
@app.route("/api/chart_data")
def chart_data():
    user = current_user()
    if not user:
        return jsonify({"error":"not logged in"}), 403
    db = get_db()
    rows = db.execute("SELECT date, activity, value FROM records WHERE user_id = ? ORDER BY date ASC", (user["id"],)).fetchall()
    out = {}
    for r in rows:
        act = r["activity"]
        out.setdefault(act, []).append({"date": r["date"], "value": float(r["value"])})
    return jsonify(out)

# Friends / connections
@app.route("/friends", methods=["GET","POST"])
def friends():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    db = get_db()
    if request.method == "POST":
        other = request.form.get("other")
        if not other:
            flash("Please select a user to connect.")
            return redirect(url_for("friends"))
        other_user = db.execute("SELECT * FROM users WHERE id = ?", (other,)).fetchone()
        if not other_user:
            flash("User not found.")
            return redirect(url_for("friends"))
        # create friend entry if not exist
        exists = db.execute("SELECT * FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
                            (user["id"], other_user["id"], other_user["id"], user["id"])).fetchone()
        if not exists:
            db.execute("INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)", (user["id"], other_user["id"], datetime.utcnow().isoformat()))
            db.commit()
            flash(f"Connected with {other_user['username']}.")
        else:
            flash("Already connected.")
        return redirect(url_for("friends"))
    # list all users and current friends
    all_users = db.execute("SELECT * FROM users WHERE id != ? ORDER BY username", (user["id"],)).fetchall()
    friends = db.execute("""SELECT u.* FROM users u JOIN friends f ON ( (f.user_id = ? AND f.friend_id = u.id) OR (f.friend_id = ? AND f.user_id = u.id) )""", (user["id"], user["id"])).fetchall()
    return render_template("friends.html", user=user, all_users=all_users, friends=friends)

@app.route("/unfriend/<int:uid>", methods=["POST"])
def unfriend(uid):
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    db = get_db()
    db.execute("DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)", (user["id"], uid, uid, user["id"]))
    db.commit()
    return redirect(url_for("friends"))

# Community feed
@app.route("/feed")
def feed():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    db = get_db()
    # show community posts and posts from friends
    friends_ids = [r["id"] for r in db.execute("""SELECT u.id FROM users u JOIN friends f ON ( (f.user_id = ? AND f.friend_id = u.id) OR (f.friend_id = ? AND f.user_id = u.id) )""", (user["id"], user["id"])).fetchall()]
    placeholders = ",".join("?" for _ in friends_ids) if friends_ids else "NULL"
    params = []
    query = "SELECT p.*, u.username FROM posts p JOIN users u ON u.id = p.user_id WHERE 1=1 "
    # community posts always visible
    query += " AND (p.visibility = 'community' OR p.user_id = ?"
    params.append(user["id"])
    if friends_ids:
        query += " OR p.user_id IN (" + placeholders + ")"
        params.extend(friends_ids)
    query += ") ORDER BY p.created_at DESC LIMIT 100"
    params = tuple(params)
    posts = db.execute(query, params).fetchall()
    return render_template("feed.html", user=user, posts=posts)

# create ad-hoc post
@app.route("/post", methods=["POST"])
def post():
    user = current_user()
    if not user:
        return redirect(url_for("index"))
    content = request.form.get("content")
    visibility = request.form.get("visibility") or "friends"
    db = get_db()
    db.execute("INSERT INTO posts (user_id, content, visibility, created_at) VALUES (?, ?, ?, ?)",
               (user["id"], content, visibility, datetime.utcnow().isoformat()))
    db.commit()
    return redirect(url_for("dashboard"))

# simple user api
@app.route("/api/users")
def api_users():
    db = get_db()
    users = db.execute("SELECT id, username FROM users ORDER BY username").fetchall()
    return jsonify([dict(u) for u in users])

if __name__ == "__main__":
    app.run(debug=True)
