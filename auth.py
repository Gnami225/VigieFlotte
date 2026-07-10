"""
auth.py — Authentification légère et rôles.

Les comptes sont définis dans st.secrets["auth"]["users"] :

    [auth]
    users = '''
    [
      {"login": "jacques", "mot_de_passe": "…", "role": "admin",  "nom": "Jacques K."},
      {"login": "agent",   "mot_de_passe": "…", "role": "editeur","nom": "Agent parc"},
      {"login": "invite",  "mot_de_passe": "…", "role": "lecteur","nom": "Invité"}
    ]
    '''

Rôles : admin (tout + audit + admin), editeur (édition des données),
lecteur (consultation seule). En l'absence de section [auth], l'application
démarre en mode ouvert avec le rôle « admin » (pratique en local).
"""
from __future__ import annotations
import json
import hashlib
import streamlit as st

ROLE_LABELS = {"admin": "Administrateur", "editeur": "Éditeur", "lecteur": "Lecteur"}


def _comptes():
    try:
        raw = st.secrets["auth"]["users"]
    except Exception:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else list(raw)
    except Exception:
        return None


def _verifie(saisie: str, stocke: str) -> bool:
    # Accepte un mot de passe en clair OU un hash sha256 (préfixé "sha256:")
    if stocke.startswith("sha256:"):
        return hashlib.sha256(saisie.encode()).hexdigest() == stocke.split(":", 1)[1]
    return saisie == stocke


def utilisateur_courant() -> dict | None:
    return st.session_state.get("auth_user")


def role() -> str:
    u = utilisateur_courant()
    return u["role"] if u else "admin"


def peut_editer() -> bool:
    return role() in ("admin", "editeur")


def est_admin() -> bool:
    return role() == "admin"


def login_gate() -> bool:
    """Affiche le formulaire de connexion si nécessaire. Retourne True si connecté."""
    comptes = _comptes()

    # Mode ouvert (pas de comptes configurés) -> admin implicite
    if not comptes:
        if "auth_user" not in st.session_state:
            st.session_state["auth_user"] = {"login": "local", "nom": "Utilisateur local",
                                             "role": "admin"}
            st.session_state["utilisateur"] = "local"
        return True

    if utilisateur_courant():
        return True

    st.markdown("## 🛡️ VigieFlotte — Connexion")
    st.caption("Veuillez vous identifier pour accéder à l'application.")
    with st.form("login"):
        login = st.text_input("Identifiant")
        mdp = st.text_input("Mot de passe", type="password")
        ok = st.form_submit_button("Se connecter", type="primary")
    if ok:
        for c in comptes:
            if c.get("login") == login and _verifie(mdp, str(c.get("mot_de_passe", ""))):
                st.session_state["auth_user"] = {
                    "login": login, "nom": c.get("nom", login),
                    "role": c.get("role", "lecteur")}
                st.session_state["utilisateur"] = login
                st.rerun()
        st.error("Identifiant ou mot de passe incorrect.")
    return False


def logout():
    for k in ("auth_user", "utilisateur"):
        st.session_state.pop(k, None)
    st.rerun()
