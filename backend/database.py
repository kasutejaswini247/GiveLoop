import os, sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "database.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
 username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, phone TEXT, area TEXT, role TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS donations(id INTEGER PRIMARY KEY AUTOINCREMENT, donor_id INTEGER NOT NULL,
 item_name TEXT NOT NULL, category TEXT NOT NULL, description TEXT, quantity INTEGER NOT NULL,
 condition TEXT NOT NULL, area TEXT NOT NULL, image TEXT, notes TEXT, status TEXT DEFAULT 'Available',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS requirements(id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_id INTEGER NOT NULL,
 item_name TEXT NOT NULL, category TEXT NOT NULL, description TEXT, quantity_needed INTEGER NOT NULL,
 condition_required TEXT NOT NULL, area TEXT NOT NULL, urgency TEXT DEFAULT 'Medium', purpose TEXT,
 status TEXT DEFAULT 'Open', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, donation_id INTEGER NOT NULL,
 recipient_id INTEGER NOT NULL, requirement_id INTEGER, status TEXT DEFAULT 'Requested',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY AUTOINCREMENT, donation_id INTEGER NOT NULL,
 requirement_id INTEGER NOT NULL, match_score INTEGER, match_reason TEXT, status TEXT DEFAULT 'Suggested',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(donation_id, requirement_id));
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = get_db()
    c.executescript(SCHEMA)
    if not c.execute("SELECT 1 FROM users").fetchone():
        seed(c)
    c.commit(); c.close()


def seed(c):
    def user(name, uname, pw, phone, area, role):
        return c.execute("INSERT INTO users(name,username,password_hash,phone,area,role) VALUES(?,?,?,?,?,?)",
                         (name, uname, generate_password_hash(pw), phone, area, role)).lastrowid
    user("Administrator", "admin", "admin123", "9000000000", "Hyderabad", "admin")
    rahul = user("Rahul", "rahul", "demo123", "9111111111", "Hyderabad", "donor")
    priya = user("Priya", "priya", "demo123", "9222222222", "Secunderabad", "donor")
    arjun = user("Arjun", "arjun", "demo123", "9333333333", "Hyderabad", "donor")
    cec = user("Community Education Center", "education", "demo123", "9444444444", "Hyderabad", "recipient")
    ngo = user("Student Support NGO", "studentngo", "demo123", "9555555555", "Secunderabad", "recipient")
    cc = user("Community Center", "community", "demo123", "9666666666", "Hyderabad", "recipient")
    D = "INSERT INTO donations(donor_id,item_name,category,description,quantity,condition,area,notes) VALUES(?,?,?,?,?,?,?,?)"
    c.execute(D, (rahul, "School Bags", "School Supplies", "Clean and usable school bags.", 5, "Good", "Hyderabad", "Pickup on weekends"))
    c.execute(D, (priya, "Books", "Books", "Story and text books in good shape.", 20, "Good", "Secunderabad", ""))
    c.execute(D, (arjun, "Study Tables", "Furniture", "Sturdy wooden tables.", 3, "Usable", "Hyderabad", ""))
    R = "INSERT INTO requirements(recipient_id,item_name,category,description,quantity_needed,condition_required,area,urgency,purpose) VALUES(?,?,?,?,?,?,?,?,?)"
    c.execute(R, (cec, "School Bags", "School Supplies", "Bags for students.", 10, "Good", "Hyderabad", "High", "Required for students who cannot afford school bags."))
    c.execute(R, (ngo, "Books", "Books", "Books for a learning library.", 15, "Good", "Secunderabad", "Medium", "Reading library for children."))
    c.execute(R, (cc, "Study Tables", "Furniture", "Tables for the study hall.", 5, "Usable", "Hyderabad", "Medium", "Study hall for evening classes."))
    c.execute(R, (cec, "Notebooks", "School Supplies", "Ruled notebooks.", 15, "New", "Hyderabad", "Low", "For classroom use."))
    c.execute(R, (cc, "Blankets", "Household Items", "Warm blankets.", 10, "Good", "Hyderabad", "High", "For winter shelter."))
