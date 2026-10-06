import os
from functools import wraps
from flask import Flask, jsonify, request, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db
from matching import score_match, label_for

FRONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app = Flask(__name__, static_folder=FRONT, static_url_path="")
app.secret_key = "giveloop-demo-secret-change-for-real-deployment"

CATEGORIES = ["Books", "Clothes", "School Supplies", "Electronics", "Furniture", "Toys",
              "Kitchen Items", "Household Items", "Medical Support Items", "Other"]
CONDITIONS = ["New", "Like New", "Good", "Usable"]
THRESHOLD = 60


# ---------- helpers ----------
def q(sql, args=(), one=False):
    c = get_db()
    rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    c.close()
    return (rows[0] if rows else None) if one else rows


def run(sql, args=()):
    c = get_db()
    cur = c.execute(sql, args)
    c.commit(); last = cur.lastrowid; c.close()
    return last


def err(msg, code=400):
    return jsonify({"error": msg}), code


def auth(*roles):
    def deco(f):
        @wraps(f)
        def wrap(*a, **k):
            if "uid" not in session:
                return err("Please log in first.", 401)
            if roles and session.get("role") not in roles:
                return err("You are not allowed to do that.", 403)
            return f(*a, **k)
        return wrap
    return deco


def pos_int(v):
    try:
        n = int(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def fulfilled(rid):
    r = q("""SELECT COALESCE(SUM(d.quantity),0) s FROM requests rq JOIN donations d ON d.id=rq.donation_id
             WHERE rq.requirement_id=? AND rq.status IN ('Accepted','Completed')""", (rid,), True)
    return r["s"]


def refresh_matches():
    """Store every suggested pair scoring >= threshold in the matches table."""
    c = get_db()
    ds = [dict(r) for r in c.execute("SELECT * FROM donations WHERE status IN ('Available','Requested')")]
    rs = [dict(r) for r in c.execute("SELECT * FROM requirements WHERE status='Open'")]
    for d in ds:
        for r in rs:
            s, why = score_match(d, r)
            if s >= THRESHOLD:
                c.execute("INSERT OR IGNORE INTO matches(donation_id,requirement_id,match_score,match_reason) VALUES(?,?,?,?)",
                          (d["id"], r["id"], s, "; ".join(why)))
    c.commit(); c.close()


def match_card(d, r, **extra):
    s, why = score_match(d, r)
    card = {"score": s, "label": label_for(s), "why": why, "donation_id": d["id"], "requirement_id": r["id"],
            "item_name": d["item_name"], "category": d["category"], "area": d["area"], "condition": d["condition"],
            "donation_qty": d["quantity"], "need_qty": r["quantity_needed"], "requirement_item": r["item_name"],
            "urgency": r["urgency"]}
    card.update(extra)
    return card


def req_matches(r):
    """Matching available donations for one requirement (dict), sorted by score."""
    ds = q("""SELECT d.*, u.name donor_name FROM donations d JOIN users u ON u.id=d.donor_id
              WHERE d.status IN ('Available','Requested')""")
    out = []
    for d in ds:
        card = match_card(d, r, party=d["donor_name"])
        already = q("SELECT 1 x FROM requests WHERE donation_id=? AND recipient_id=? AND status!='Rejected'",
                    (d["id"], r["recipient_id"]), True)
        card["already_requested"] = bool(already)
        card["donation_status"] = d["status"]
        if card["score"] >= THRESHOLD:
            out.append(card)
    return sorted(out, key=lambda x: -x["score"])


def groups_for_user():
    groups = []
    if session["role"] == "recipient":
        for r in q("SELECT * FROM requirements WHERE recipient_id=? ORDER BY id DESC", (session["uid"],)):
            groups.append({"title": f"{r['quantity_needed']} × {r['item_name']}", "area": r["area"], "urgency": r["urgency"],
                           "fulfilled": fulfilled(r["id"]), "needed": r["quantity_needed"], "status": r["status"],
                           "matches": req_matches(r) if r["status"] == "Open" else []})
    else:
        reqs = q("SELECT r.*, u.name recipient_name FROM requirements r JOIN users u ON u.id=r.recipient_id WHERE r.status='Open'")
        for d in q("SELECT * FROM donations WHERE donor_id=? AND status IN ('Available','Requested') ORDER BY id DESC", (session["uid"],)):
            ms = [match_card(d, r, party=r["recipient_name"]) for r in reqs]
            ms = sorted([m for m in ms if m["score"] >= THRESHOLD], key=lambda x: -x["score"])
            groups.append({"title": f"{d['quantity']} × {d['item_name']}", "area": d["area"], "status": d["status"],
                           "matches": ms})
    return groups


# ---------- pages ----------
@app.route("/")
def home():
    return send_from_directory(FRONT, "index.html")


# ---------- auth ----------
@app.post("/api/register")
def register():
    d = request.get_json(silent=True) or {}
    name, uname, pw = (d.get("name") or "").strip(), (d.get("username") or "").strip().lower(), d.get("password") or ""
    phone, area, role = (d.get("phone") or "").strip(), (d.get("area") or "").strip(), d.get("role")
    if not all([name, uname, pw, phone, area, role]):
        return err("Please enter all required fields.")
    if role not in ("donor", "recipient"):
        return err("Please choose Donor or Recipient.")
    if len(pw) < 6:
        return err("Password must be at least 6 characters.")
    digits = phone.replace("+", "").replace(" ", "")
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        return err("Please enter a valid phone number.")
    if q("SELECT 1 x FROM users WHERE username=?", (uname,), True):
        return err("That username is already taken.")
    run("INSERT INTO users(name,username,password_hash,phone,area,role) VALUES(?,?,?,?,?,?)",
        (name, uname, generate_password_hash(pw), phone, area, role))
    return jsonify({"message": "Account created! Please log in."}), 201


@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    uname, pw = (d.get("username") or "").strip().lower(), d.get("password") or ""
    if not uname or not pw:
        return err("Please enter all required fields.")
    u = q("SELECT * FROM users WHERE username=?", (uname,), True)
    if not u or not check_password_hash(u["password_hash"], pw):
        return err("Invalid username or password.", 401)
    session.update(uid=u["id"], role=u["role"], name=u["name"])
    return jsonify({"user": {"id": u["id"], "name": u["name"], "role": u["role"]}})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.get("/api/me")
def me():
    if "uid" not in session:
        return jsonify({"user": None})
    return jsonify({"user": {"id": session["uid"], "name": session["name"], "role": session["role"]}})


@app.get("/api/stats")
def public_stats():
    n = lambda s: q(s, (), True)["n"]
    return jsonify({"donations": n("SELECT COUNT(*) n FROM donations"),
                    "needs": n("SELECT COUNT(*) n FROM requirements WHERE status='Open'"),
                    "matches": n("SELECT COUNT(*) n FROM matches"),
                    "completed": n("SELECT COUNT(*) n FROM donations WHERE status='Completed'")})


# ---------- donations ----------
@app.get("/api/donations")
def list_donations():
    sql = "SELECT d.*, u.name donor_name FROM donations d JOIN users u ON u.id=d.donor_id WHERE 1=1"
    args = []
    if request.args.get("mine") and session.get("role") == "donor":
        sql += " AND d.donor_id=?"; args.append(session["uid"])
    else:
        sql += " AND d.status IN ('Available','Requested')"
    for key, col in (("category", "d.category"), ("condition", "d.condition")):
        if request.args.get(key):
            sql += f" AND {col}=?"; args.append(request.args[key])
    if request.args.get("location"):
        sql += " AND LOWER(d.area) LIKE ?"; args.append(f"%{request.args['location'].lower()}%")
    if request.args.get("q"):
        sql += " AND LOWER(d.item_name) LIKE ?"; args.append(f"%{request.args['q'].lower()}%")
    return jsonify(q(sql + " ORDER BY d.id DESC", args))


@app.post("/api/donations")
@auth("donor")
def add_donation():
    d = request.get_json(silent=True) or {}
    name, area = (d.get("item_name") or "").strip(), (d.get("area") or "").strip()
    qty = pos_int(d.get("quantity"))
    if not name or not area or not d.get("category") or not d.get("condition"):
        return err("Please enter all required fields.")
    if qty is None:
        return err("Quantity must be a whole number greater than 0.")
    if d["category"] not in CATEGORIES or d["condition"] not in CONDITIONS:
        return err("Invalid category or condition.")
    run("""INSERT INTO donations(donor_id,item_name,category,description,quantity,condition,area,image,notes)
           VALUES(?,?,?,?,?,?,?,?,?)""", (session["uid"], name, d["category"], d.get("description", ""), qty,
                                         d["condition"], area, (d.get("image") or "").strip(), d.get("notes", "")))
    refresh_matches()
    return jsonify({"message": "Your donation has been added to GiveLoop."}), 201


@app.put("/api/donations/<int:did>/complete")
@auth("donor", "recipient")
def complete(did):
    d = q("SELECT * FROM donations WHERE id=?", (did,), True)
    rq = q("SELECT * FROM requests WHERE donation_id=? AND status='Accepted'", (did,), True)
    if not d or not rq:
        return err("This donation has no accepted request to complete.", 404)
    if session["uid"] not in (d["donor_id"], rq["recipient_id"]):
        return err("You are not allowed to do that.", 403)
    run("UPDATE donations SET status='Completed' WHERE id=?", (did,))
    run("UPDATE requests SET status='Completed' WHERE id=?", (rq["id"],))
    run("UPDATE matches SET status='Completed' WHERE donation_id=? AND requirement_id=?", (did, rq["requirement_id"]))
    return jsonify({"message": "Donation marked as completed. Thank you for closing the loop!"})


# ---------- requirements ----------
@app.get("/api/requirements")
def list_requirements():
    sql = "SELECT r.*, u.name recipient_name FROM requirements r JOIN users u ON u.id=r.recipient_id WHERE 1=1"
    args = []
    if request.args.get("mine") and session.get("role") == "recipient":
        sql += " AND r.recipient_id=?"; args.append(session["uid"])
    else:
        sql += " AND r.status='Open'"
    rows = q(sql + " ORDER BY CASE r.urgency WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, r.id DESC", args)
    for r in rows:
        r["fulfilled"] = fulfilled(r["id"])
    return jsonify(rows)


@app.post("/api/requirements")
@auth("recipient")
def add_requirement():
    d = request.get_json(silent=True) or {}
    name, area = (d.get("item_name") or "").strip(), (d.get("area") or "").strip()
    qty = pos_int(d.get("quantity_needed"))
    if not name or not area or not d.get("category") or not d.get("condition_required") or not d.get("urgency"):
        return err("Please enter all required fields.")
    if qty is None:
        return err("Quantity needed must be a whole number greater than 0.")
    if d["category"] not in CATEGORIES or d["condition_required"] not in CONDITIONS or d["urgency"] not in ("Low", "Medium", "High"):
        return err("Invalid category, condition or urgency.")
    run("""INSERT INTO requirements(recipient_id,item_name,category,description,quantity_needed,condition_required,area,urgency,purpose)
           VALUES(?,?,?,?,?,?,?,?,?)""", (session["uid"], name, d["category"], d.get("description", ""), qty,
                                         d["condition_required"], area, d["urgency"], d.get("purpose", "")))
    refresh_matches()
    return jsonify({"message": "Your requirement has been posted on GiveLoop."}), 201


# ---------- matches ----------
@app.get("/api/matches/<int:rid>")
@auth("recipient", "admin")
def matches_for(rid):
    r = q("SELECT * FROM requirements WHERE id=?", (rid,), True)
    if not r:
        return err("Requirement not found.", 404)
    if session["role"] == "recipient" and r["recipient_id"] != session["uid"]:
        return err("You are not allowed to do that.", 403)
    return jsonify({"requirement": r, "fulfilled": fulfilled(rid), "matches": req_matches(r)})


@app.get("/api/my-matches")
@auth("donor", "recipient")
def my_matches():
    return jsonify(groups_for_user())


# ---------- requests ----------
@app.get("/api/requests")
@auth("donor", "recipient")
def list_requests():
    col = "d.donor_id" if session["role"] == "donor" else "rq.recipient_id"
    return jsonify(q(f"""SELECT rq.*, d.item_name, d.quantity, d.donor_id, du.name donor_name, ru.name recipient_name
        FROM requests rq JOIN donations d ON d.id=rq.donation_id JOIN users du ON du.id=d.donor_id
        JOIN users ru ON ru.id=rq.recipient_id WHERE {col}=? ORDER BY rq.id DESC""", (session["uid"],)))


@app.post("/api/requests")
@auth("recipient")
def create_request():
    d = request.get_json(silent=True) or {}
    don = q("SELECT * FROM donations WHERE id=?", (pos_int(d.get("donation_id")),), True)
    if not don:
        return err("Donation not found.", 404)
    if don["status"] != "Available":
        return err("This donation has already been requested.")
    if q("SELECT 1 x FROM requests WHERE donation_id=? AND recipient_id=? AND status!='Rejected'", (don["id"], session["uid"]), True):
        return err("You have already requested this donation.")
    reqs = q("SELECT * FROM requirements WHERE recipient_id=? AND status='Open'", (session["uid"],))
    if d.get("requirement_id"):
        reqs = [r for r in reqs if r["id"] == pos_int(d["requirement_id"])]
    best = max(reqs, key=lambda r: score_match(don, r)[0], default=None)
    if not best:
        return err("Please create a requirement first so GiveLoop can match this donation.")
    s, why = score_match(don, best)
    run("INSERT INTO requests(donation_id,recipient_id,requirement_id) VALUES(?,?,?)", (don["id"], session["uid"], best["id"]))
    run("UPDATE donations SET status='Requested' WHERE id=?", (don["id"],))
    run("""INSERT INTO matches(donation_id,requirement_id,match_score,match_reason) VALUES(?,?,?,?)
           ON CONFLICT(donation_id,requirement_id) DO UPDATE SET match_score=excluded.match_score""",
        (don["id"], best["id"], s, "; ".join(why)))
    return jsonify({"message": "Your donation request has been sent."}), 201


def owned_request(rid):
    rq = q("""SELECT rq.*, d.donor_id FROM requests rq JOIN donations d ON d.id=rq.donation_id
              WHERE rq.id=?""", (rid,), True)
    if not rq:
        return None, err("Request not found.", 404)
    if rq["donor_id"] != session["uid"]:
        return None, err("You are not allowed to do that.", 403)
    if rq["status"] != "Requested":
        return None, err("This request has already been handled.")
    return rq, None


@app.put("/api/requests/<int:rid>/accept")
@auth("donor")
def accept(rid):
    rq, e = owned_request(rid)
    if e: return e
    run("UPDATE requests SET status='Accepted' WHERE id=?", (rid,))
    run("UPDATE requests SET status='Rejected' WHERE donation_id=? AND id!=? AND status='Requested'", (rq["donation_id"], rid))
    run("UPDATE donations SET status='Accepted' WHERE id=?", (rq["donation_id"],))
    run("UPDATE matches SET status='Matched' WHERE donation_id=? AND requirement_id=?", (rq["donation_id"], rq["requirement_id"]))
    r = q("SELECT * FROM requirements WHERE id=?", (rq["requirement_id"],), True)
    if r and fulfilled(r["id"]) >= r["quantity_needed"]:
        run("UPDATE requirements SET status='Fulfilled' WHERE id=?", (r["id"],))
        run("""UPDATE donations SET status='Matched' WHERE status='Accepted' AND id IN
               (SELECT donation_id FROM requests WHERE requirement_id=? AND status='Accepted')""", (r["id"],))
    return jsonify({"message": "Request accepted. Arrange the hand-over, then mark it completed."})


@app.put("/api/requests/<int:rid>/reject")
@auth("donor")
def reject(rid):
    rq, e = owned_request(rid)
    if e: return e
    run("UPDATE requests SET status='Rejected' WHERE id=?", (rid,))
    if not q("SELECT 1 x FROM requests WHERE donation_id=? AND status='Requested'", (rq["donation_id"],), True):
        run("UPDATE donations SET status='Available' WHERE id=?", (rq["donation_id"],))
    return jsonify({"message": "Request rejected. The donation is available again."})


# ---------- dashboard ----------
@app.get("/api/dashboard")
@auth("donor", "recipient")
def dashboard():
    uid = session["uid"]
    n = lambda s, a=(): q(s, a, True)["n"]
    match_count = sum(len(g["matches"]) for g in groups_for_user())
    if session["role"] == "donor":
        mine = q("SELECT * FROM donations WHERE donor_id=? ORDER BY id DESC", (uid,))
        stats = [["My Donations", len(mine)], ["Available Matches", match_count],
                 ["Pending Requests", n("""SELECT COUNT(*) n FROM requests rq JOIN donations d ON d.id=rq.donation_id
                                           WHERE d.donor_id=? AND rq.status='Requested'""", (uid,))],
                 ["Completed Donations", sum(1 for m in mine if m["status"] == "Completed")]]
    else:
        mine = q("SELECT * FROM requirements WHERE recipient_id=? ORDER BY id DESC", (uid,))
        for m in mine:
            m["fulfilled"] = fulfilled(m["id"])
        stats = [["My Requirements", len(mine)], ["Matching Donations", match_count],
                 ["Pending Requests", n("SELECT COUNT(*) n FROM requests WHERE recipient_id=? AND status='Requested'", (uid,))],
                 ["Completed Requests", n("SELECT COUNT(*) n FROM requests WHERE recipient_id=? AND status='Completed'", (uid,))]]
    return jsonify({"stats": stats, "items": mine})


# ---------- admin ----------
TABLES = ["users", "donations", "requirements", "matches"]
STATUSES = {"donations": ["Available", "Requested", "Accepted", "Matched", "Completed"],
            "requirements": ["Open", "Fulfilled"], "matches": ["Suggested", "Matched", "Completed"]}


@app.get("/api/admin/statistics")
@auth("admin")
def admin_stats():
    n = lambda s: q(s, (), True)["n"]
    return jsonify({"Total Users": n("SELECT COUNT(*) n FROM users WHERE role!='admin'"),
                    "Total Donors": n("SELECT COUNT(*) n FROM users WHERE role='donor'"),
                    "Total Recipients": n("SELECT COUNT(*) n FROM users WHERE role='recipient'"),
                    "Total Donations": n("SELECT COUNT(*) n FROM donations"),
                    "Active Requirements": n("SELECT COUNT(*) n FROM requirements WHERE status='Open'"),
                    "Active Matches": n("SELECT COUNT(*) n FROM matches WHERE status!='Completed'"),
                    "Completed Donations": n("SELECT COUNT(*) n FROM donations WHERE status='Completed'")})


@app.get("/api/admin/<table>")
@auth("admin")
def admin_list(table):
    if table not in TABLES:
        return err("Unknown table.", 404)
    sql = {"users": "SELECT id,name,username,phone,area,role,created_at FROM users ORDER BY id",
           "donations": "SELECT d.id,d.item_name,d.category,d.quantity,d.condition,d.area,d.status,u.name donor FROM donations d JOIN users u ON u.id=d.donor_id ORDER BY d.id DESC",
           "requirements": "SELECT r.id,r.item_name,r.category,r.quantity_needed,r.area,r.urgency,r.status,u.name recipient FROM requirements r JOIN users u ON u.id=r.recipient_id ORDER BY r.id DESC",
           "matches": """SELECT m.id,d.item_name donation,r.item_name requirement,m.match_score score,m.status FROM matches m
                         JOIN donations d ON d.id=m.donation_id JOIN requirements r ON r.id=m.requirement_id
                         ORDER BY m.match_score DESC"""}[table]
    return jsonify({"rows": q(sql), "statuses": STATUSES.get(table, [])})


@app.delete("/api/admin/<table>/<int:rid>")
@auth("admin")
def admin_delete(table, rid):
    if table not in TABLES:
        return err("Unknown table.", 404)
    if table == "users":
        u = q("SELECT role FROM users WHERE id=?", (rid,), True)
        if not u or u["role"] == "admin":
            return err("This user cannot be removed.")
        for x in q("SELECT id FROM donations WHERE donor_id=?", (rid,)):
            run("DELETE FROM matches WHERE donation_id=?", (x["id"],)); run("DELETE FROM requests WHERE donation_id=?", (x["id"],))
        run("DELETE FROM donations WHERE donor_id=?", (rid,))
        for x in q("SELECT id FROM requirements WHERE recipient_id=?", (rid,)):
            run("DELETE FROM matches WHERE requirement_id=?", (x["id"],))
        run("DELETE FROM requirements WHERE recipient_id=?", (rid,)); run("DELETE FROM requests WHERE recipient_id=?", (rid,))
    elif table == "donations":
        run("DELETE FROM matches WHERE donation_id=?", (rid,)); run("DELETE FROM requests WHERE donation_id=?", (rid,))
    elif table == "requirements":
        run("DELETE FROM matches WHERE requirement_id=?", (rid,)); run("UPDATE requests SET requirement_id=NULL WHERE requirement_id=?", (rid,))
    run(f"DELETE FROM {table} WHERE id=?", (rid,))
    return jsonify({"message": "Record removed."})


@app.put("/api/admin/<table>/<int:rid>/status")
@auth("admin")
def admin_status(table, rid):
    st = (request.get_json(silent=True) or {}).get("status")
    if table not in STATUSES or st not in STATUSES[table]:
        return err("Invalid status.")
    run(f"UPDATE {table} SET status=? WHERE id=?", (st, rid))
    return jsonify({"message": "Status updated."})


@app.errorhandler(404)
def not_found(e):
    return err("Not found.", 404) if request.path.startswith("/api") else send_from_directory(FRONT, "index.html")


@app.errorhandler(500)
def server_error(e):
    return err("Something went wrong on the server.", 500)


init_db()
refresh_matches()

if __name__ == "__main__":
    print("GiveLoop running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
