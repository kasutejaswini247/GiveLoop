"""GiveLoop smart matching: scores a donation against a requirement (0-100), fully local."""
import difflib, re

COND_RANK = {"Usable": 1, "Good": 2, "Like New": 3, "New": 4}
URGENCY_PTS = {"High": 5, "Medium": 3, "Low": 1}


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower().strip())


def _stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def item_similarity(a, b):
    ta = {_stem(w) for w in _norm(a).split()}
    tb = {_stem(w) for w in _norm(b).split()}
    overlap = len(ta & tb) / max(len(ta | tb), 1)
    return max(overlap, difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio())


def label_for(score):
    if score >= 90: return "Excellent Match"
    if score >= 75: return "Good Match"
    if score >= 60: return "Possible Match"
    return "Low Match"


def score_match(d, r):
    """d = donation row, r = requirement row. Returns (score, [reasons])."""
    pts, why = 0, []
    if d["category"] == r["category"]:
        pts += 30; why.append("Same category")
    sim = item_similarity(d["item_name"], r["item_name"])
    pts += round(25 * sim)
    if sim >= 0.85: why.append("Same item")
    elif sim >= 0.5: why.append("Similar item")
    da, ra = _norm(d["area"]), _norm(r["area"])
    if da == ra: pts += 20; why.append("Same location")
    elif da and ra and (da in ra or ra in da): pts += 10; why.append("Nearby location")
    dc, rc = COND_RANK.get(d["condition"], 1), COND_RANK.get(r["condition_required"], 1)
    if dc >= rc: pts += 10; why.append("Suitable condition")
    elif dc == rc - 1: pts += 5; why.append("Condition slightly below requirement")
    need = max(int(r["quantity_needed"]), 1)
    have = int(d["quantity"])
    pts += round(10 * min(have, need) / need)
    why.append("Quantity fully satisfies requirement" if have >= need
               else "Quantity partially satisfies requirement")
    pts += URGENCY_PTS.get(r["urgency"], 1)
    if r["urgency"] == "High": why.append("High urgency need")
    return min(pts, 100), why
