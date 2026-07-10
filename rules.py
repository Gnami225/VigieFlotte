"""
rules.py — Moteur métier : types de documents, calcul d'état et d'échéances.
Aucune dépendance Streamlit/DB : 100% testable unitairement.
"""
from __future__ import annotations
from datetime import date
from dateutil.relativedelta import relativedelta

# --- Configuration des types de documents -----------------------------------
# kind:
#   'possession'      -> détenu ou non, sans échéance (carte grise, douanes)
#   'date'            -> échéance explicite (assurance, transport, visite...)
#   'annuel_janvier'  -> renouvellement annuel en janvier (stationnement, patente)
POSSESSION, DATE, ANNUEL_JAN = "possession", "date", "annuel_janvier"

DOC_TYPES = {
    "carte_grise":        {"label": "Carte grise",            "kind": POSSESSION, "cats": ["camion"]},
    "carte_transport":    {"label": "Carte de transport",     "kind": DATE,       "cats": ["camion"], "periode_mois": 24, "alerte_mois": 2},
    "carte_stationnement":{"label": "Carte de stationnement", "kind": ANNUEL_JAN, "cats": ["camion"], "alerte_mois": 2},
    "patente":            {"label": "Patente",                "kind": ANNUEL_JAN, "cats": ["camion"], "alerte_mois": 2},
    "visite_technique":   {"label": "Visite technique",       "kind": DATE,       "cats": ["camion"], "periode_mois": 12, "alerte_mois": 2},
    "assurance":          {"label": "Assurance",              "kind": DATE,       "cats": ["camion", "engin"], "periode_mois": 12, "alerte_mois": 2},
    "douanes":            {"label": "Papiers de douane",      "kind": POSSESSION, "cats": ["engin"]},
}
PORTE_CHARS = {"label": "Autorisation porte-chars", "periode_mois": 6, "alerte_mois": 1}

# --- Codes d'état ------------------------------------------------------------
A_JOUR, A_RENOUVELER, EXPIRE = "a_jour", "a_renouveler", "expire"
DETENU, NON_DETENU, A_RENSEIGNER = "detenu", "non_detenu", "a_renseigner"

ETAT_LABEL = {
    A_JOUR: "À jour", A_RENOUVELER: "À renouveler", EXPIRE: "Expiré",
    DETENU: "Détenu", NON_DETENU: "Non détenu", A_RENSEIGNER: "À renseigner",
}
# Couleurs (vert / ambre / rouge / gris) — réutilisées partout (AgGrid, Plotly)
ETAT_COULEUR = {
    A_JOUR: "#1a7f48", A_RENOUVELER: "#c47f17", EXPIRE: "#b3261e",
    DETENU: "#1a7f48", NON_DETENU: "#5f6368", A_RENSEIGNER: "#8a6d00",
}
# États considérés "conformes" pour le taux de conformité
CONFORMES = {A_JOUR, DETENU}


def _echeance_janvier(today: date) -> date:
    """Prochaine échéance annuelle fixée au 31 janvier."""
    y = today.year if today <= date(today.year, 1, 31) else today.year + 1
    return date(y, 1, 31)


def compute_etat(type_doc: str, possede, date_expiration, today: date | None = None):
    """
    Renvoie (code_etat, echeance_effective, jours_restants).
    - possede: bool | None
    - date_expiration: datetime.date | None
    """
    today = today or date.today()
    cfg = DOC_TYPES.get(type_doc)
    if cfg is None:  # porte-chars ou type inconnu -> traité comme 'date'
        kind, alerte_mois = DATE, PORTE_CHARS["alerte_mois"]
    else:
        kind, alerte_mois = cfg["kind"], cfg.get("alerte_mois", 2)

    # 1) Documents de possession pure
    if kind == POSSESSION:
        if possede is True:
            return DETENU, None, None
        if possede is False:
            return NON_DETENU, None, None
        return A_RENSEIGNER, None, None

    # 2) Détermination de l'échéance effective
    ech = date_expiration
    if ech is None and kind == ANNUEL_JAN and possede is not False:
        ech = _echeance_janvier(today)

    if ech is None:
        if possede is False:
            return NON_DETENU, None, None
        return A_RENSEIGNER, None, None

    jours = (ech - today).days
    seuil = ech - relativedelta(months=alerte_mois)
    if jours < 0:
        return EXPIRE, ech, jours
    if today >= seuil:
        return A_RENOUVELER, ech, jours
    return A_JOUR, ech, jours


def prochaine_echeance(type_doc: str, base: date) -> date:
    """Échéance suggérée lors d'un renouvellement (bouton 'Renouveler')."""
    cfg = DOC_TYPES.get(type_doc)
    if cfg and cfg["kind"] == ANNUEL_JAN:
        return _echeance_janvier(base + relativedelta(days=1))
    mois = (cfg or PORTE_CHARS).get("periode_mois", 12)
    return base + relativedelta(months=mois)


def alerte_mois(type_doc: str) -> int:
    cfg = DOC_TYPES.get(type_doc)
    return (cfg or PORTE_CHARS).get("alerte_mois", 2)
