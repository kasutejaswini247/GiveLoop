# GiveLoop — *Where Giving Meets Need.*
*Turn what you have into what someone needs.*

**GiveLoop does not simply list donations. It intelligently connects available resources with real-world needs.**

## Problem
People hold usable items they no longer need while schools, NGOs and families need those same items — and neither side knows about the other.

## Solution
Donors list items, recipients post requirements, and GiveLoop scores every donation/requirement pair locally (no paid API) so the best matches appear first. Several donors can contribute to one requirement (e.g. 5 + 10 + 5 bags = 20/20 → *Requirement Fulfilled*).

## Features
Donor / Recipient / Admin roles · registration with hashed passwords · donations & requirements · smart match scores with reasons · partial-quantity matching · request → accept/reject → complete flow · public Active Needs and Browse pages with filters · admin dashboard (stats, view, update status, remove with confirmation) · responsive soft design.

## Smart matching (backend/matching.py)
Score 0–100: category 30 · item-name similarity 25 · location 20 · condition 10 · quantity 10 · urgency 5.
Labels: 90–100 Excellent, 75–89 Good, 60–74 Possible, below 60 Low (hidden). Item similarity uses word overlap + difflib. Condition passes if the donation is at least as good as required. Quantity score is proportional (5 of 10 = half the points).

## Tech
Python Flask · SQLite · HTML/CSS/vanilla JS (Flask serves the frontend).

## Database
`users`, `donations`, `requirements`, `requests`, `matches` (see `backend/database.py`). Extras: `requests.requirement_id` links a request to the need it serves; `donations.notes` holds Purpose/Notes.

## Structure
```
GiveLoop/
├── backend/  app.py  database.py  matching.py  requirements.txt
├── frontend/ index.html  style.css  script.js   (single-page site, hash navigation)
├── data/     database.db  (auto-created)
├── .gitignore
└── README.md
```
The frontend is one single-page app (Home, How It Works, Browse, Active Needs, About, Login, Register, Dashboard, Donate, Create Requirement, Smart Matches, Admin are all views in `script.js`).

## Install & run (VS Code)
1. Install Python 3.9+. Unzip the project and open the `GiveLoop` folder in VS Code.
2. Open a terminal (Ctrl+`) and run:
```
cd backend
python -m venv .venv
.venv\Scripts\activate        (Windows)   |   source .venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
python app.py
```
3. Open **http://127.0.0.1:5000**. The database and demo data are created automatically. To reset, stop the server and delete `data/database.db`.

## Demo accounts
| Role | Username | Password |
|---|---|---|
| Admin | admin | admin123 |
| Donors | rahul, priya, arjun | demo123 |
| Recipients | education, studentngo, community | demo123 |

> ⚠️ Demo credentials and the Flask secret key in `app.py` are for demonstration only — change them for any real deployment.

## Example workflow
1. Register as a donor, log in, **Donate an Item** (e.g. 5 School Bags, Hyderabad).
2. Log in as `education` → **Smart Matches** shows the bags at ~90%+ ("5 of 10 required items available").
3. Click **Request Donation**. Log in as the donor → dashboard → **Accept**.
4. Either side clicks **Mark Completed**. Admin sees everything in the admin dashboard.

## Future improvements
Messaging between users, image upload, email/SMS alerts, map-based distance, multi-language, pagination, CSRF tokens and HTTPS for production.
