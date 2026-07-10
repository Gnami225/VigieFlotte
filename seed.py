"""
seed.py — Chargement initial des bases (engins, camions, couples) dans la DB.

N'insère QUE si les tables sont vides (idempotent au premier lancement).
Les fichiers sources sont des PSV (séparateur '|') dans ./data/.

Mappage des valeurs de possession :
    'OK'                       -> True
    'NO'                       -> False
    'NO DEFINE' | 'Na' | ''    -> None
Dates au format DD/MM/YYYY -> datetime.date | None
"""
from __future__ import annotations
import os
from datetime import datetime, date

from sqlalchemy import text
import db as DB

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

_VRAI = {"OK", "OUI", "TRUE", "1"}
_FAUX = {"NO", "NON", "FALSE", "0"}
_VIDE = {"", "NA", "NO DEFINE", "??", "EFFACÉ", "EFFACE", "NONE"}


def to_bool(v):
    if v is None:
        return None
    s = str(v).strip().upper()
    if s in _VRAI:
        return True
    if s in _FAUX:
        return False
    if s in _VIDE:
        return None
    return None


def to_date(v):
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.upper() in _VIDE:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _clean(v):
    s = (v or "").strip()
    return s or None


def data_disponible() -> bool:
    """Vrai si les fichiers sources sont présents dans ./data/."""
    return all(os.path.exists(os.path.join(DATA_DIR, f))
               for f in ("engins.psv", "camions.psv", "couples.psv"))


def _rows(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            yield [c.strip() for c in line.split("|")]


# --- Engins ------------------------------------------------------------------
def seed_engins():
    """matricule|id_chassis|marque|distinctions|type_engin|douanes|assurance"""
    for r in _rows("engins.psv"):
        r = (r + [""] * 7)[:7]
        matricule, chassis, marque, distinct, type_eng, douane, assur = r
        vid = DB.insert_vehicle({
            "categorie": "engin",
            "code_interne": _clean(matricule),
            "immatriculation": _clean(matricule),
            "type_vehicule": _clean(type_eng),
            "marque": _clean(marque),
            "modele": _clean(distinct),
            "id_chassis": _clean(chassis),
        })
        DB.upsert_document(vid, "douanes", to_bool(douane), None)
        # Engins : assurance en possession (pas de date fournie)
        DB.upsert_document(vid, "assurance", to_bool(assur), None)


# --- Camions -----------------------------------------------------------------
# id_interne|immat|type|nb_roues|marque|age|date_circ|places|cu|cv|couleur|
# cg|ct|cs|vt|pat|ass|n_cg|chassis|exp_ass|exp_ct|exp_vt
def seed_camions():
    for r in _rows("camions.psv"):
        r = (r + [""] * 22)[:22]
        (id_int, immat, typ, roues, marque, age, dcirc, places, cu, cv, couleur,
         cg, ct, cs, vt, pat, ass, n_cg, chassis, exp_ass, exp_ct, exp_vt) = r

        vid = DB.insert_vehicle({
            "categorie": "camion",
            "code_interne": _clean(id_int),
            "immatriculation": _clean(immat),
            "type_vehicule": _clean(typ),
            "marque": _clean(marque),
            "modele": None,
            "id_chassis": _clean(chassis),
            "nb_roues": _clean(roues),
            "age": _clean(age),
            "date_mise_circulation": to_date(dcirc),
            "nb_places": _clean(places),
            "charge_utile": _clean(cu),
            "puissance_cv": _clean(cv),
            "couleur": _clean(couleur),
            "n_carte_grise": _clean(n_cg),
        })
        # 6 documents par camion
        DB.upsert_document(vid, "carte_grise",          to_bool(cg), None)
        DB.upsert_document(vid, "carte_transport",      to_bool(ct), to_date(exp_ct))
        DB.upsert_document(vid, "carte_stationnement",  to_bool(cs), None)
        DB.upsert_document(vid, "visite_technique",     to_bool(vt), to_date(exp_vt))
        DB.upsert_document(vid, "patente",              to_bool(pat), None)
        DB.upsert_document(vid, "assurance",            to_bool(ass), to_date(exp_ass))


# --- Couples porte-chars -----------------------------------------------------
def seed_couples():
    """'VEH_A & VEH_B|date_exp'"""
    for r in _rows("couples.psv"):
        r = (r + [""] * 2)[:2]
        couple, dexp = r
        sep = "&" if "&" in couple else ("/" if "/" in couple else None)
        if sep:
            a, _, b = couple.partition(sep)
        else:
            a, b = couple, ""
        DB.upsert_couple(_clean(a), _clean(b), to_date(dexp))


def run_seed(force: bool = False) -> dict:
    """Initialise le schéma puis charge les données si les tables sont vides."""
    DB.init_db()
    res = {"vehicles": 0, "couples": 0, "skipped": False,
           "data_manquante": not data_disponible()}
    if not force and not DB.table_vide("vehicles"):
        res["skipped"] = True
    else:
        seed_engins()
        seed_camions()
    if force or DB.table_vide("porte_chars_couples"):
        seed_couples()

    eng = DB.get_engine()
    with eng.connect() as conn:
        res["vehicles"] = conn.execute(text("SELECT COUNT(*) FROM vehicles")).scalar()
        res["couples"] = conn.execute(text("SELECT COUNT(*) FROM porte_chars_couples")).scalar()
    return res


if __name__ == "__main__":
    print(run_seed(force=True))
