"""
db.py — Connexion Neon (PostgreSQL), schéma et accès aux données.

Tables : vehicles, documents, porte_chars_couples, paiements (coûts),
pieces_jointes (scans), audit_log (traçabilité).
Repli SQLite local (./fleet_local.db) si aucun secret Neon.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


# --- Schéma ------------------------------------------------------------------
SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS vehicles (
        id                  SERIAL PRIMARY KEY,
        categorie           VARCHAR(10)  NOT NULL,
        code_interne        VARCHAR(60),
        immatriculation     VARCHAR(60),
        type_vehicule       VARCHAR(120),
        marque              VARCHAR(120),
        modele              VARCHAR(200),
        id_chassis          VARCHAR(120),
        nb_roues            VARCHAR(20),
        age                 VARCHAR(20),
        date_mise_circulation DATE,
        nb_places           VARCHAR(20),
        charge_utile        VARCHAR(40),
        puissance_cv        VARCHAR(40),
        couleur             VARCHAR(60),
        n_carte_grise       VARCHAR(80),
        cree_le             TIMESTAMP DEFAULT NOW(),
        maj_le              TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id                  SERIAL PRIMARY KEY,
        vehicle_id          INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
        type_doc            VARCHAR(40) NOT NULL,
        possede             BOOLEAN,
        date_expiration     DATE,
        date_dernier_renouv DATE,
        notes               VARCHAR(300),
        maj_le              TIMESTAMP DEFAULT NOW(),
        UNIQUE (vehicle_id, type_doc)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS porte_chars_couples (
        id                  SERIAL PRIMARY KEY,
        vehicule_a          VARCHAR(60) NOT NULL,
        vehicule_b          VARCHAR(60) NOT NULL,
        date_expiration     DATE,
        notes               VARCHAR(300),
        maj_le              TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paiements (
        id                  SERIAL PRIMARY KEY,
        vehicle_id          INTEGER REFERENCES vehicles(id) ON DELETE CASCADE,
        type_doc            VARCHAR(40),
        montant             NUMERIC(14,2),
        date_paiement       DATE,
        notes               VARCHAR(300),
        cree_le             TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pieces_jointes (
        id                  SERIAL PRIMARY KEY,
        vehicle_id          INTEGER REFERENCES vehicles(id) ON DELETE CASCADE,
        type_doc            VARCHAR(40),
        nom_fichier         VARCHAR(255),
        mime                VARCHAR(120),
        contenu             BYTEA,
        taille              INTEGER,
        cree_le             TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id                  SERIAL PRIMARY KEY,
        horodatage          TIMESTAMP DEFAULT NOW(),
        utilisateur         VARCHAR(80),
        action              VARCHAR(30),
        cible               VARCHAR(160),
        details             VARCHAR(600)
    )
    """,
]


@st.cache_resource
def get_engine():
    url = None
    try:
        url = st.secrets["neon"]["url"]
    except Exception:
        url = None
    if url:
        return create_engine(url, pool_pre_ping=True, pool_recycle=300)
    return create_engine("sqlite:///fleet_local.db")


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"


def init_db():
    eng = get_engine()
    ddl = SCHEMA
    if not is_postgres():
        ddl = [
            s.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
             .replace("TIMESTAMP DEFAULT NOW()", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
             .replace("BYTEA", "BLOB")
             .replace("NUMERIC(14,2)", "REAL")
            for s in SCHEMA
        ]
    with eng.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))


def table_vide(nom: str) -> bool:
    eng = get_engine()
    with eng.connect() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM {nom}")).scalar()
    return (n or 0) == 0


# --- Audit -------------------------------------------------------------------
def _utilisateur() -> str:
    try:
        return st.session_state.get("utilisateur", "système") or "système"
    except Exception:
        return "système"


def log_audit(conn, action: str, cible: str, details: str = ""):
    """Journalise une opération dans la transaction courante."""
    now_fn = "NOW()" if is_postgres() else "CURRENT_TIMESTAMP"
    conn.execute(text(f"""
        INSERT INTO audit_log (horodatage, utilisateur, action, cible, details)
        VALUES ({now_fn}, :u, :a, :c, :d)
    """), dict(u=_utilisateur(), a=action, c=cible[:160], d=(details or "")[:600]))


@st.cache_data(ttl=60)
def load_audit(limite: int = 500) -> pd.DataFrame:
    eng = get_engine()
    return pd.read_sql(text("SELECT * FROM audit_log ORDER BY id DESC LIMIT :l"),
                       eng, params={"l": limite})


# --- Lectures ----------------------------------------------------------------
@st.cache_data(ttl=120)
def load_vehicles(categorie: str | None = None) -> pd.DataFrame:
    eng = get_engine()
    q = "SELECT * FROM vehicles"
    params = {}
    if categorie:
        q += " WHERE categorie = :c"
        params["c"] = categorie
    q += " ORDER BY code_interne, immatriculation"
    return pd.read_sql(text(q), eng, params=params)


@st.cache_data(ttl=120)
def load_documents() -> pd.DataFrame:
    eng = get_engine()
    return pd.read_sql(text("SELECT * FROM documents"), eng)


@st.cache_data(ttl=120)
def load_couples() -> pd.DataFrame:
    eng = get_engine()
    return pd.read_sql(text("SELECT * FROM porte_chars_couples ORDER BY date_expiration"), eng)


@st.cache_data(ttl=120)
def load_paiements() -> pd.DataFrame:
    eng = get_engine()
    return pd.read_sql(text("SELECT * FROM paiements ORDER BY date_paiement DESC"), eng)


# --- Écritures ---------------------------------------------------------------
def _flush():
    st.cache_data.clear()


def _vehicle_label(conn, vehicle_id):
    r = conn.execute(text("SELECT immatriculation, code_interne FROM vehicles WHERE id=:v"),
                     {"v": vehicle_id}).fetchone()
    if not r:
        return f"#{vehicle_id}"
    return (r[0] or r[1] or f"#{vehicle_id}")


def upsert_document(vehicle_id: int, type_doc: str, possede, date_expiration,
                    date_dernier_renouv=None, notes=None):
    eng = get_engine()
    with eng.begin() as conn:
        old = conn.execute(text(
            "SELECT possede, date_expiration FROM documents WHERE vehicle_id=:v AND type_doc=:t"),
            {"v": vehicle_id, "t": type_doc}).fetchone()
        if is_postgres():
            conn.execute(text("""
                INSERT INTO documents (vehicle_id, type_doc, possede, date_expiration, date_dernier_renouv, notes)
                VALUES (:vid, :td, :p, :de, :dr, :n)
                ON CONFLICT (vehicle_id, type_doc) DO UPDATE
                  SET possede=:p, date_expiration=:de, date_dernier_renouv=:dr,
                      notes=:n, maj_le=NOW()
            """), dict(vid=vehicle_id, td=type_doc, p=possede, de=date_expiration,
                       dr=date_dernier_renouv, n=notes))
        else:
            conn.execute(text("""
                INSERT INTO documents (vehicle_id, type_doc, possede, date_expiration, date_dernier_renouv, notes)
                VALUES (:vid, :td, :p, :de, :dr, :n)
                ON CONFLICT (vehicle_id, type_doc) DO UPDATE
                  SET possede=:p, date_expiration=:de, date_dernier_renouv=:dr, notes=:n
            """), dict(vid=vehicle_id, td=type_doc, p=possede, de=date_expiration,
                       dr=date_dernier_renouv, n=notes))
        anc = f"{old[0] if old else None}/{old[1] if old else None}"
        nouv = f"{possede}/{date_expiration}"
        if anc != nouv:
            log_audit(conn, "pièce", f"{_vehicle_label(conn, vehicle_id)} · {type_doc}",
                      f"{anc} → {nouv}")
    _flush()


def update_vehicle_fields(vehicle_id: int, fields: dict):
    if not fields:
        return
    eng = get_engine()
    with eng.begin() as conn:
        old = conn.execute(text(f"SELECT {', '.join(fields.keys())} FROM vehicles WHERE id=:v"),
                           {"v": vehicle_id}).fetchone()
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        conn.execute(text(f"UPDATE vehicles SET {sets} WHERE id = :vid"),
                     dict(fields, vid=vehicle_id))
        changes = []
        if old is not None:
            for i, k in enumerate(fields.keys()):
                if str(old[i] or "") != str(fields[k] or ""):
                    changes.append(f"{k}: {old[i]}→{fields[k]}")
        if changes:
            log_audit(conn, "véhicule", _vehicle_label(conn, vehicle_id),
                      " ; ".join(changes))
    _flush()


def insert_vehicle(data: dict) -> int:
    eng = get_engine()
    cols = ", ".join(data.keys())
    ph = ", ".join(f":{k}" for k in data)
    with eng.begin() as conn:
        if is_postgres():
            vid = conn.execute(
                text(f"INSERT INTO vehicles ({cols}) VALUES ({ph}) RETURNING id"), data).scalar()
        else:
            vid = conn.execute(text(f"INSERT INTO vehicles ({cols}) VALUES ({ph})"), data).lastrowid
        log_audit(conn, "création", data.get("immatriculation") or data.get("code_interne") or f"#{vid}",
                  f"catégorie {data.get('categorie')}")
    _flush()
    return int(vid)


def delete_vehicle(vehicle_id: int):
    eng = get_engine()
    with eng.begin() as conn:
        lbl = _vehicle_label(conn, vehicle_id)
        if not is_postgres():
            conn.execute(text("DELETE FROM documents WHERE vehicle_id = :v"), {"v": vehicle_id})
            conn.execute(text("DELETE FROM paiements WHERE vehicle_id = :v"), {"v": vehicle_id})
            conn.execute(text("DELETE FROM pieces_jointes WHERE vehicle_id = :v"), {"v": vehicle_id})
        conn.execute(text("DELETE FROM vehicles WHERE id = :v"), {"v": vehicle_id})
        log_audit(conn, "suppression", lbl, "véhicule supprimé")
    _flush()


def upsert_couple(vehicule_a, vehicule_b, date_expiration, notes=None, couple_id=None):
    eng = get_engine()
    with eng.begin() as conn:
        if couple_id:
            conn.execute(text("""
                UPDATE porte_chars_couples
                   SET vehicule_a=:a, vehicule_b=:b, date_expiration=:d, notes=:n
                 WHERE id=:id
            """), dict(a=vehicule_a, b=vehicule_b, d=date_expiration, n=notes, id=couple_id))
            log_audit(conn, "couple", f"{vehicule_a} & {vehicule_b}", f"échéance {date_expiration}")
        else:
            conn.execute(text("""
                INSERT INTO porte_chars_couples (vehicule_a, vehicule_b, date_expiration, notes)
                VALUES (:a, :b, :d, :n)
            """), dict(a=vehicule_a, b=vehicule_b, d=date_expiration, n=notes))
            log_audit(conn, "création", f"{vehicule_a} & {vehicule_b}", "couple porte-chars")
    _flush()


def delete_couple(couple_id: int):
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM porte_chars_couples WHERE id = :id"), {"id": couple_id})
        log_audit(conn, "suppression", f"couple #{couple_id}", "couple supprimé")
    _flush()


# --- Paiements (coûts) -------------------------------------------------------
def insert_paiement(vehicle_id, type_doc, montant, date_paiement, notes=None):
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO paiements (vehicle_id, type_doc, montant, date_paiement, notes)
            VALUES (:v, :t, :m, :d, :n)
        """), dict(v=vehicle_id, t=type_doc, m=montant, d=date_paiement, n=notes))
        log_audit(conn, "paiement", _vehicle_label(conn, vehicle_id) if vehicle_id else "—",
                  f"{type_doc} · {montant} FCFA")
    _flush()


def delete_paiement(paiement_id: int):
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM paiements WHERE id = :id"), {"id": paiement_id})
    _flush()


# --- Pièces jointes (scans) --------------------------------------------------
def insert_piece_jointe(vehicle_id, type_doc, nom_fichier, mime, contenu: bytes):
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO pieces_jointes (vehicle_id, type_doc, nom_fichier, mime, contenu, taille)
            VALUES (:v, :t, :nom, :m, :c, :s)
        """), dict(v=vehicle_id, t=type_doc, nom=nom_fichier, m=mime,
                   c=contenu, s=len(contenu)))
        log_audit(conn, "scan", _vehicle_label(conn, vehicle_id), f"{type_doc} · {nom_fichier}")
    _flush()


@st.cache_data(ttl=120)
def load_pieces_jointes_meta(vehicle_id=None) -> pd.DataFrame:
    eng = get_engine()
    q = ("SELECT id, vehicle_id, type_doc, nom_fichier, mime, taille, cree_le "
         "FROM pieces_jointes")
    params = {}
    if vehicle_id is not None:
        q += " WHERE vehicle_id = :v"
        params["v"] = vehicle_id
    q += " ORDER BY id DESC"
    return pd.read_sql(text(q), eng, params=params)


def get_piece_jointe(piece_id: int):
    eng = get_engine()
    with eng.connect() as conn:
        r = conn.execute(text("SELECT nom_fichier, mime, contenu FROM pieces_jointes WHERE id=:i"),
                         {"i": piece_id}).fetchone()
    if not r:
        return None
    contenu = r[2]
    if contenu is not None and not isinstance(contenu, (bytes, bytearray)):
        contenu = bytes(contenu)
    return {"nom": r[0], "mime": r[1], "contenu": contenu}


def delete_piece_jointe(piece_id: int):
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM pieces_jointes WHERE id = :i"), {"i": piece_id})
    _flush()
