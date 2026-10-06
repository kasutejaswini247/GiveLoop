import os
import sys
import sqlite3
import streamlit as st
from werkzeug.security import generate_password_hash, check_password_hash

# Reuse your existing GiveLoop database + smart matching logic.
ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from database import get_db, init_db  # noqa: E402
from matching import score_match, label_for  # noqa: E402

st.set_page_config(page_title="GiveLoop", page_icon="🎁", layout="wide")

CATEGORIES = [
    "Books", "Clothes", "School Supplies", "Electronics", "Furniture",
    "Toys", "Kitchen Items", "Household Items", "Medical Support Items", "Other"
]
CONDITIONS = ["New", "Like New", "Good", "Usable"]
THRESHOLD = 60

# ---------- Styling ----------
st.markdown("""
<style>
:root {
    --cream:#fbf7ef;
    --sage:#e4eddf;
    --green:#6f9e7a;
    --green-dark:#3f6650;
    --blue:#e3eef6;
    --text:#30443a;
    --muted:#61736a;
    --border:#dfe8e1;
}

/* Main application */
.stApp {
    background: var(--cream);
    color: var(--text);
}
.block-container {
    max-width: 1180px;
    padding-top: 2rem;
}

/* Global text visibility */
.stApp, .stApp p, .stApp span, .stApp label,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    color: var(--text);
}
.stMarkdown p, .stMarkdown span,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] * {
    color: var(--muted) !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background:#ffffff;
    border-right:1px solid var(--border);
}
[data-testid="stSidebar"] * {
    color:var(--text) !important;
}
[data-testid="stSidebar"] .stRadio label {
    color:var(--text) !important;
}
[data-testid="stSidebar"] .stCaption {
    color:var(--muted) !important;
}

/* Hero */
.hero {
    background:linear-gradient(135deg,#e4eddf,#e3eef6);
    border-radius:24px;
    padding:38px;
    margin-bottom:24px;
    border:1px solid #dce7df;
}
.hero h1 {
    font-size:3rem;
    margin:0 0 8px;
    color:#30443a !important;
}
.hero p {
    color:#526b5f !important;
    font-size:1.08rem;
}

/* Cards */
.card {
    background:#ffffff;
    color:var(--text) !important;
    border-radius:18px;
    padding:20px;
    margin:10px 0;
    box-shadow:0 4px 16px rgba(80,100,80,.08);
    border:1px solid #e5ebe6;
}
.card h2, .card h3, .card p, .card span {
    color:var(--text) !important;
}
.match-card {
    border-left:6px solid var(--green);
}
.score {
    font-size:1.7rem;
    font-weight:700;
    color:#4f7d5b !important;
}
.small {
    color:var(--muted) !important;
    font-size:.9rem;
}
.pill {
    display:inline-block;
    padding:3px 10px;
    border-radius:14px;
    background:#e4eddf;
    color:#3f6650 !important;
    font-size:.8rem;
    font-weight:600;
}

/* Metrics */
[data-testid="stMetric"] {
    background:#ffffff;
    border-radius:18px;
    padding:15px;
    box-shadow:0 4px 16px rgba(80,100,80,.08);
    border:1px solid #e5ebe6;
}
[data-testid="stMetric"] * {
    color:#30443a !important;
}
[data-testid="stMetricLabel"] {
    color:#61736a !important;
}
[data-testid="stMetricValue"] {
    color:#30443a !important;
}

/* Forms and inputs */
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stRadio"] label {
    color:#30443a !important;
}
.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
    color:#30443a !important;
    background:#ffffff !important;
    border:1px solid #ccd9d0 !important;
}
.stSelectbox div[data-baseweb="select"] {
    background:#ffffff !important;
}
.stSelectbox div[data-baseweb="select"] * {
    color:#30443a !important;
}

/* Tables */
[data-testid="stDataFrame"] {
    border:1px solid #dfe8e1;
    border-radius:12px;
    overflow:hidden;
}

/* Buttons */
.stButton > button {
    color:#ffffff !important;
    background:#6f9e7a !important;
    border:1px solid #6f9e7a !important;
    border-radius:10px;
    font-weight:600;
}
.stButton > button:hover {
    background:#5f8f6b !important;
    border-color:#5f8f6b !important;
}

/* Alerts */
[data-testid="stAlert"] * {
    color:#30443a !important;
}

/* Dividers */
hr {
    border-color:#e7ebe4;
}
</style>
""", unsafe_allow_html=True)

# ---------- Database helpers ----------
def q(sql, args=(), one=False):
    c = get_db()
    rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    c.close()
    return (rows[0] if rows else None) if one else rows


def run(sql, args=()):
    c = get_db()
    cur = c.execute(sql, args)
    c.commit()
    last = cur.lastrowid
    c.close()
    return last


def refresh_matches():
    c = get_db()
    donations = [dict(r) for r in c.execute("SELECT * FROM donations WHERE status IN ('Available','Requested')")]
    requirements = [dict(r) for r in c.execute("SELECT * FROM requirements WHERE status='Open'")]
    for d in donations:
        for r in requirements:
            score, why = score_match(d, r)
            if score >= THRESHOLD:
                c.execute(
                    "INSERT OR IGNORE INTO matches(donation_id,requirement_id,match_score,match_reason) VALUES(?,?,?,?)",
                    (d["id"], r["id"], score, "; ".join(why)),
                )
    c.commit()
    c.close()


def fulfilled(rid):
    row = q("""SELECT COALESCE(SUM(d.quantity),0) AS s
              FROM requests rq JOIN donations d ON d.id=rq.donation_id
              WHERE rq.requirement_id=? AND rq.status IN ('Accepted','Completed')""", (rid,), True)
    return int(row["s"] or 0)


def current_user():
    return st.session_state.get("user")


def logout():
    st.session_state.user = None
    st.session_state.page = "Home"
    st.rerun()


def login_user(username, password):
    u = q("SELECT * FROM users WHERE username=?", (username.strip().lower(),), True)
    if not u or not check_password_hash(u["password_hash"], password):
        return False, "Invalid username or password."
    st.session_state.user = {"id": u["id"], "name": u["name"], "role": u["role"]}
    return True, "Login successful."


def register_user(name, username, password, phone, area, role):
    username = username.strip().lower()
    if not all([name.strip(), username, password, phone.strip(), area.strip()]):
        return False, "Please enter all required fields."
    if role not in ("donor", "recipient"):
        return False, "Please choose Donor or Recipient."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    digits = phone.replace("+", "").replace(" ", "")
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        return False, "Please enter a valid phone number."
    if q("SELECT 1 FROM users WHERE username=?", (username,), True):
        return False, "That username is already taken."
    run("INSERT INTO users(name,username,password_hash,phone,area,role) VALUES(?,?,?,?,?,?)",
        (name.strip(), username, generate_password_hash(password), phone.strip(), area.strip(), role))
    return True, "Account created. You can now log in."


def donation_matches(donation):
    reqs = q("""SELECT r.*, u.name recipient_name FROM requirements r
               JOIN users u ON u.id=r.recipient_id WHERE r.status='Open'""")
    out = []
    for r in reqs:
        score, why = score_match(donation, r)
        if score >= THRESHOLD:
            out.append((score, why, r))
    return sorted(out, key=lambda x: -x[0])


def requirement_matches(req):
    ds = q("""SELECT d.*, u.name donor_name FROM donations d
              JOIN users u ON u.id=d.donor_id
              WHERE d.status IN ('Available','Requested')""")
    out = []
    for d in ds:
        score, why = score_match(d, req)
        if score >= THRESHOLD:
            already = q("""SELECT 1 FROM requests
                         WHERE donation_id=? AND recipient_id=? AND status!='Rejected'""",
                        (d["id"], req["recipient_id"]), True)
            out.append({"score":score, "label":label_for(score), "why":why, "donation":d,
                        "already_requested":bool(already)})
    return sorted(out, key=lambda x: -x["score"])


# Initialize database automatically.
init_db()
refresh_matches()

# ---------- Page functions ----------
def home():
    st.markdown("""
    <div class="hero">
      <h1>GiveLoop</h1>
      <p><b>Where Giving Meets Need.</b><br>
      A smart donation item matching platform that connects available resources with real-world needs.</p>
    </div>
    """, unsafe_allow_html=True)

    stats = q("SELECT COUNT(*) n FROM donations", (), True)["n"]
    needs = q("SELECT COUNT(*) n FROM requirements WHERE status='Open'", (), True)["n"]
    matches = q("SELECT COUNT(*) n FROM matches", (), True)["n"]
    completed = q("SELECT COUNT(*) n FROM donations WHERE status='Completed'", (), True)["n"]
    a,b,c,d = st.columns(4)
    a.metric("Donations", stats); b.metric("Active Needs", needs); c.metric("Matches", matches); d.metric("Completed", completed)

    st.markdown("### How GiveLoop works")
    cols = st.columns(3)
    for col, icon, title, text in zip(cols,
        ["🎁", "🤝", "✅"],
        ["Donate", "Smart Match", "Complete"],
        ["List an item you can give.", "GiveLoop compares item, category, location, condition, quantity and urgency.", "Recipients request, donors accept, and the hand-over is completed."]):
        with col:
            st.markdown(f"<div class='card'><h2>{icon} {title}</h2><p>{text}</p></div>", unsafe_allow_html=True)

    st.info("Tip: Use the demo accounts from the sidebar to test the complete workflow.")


def login_page():
    st.markdown("## Welcome back")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")
    if submitted:
        ok, msg = login_user(username, password)
        if ok:
            st.success(msg); st.session_state.page = "Dashboard"; st.rerun()
        else:
            st.error(msg)
    st.caption("Demo: admin/admin123 · donor rahul/demo123 · recipient education/demo123")


def register_page():
    st.markdown("## Create your account")
    with st.form("register_form"):
        name = st.text_input("Full Name")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        phone = st.text_input("Phone Number")
        area = st.text_input("Area / Location")
        role = st.selectbox("User Role", ["donor", "recipient"])
        submitted = st.form_submit_button("Register", type="primary")
    if submitted:
        ok, msg = register_user(name, username, password, phone, area, role)
        if ok:
            st.success(msg); st.session_state.page = "Login"
        else:
            st.error(msg)


def browse_donations():
    st.markdown("## Browse Donations")
    c1,c2,c3,c4 = st.columns(4)
    search = c1.text_input("Search item")
    category = c2.selectbox("Category", ["All"] + CATEGORIES)
    condition = c3.selectbox("Condition", ["All"] + CONDITIONS)
    location = c4.text_input("Location")
    sql = """SELECT d.*, u.name donor_name FROM donations d JOIN users u ON u.id=d.donor_id
             WHERE d.status IN ('Available','Requested')"""
    args=[]
    if search: sql += " AND LOWER(d.item_name) LIKE ?"; args.append(f"%{search.lower()}%")
    if category != "All": sql += " AND d.category=?"; args.append(category)
    if condition != "All": sql += " AND d.condition=?"; args.append(condition)
    if location: sql += " AND LOWER(d.area) LIKE ?"; args.append(f"%{location.lower()}%")
    rows = q(sql + " ORDER BY d.id DESC", args)
    if not rows:
        st.info("No donations found.")
        return
    cols = st.columns(3)
    for i, d in enumerate(rows):
        with cols[i % 3]:
            st.markdown(f"<div class='card'><h3>{d['item_name']}</h3><p class='small'>{d['category']} · {d['condition']} · {d['area']}</p><p>{d.get('description') or 'No description provided.'}</p><p><b>Quantity:</b> {d['quantity']}<br><b>Donor:</b> {d['donor_name']}</p></div>", unsafe_allow_html=True)
            if current_user() and current_user()["role"] == "recipient" and d["status"] == "Available":
                if st.button("Request Donation", key=f"req_{d['id']}"):
                    reqs = q("SELECT * FROM requirements WHERE recipient_id=? AND status='Open'", (current_user()["id"],))
                    if not reqs:
                        st.error("Create a requirement first so GiveLoop can match this donation.")
                    else:
                        best = max(reqs, key=lambda r: score_match(d, r)[0])
                        score, why = score_match(d, best)
                        run("INSERT INTO requests(donation_id,recipient_id,requirement_id) VALUES(?,?,?)", (d["id"], current_user()["id"], best["id"]))
                        run("UPDATE donations SET status='Requested' WHERE id=?", (d["id"],))
                        run("""INSERT INTO matches(donation_id,requirement_id,match_score,match_reason) VALUES(?,?,?,?)
                             ON CONFLICT(donation_id,requirement_id) DO UPDATE SET match_score=excluded.match_score""",
                            (d["id"], best["id"], score, "; ".join(why)))
                        st.success("Donation request sent!"); st.rerun()


def active_needs():
    st.markdown("## Active Needs")
    rows = q("""SELECT r.*, u.name recipient_name FROM requirements r JOIN users u ON u.id=r.recipient_id
                 WHERE r.status='Open' ORDER BY CASE r.urgency WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, r.id DESC""")
    if not rows:
        st.info("No active requirements yet.")
        return
    for r in rows:
        done = fulfilled(r["id"])
        st.markdown(f"<div class='card'><h3>{r['quantity_needed']} × {r['item_name']} <span class='pill'>{r['urgency']} urgency</span></h3><p class='small'>{r['category']} · {r['condition_required']} · {r['area']} · Posted by {r['recipient_name']}</p><p>{r.get('purpose') or r.get('description') or 'No additional details.'}</p><p><b>Fulfilled:</b> {done} / {r['quantity_needed']}</p></div>", unsafe_allow_html=True)


def add_donation():
    u = current_user()
    if not u or u["role"] != "donor":
        st.warning("Please log in as a donor."); return
    st.markdown("## Donate an Item")
    with st.form("donation_form"):
        item = st.text_input("Item Name", placeholder="e.g. School Bags")
        c1,c2 = st.columns(2)
        category = c1.selectbox("Category", CATEGORIES)
        quantity = c2.number_input("Quantity", min_value=1, step=1)
        condition = c1.selectbox("Condition", CONDITIONS, index=2)
        area = c2.text_input("Area / Location", placeholder="e.g. Hyderabad")
        description = st.text_area("Description")
        notes = st.text_input("Purpose / Notes")
        submitted = st.form_submit_button("Add Donation", type="primary")
    if submitted:
        if not item.strip() or not area.strip(): st.error("Please enter item name and area."); return
        run("""INSERT INTO donations(donor_id,item_name,category,description,quantity,condition,area,image,notes)
             VALUES(?,?,?,?,?,?,?,?,?)""", (u["id"], item.strip(), category, description, int(quantity), condition, area.strip(), "", notes))
        refresh_matches(); st.success("Your donation has been added to GiveLoop!"); st.session_state.page="Smart Matches"; st.rerun()


def create_requirement():
    u = current_user()
    if not u or u["role"] != "recipient":
        st.warning("Please log in as a recipient."); return
    st.markdown("## Create Requirement")
    with st.form("requirement_form"):
        item = st.text_input("Required Item", placeholder="e.g. School Bags")
        c1,c2 = st.columns(2)
        category = c1.selectbox("Category", CATEGORIES)
        quantity = c2.number_input("Quantity Needed", min_value=1, step=1)
        condition = c1.selectbox("Minimum Condition Required", CONDITIONS, index=2)
        area = c2.text_input("Area / Location", placeholder="e.g. Hyderabad")
        urgency = st.selectbox("Urgency", ["Low","Medium","High"], index=1)
        purpose = st.text_input("Purpose")
        description = st.text_area("Description")
        submitted = st.form_submit_button("Post Requirement", type="primary")
    if submitted:
        if not item.strip() or not area.strip(): st.error("Please enter item name and area."); return
        run("""INSERT INTO requirements(recipient_id,item_name,category,description,quantity_needed,condition_required,area,urgency,purpose)
             VALUES(?,?,?,?,?,?,?,?,?)""", (u["id"], item.strip(), category, description, int(quantity), condition, area.strip(), urgency, purpose))
        refresh_matches(); st.success("Your requirement has been posted on GiveLoop!"); st.session_state.page="Smart Matches"; st.rerun()


def dashboard():
    u = current_user()
    if not u:
        st.warning("Please log in first."); return
    if u["role"] == "admin":
        admin_dashboard(); return
    st.markdown(f"## Welcome back, {u['name']}")
    if u["role"] == "donor":
        mine = q("SELECT * FROM donations WHERE donor_id=? ORDER BY id DESC", (u["id"],))
        pending = q("""SELECT COUNT(*) n FROM requests rq JOIN donations d ON d.id=rq.donation_id
                       WHERE d.donor_id=? AND rq.status='Requested'""", (u["id"],), True)["n"]
        completed = sum(1 for x in mine if x["status"] == "Completed")
        matches_count = sum(len(donation_matches(d)) for d in mine if d["status"] in ("Available","Requested"))
        a,b,c,d=st.columns(4); a.metric("My Donations",len(mine)); b.metric("Available Matches",matches_count); c.metric("Pending Requests",pending); d.metric("Completed Donations",completed)
        st.markdown("### My Donations")
        if mine:
            st.dataframe([{"Item":x["item_name"],"Category":x["category"],"Quantity":x["quantity"],"Condition":x["condition"],"Area":x["area"],"Status":x["status"]} for x in mine], use_container_width=True, hide_index=True)
        else: st.info("No donations yet.")
        st.markdown("### Donation Requests")
        reqs=q("""SELECT rq.*,d.item_name,d.quantity,ru.name recipient_name FROM requests rq
                  JOIN donations d ON d.id=rq.donation_id JOIN users ru ON ru.id=rq.recipient_id
                  WHERE d.donor_id=? ORDER BY rq.id DESC""",(u["id"],))
        for r in reqs:
            st.markdown(f"**{r['item_name']}** · requested by **{r['recipient_name']}** · `{r['status']}`")
            c1,c2=st.columns(2)
            if r["status"]=="Requested":
                if c1.button("Accept", key=f"acc{r['id']}"):
                    run("UPDATE requests SET status='Accepted' WHERE id=?",(r["id"],)); run("UPDATE requests SET status='Rejected' WHERE donation_id=? AND id!=? AND status='Requested'",(r["donation_id"],r["id"])); run("UPDATE donations SET status='Accepted' WHERE id=?",(r["donation_id"],)); run("UPDATE matches SET status='Matched' WHERE donation_id=? AND requirement_id=?",(r["donation_id"],r["requirement_id"])); st.success("Request accepted."); st.rerun()
                if c2.button("Reject", key=f"rej{r['id']}"):
                    run("UPDATE requests SET status='Rejected' WHERE id=?",(r["id"],)); run("UPDATE donations SET status='Available' WHERE id=?",(r["donation_id"],)); st.info("Request rejected."); st.rerun()
            if r["status"]=="Accepted":
                if st.button("Mark Completed", key=f"done{r['id']}"):
                    run("UPDATE donations SET status='Completed' WHERE id=?",(r["donation_id"],)); run("UPDATE requests SET status='Completed' WHERE id=?",(r["id"],)); run("UPDATE matches SET status='Completed' WHERE donation_id=? AND requirement_id=?",(r["donation_id"],r["requirement_id"])); st.success("Donation completed. Thank you!"); st.rerun()
    else:
        mine=q("SELECT * FROM requirements WHERE recipient_id=? ORDER BY id DESC",(u["id"],))
        for x in mine: x["fulfilled"]=fulfilled(x["id"])
        pending=q("SELECT COUNT(*) n FROM requests WHERE recipient_id=? AND status='Requested'",(u["id"],),True)["n"]
        completed=q("SELECT COUNT(*) n FROM requests WHERE recipient_id=? AND status='Completed'",(u["id"],),True)["n"]
        matches_count=sum(len(requirement_matches(x)) for x in mine if x["status"]=="Open")
        a,b,c,d=st.columns(4); a.metric("My Requirements",len(mine)); b.metric("Matching Donations",matches_count); c.metric("Pending Requests",pending); d.metric("Completed Requests",completed)
        st.markdown("### My Requirements")
        if mine: st.dataframe([{"Item":x["item_name"],"Category":x["category"],"Fulfilled":f"{x['fulfilled']} / {x['quantity_needed']}","Area":x["area"],"Urgency":x["urgency"],"Status":x["status"]} for x in mine],use_container_width=True,hide_index=True)
        else: st.info("No requirements yet.")
        st.markdown("### My Requests")
        reqs=q("""SELECT rq.*,d.item_name,d.quantity,du.name donor_name FROM requests rq JOIN donations d ON d.id=rq.donation_id JOIN users du ON du.id=d.donor_id WHERE rq.recipient_id=? ORDER BY rq.id DESC""",(u["id"],))
        for r in reqs:
            st.write(f"**{r['item_name']}** · donor **{r['donor_name']}** · `{r['status']}`")


def smart_matches():
    u=current_user()
    if not u:
        st.warning("Please log in to see smart matches."); return
    refresh_matches()
    st.markdown("## Smart Matches")
    st.caption("GiveLoop scores matches from 0–100. Matches below 60 are hidden.")
    if u["role"]=="donor":
        ds=q("SELECT * FROM donations WHERE donor_id=? AND status IN ('Available','Requested') ORDER BY id DESC",(u["id"],))
        if not ds: st.info("Add a donation to see smart matches."); return
        for d in ds:
            ms=donation_matches(d)
            st.markdown(f"### {d['quantity']} × {d['item_name']} · {d['area']}")
            if not ms: st.info("No suitable matches found yet."); continue
            for score,why,r in ms[:10]:
                with st.container(border=True):
                    st.markdown(f"<div class='score'>{score}% MATCH</div><b>{label_for(score)}</b><p class='small'>Needed by {r['recipient_name']} · {r['quantity_needed']} needed · {r['area']}</p><p><b>Why this match:</b> {' · '.join(why)}</p>",unsafe_allow_html=True)
    elif u["role"]=="recipient":
        rs=q("SELECT * FROM requirements WHERE recipient_id=? AND status='Open' ORDER BY id DESC",(u["id"],))
        if not rs: st.info("Create a requirement to see smart matches."); return
        for r in rs:
            done=fulfilled(r["id"]); st.markdown(f"### {r['quantity_needed']} × {r['item_name']} · {r['area']} · {done}/{r['quantity_needed']} fulfilled")
            ms=requirement_matches(r)
            if not ms: st.info("No suitable donations found yet."); continue
            for m in ms[:10]:
                d=m["donation"]; score=m["score"]
                with st.container(border=True):
                    st.markdown(f"<div class='score'>{score}% MATCH</div><b>{m['label']}</b><p class='small'>Donor: {d['donor_name']} · Available: {d['quantity']} · Required: {r['quantity_needed']} · {d['area']}</p><p><b>Why this match:</b> {' · '.join(m['why'])}</p>",unsafe_allow_html=True)
                if m["already_requested"]: st.info("Already requested")
                elif d["status"] != "Available": st.warning("This donation has been requested by someone else.")
                elif st.button("Request Donation", key=f"matchreq{d['id']}_{r['id']}"):
                    run("INSERT INTO requests(donation_id,recipient_id,requirement_id) VALUES(?,?,?)",(d["id"],u["id"],r["id"]))
                    run("UPDATE donations SET status='Requested' WHERE id=?",(d["id"],))
                    run("""INSERT INTO matches(donation_id,requirement_id,match_score,match_reason) VALUES(?,?,?,?)
                         ON CONFLICT(donation_id,requirement_id) DO UPDATE SET match_score=excluded.match_score""",(d["id"],r["id"],score,"; ".join(m["why"])))
                    st.success("Donation request sent!"); st.rerun()


def admin_dashboard():
    u=current_user()
    if not u or u["role"]!="admin": st.warning("Admin access only."); return
    st.markdown("## Admin Dashboard")
    stats={
        "Total Users":q("SELECT COUNT(*) n FROM users WHERE role!='admin'",(),True)["n"],
        "Total Donors":q("SELECT COUNT(*) n FROM users WHERE role='donor'",(),True)["n"],
        "Total Recipients":q("SELECT COUNT(*) n FROM users WHERE role='recipient'",(),True)["n"],
        "Total Donations":q("SELECT COUNT(*) n FROM donations",(),True)["n"],
        "Active Requirements":q("SELECT COUNT(*) n FROM requirements WHERE status='Open'",(),True)["n"],
        "Active Matches":q("SELECT COUNT(*) n FROM matches WHERE status!='Completed'",(),True)["n"],
        "Completed Donations":q("SELECT COUNT(*) n FROM donations WHERE status='Completed'",(),True)["n"],
    }
    cols=st.columns(4)
    for i,(k,v) in enumerate(stats.items()): cols[i%4].metric(k,v)
    tabs=st.tabs(["Users","Donations","Requirements","Matches"])
    with tabs[0]:
        rows=q("SELECT id,name,username,phone,area,role,created_at FROM users ORDER BY id"); st.dataframe(rows,use_container_width=True,hide_index=True)
    with tabs[1]:
        rows=q("""SELECT d.id,d.item_name,d.category,d.quantity,d.condition,d.area,d.status,u.name donor
                  FROM donations d JOIN users u ON u.id=d.donor_id ORDER BY d.id DESC"""); st.dataframe(rows,use_container_width=True,hide_index=True)
    with tabs[2]:
        rows=q("""SELECT r.id,r.item_name,r.category,r.quantity_needed,r.area,r.urgency,r.status,u.name recipient
                  FROM requirements r JOIN users u ON u.id=r.recipient_id ORDER BY r.id DESC"""); st.dataframe(rows,use_container_width=True,hide_index=True)
    with tabs[3]:
        rows=q("""SELECT m.id,d.item_name donation,r.item_name requirement,m.match_score score,m.status
                  FROM matches m JOIN donations d ON d.id=m.donation_id JOIN requirements r ON r.id=m.requirement_id
                  ORDER BY m.match_score DESC"""); st.dataframe(rows,use_container_width=True,hide_index=True)


# ---------- Navigation ----------
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Home"

u=current_user()
with st.sidebar:
    st.markdown("# 🎁 GiveLoop")
    st.caption("Where Giving Meets Need.")
    st.divider()
    if u:
        st.success(f"Logged in as {u['name']} ({u['role'].title()})")
        pages=["Home","Dashboard","Smart Matches","Browse Donations","Active Needs"]
        if u["role"]=="donor": pages += ["Donate an Item"]
        if u["role"]=="recipient": pages += ["Create Requirement"]
        if u["role"]=="admin": pages=["Home","Dashboard","Smart Matches","Browse Donations","Active Needs","Admin"]
        page=st.radio("Navigate",pages,index=pages.index(st.session_state.page) if st.session_state.page in pages else 0)
        st.session_state.page=page
        if st.button("Logout", use_container_width=True): logout()
    else:
        pages=["Home","Login","Register","Browse Donations","Active Needs"]
        page=st.radio("Navigate",pages,index=pages.index(st.session_state.page) if st.session_state.page in pages else 0)
        st.session_state.page=page
        st.divider()
        st.caption("Demo accounts")
        st.code("admin / admin123\nrahul / demo123\neducation / demo123", language=None)

page=st.session_state.page
if page=="Home": home()
elif page=="Login": login_page()
elif page=="Register": register_page()
elif page=="Browse Donations": browse_donations()
elif page=="Active Needs": active_needs()
elif page=="Donate an Item": add_donation()
elif page=="Create Requirement": create_requirement()
elif page=="Dashboard": dashboard()
elif page=="Smart Matches": smart_matches()
elif page=="Admin": admin_dashboard()
