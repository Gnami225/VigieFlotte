"""
alertes_mail.py — Alertes e-mail des pièces à échéance.

Deux usages :
  1) Script planifié (cron / GitHub Actions) :  python alertes_mail.py
  2) Depuis l'application (bouton « Envoyer maintenant »).

Configuration via st.secrets["email"] OU variables d'environnement :
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO
  (EMAIL_TO = liste séparée par des virgules), SEUIL_JOURS (défaut 60)
Et la connexion Neon via NEON_URL (script) ou st.secrets["neon"]["url"] (app).
"""
from __future__ import annotations
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text

import rules


# --- Configuration -----------------------------------------------------------
def _conf(cle, defaut=None):
    val = os.environ.get(cle)
    if val is not None:
        return val
    try:
        import streamlit as st
        return st.secrets["email"].get(cle.lower(), defaut)
    except Exception:
        return defaut


def _engine():
    url = os.environ.get("NEON_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets["neon"]["url"]
        except Exception:
            url = "sqlite:///fleet_local.db"
    return create_engine(url, pool_pre_ping=True)


# --- Calcul des pièces en alerte --------------------------------------------
def pieces_en_alerte(seuil_jours: int = 60) -> pd.DataFrame:
    eng = _engine()
    veh = pd.read_sql(text("SELECT * FROM vehicles"), eng)
    docs = pd.read_sql(text("SELECT * FROM documents"), eng)
    if docs.empty:
        return pd.DataFrame()
    df = docs.merge(veh[["id", "immatriculation", "type_vehicule"]],
                    left_on="vehicle_id", right_on="id", suffixes=("", "_v"))
    lignes = []
    today = date.today()
    for _, r in df.iterrows():
        de = r["date_expiration"]
        de = pd.to_datetime(de).date() if pd.notna(de) and de is not None else None
        possede = None if pd.isna(r["possede"]) else bool(r["possede"])
        code, ech, j = rules.compute_etat(r["type_doc"], possede, de, today)
        if code in (rules.EXPIRE, rules.A_RENOUVELER) or (j is not None and j <= seuil_jours):
            lignes.append({
                "Immatriculation": r["immatriculation"],
                "Type": r["type_vehicule"],
                "Pièce": rules.DOC_TYPES.get(r["type_doc"], {}).get("label", r["type_doc"]),
                "Échéance": ech.strftime("%d/%m/%Y") if ech else "",
                "Jours restants": j if j is not None else "",
                "État": rules.ETAT_LABEL.get(code, code),
            })
    # Couples porte-chars
    couples = pd.read_sql(text("SELECT * FROM porte_chars_couples"), eng)
    for _, r in couples.iterrows():
        de = r["date_expiration"]
        de = pd.to_datetime(de).date() if pd.notna(de) and de is not None else None
        code, ech, j = rules.compute_etat("porte_chars", True, de, today)
        if code in (rules.EXPIRE, rules.A_RENOUVELER) or (j is not None and j <= seuil_jours):
            lignes.append({
                "Immatriculation": f"{r['vehicule_a']} & {r['vehicule_b']}",
                "Type": "Porte-chars (couple)",
                "Pièce": "Autorisation porte-chars",
                "Échéance": ech.strftime("%d/%m/%Y") if ech else "",
                "Jours restants": j if j is not None else "",
                "État": rules.ETAT_LABEL.get(code, code),
            })
    out = pd.DataFrame(lignes)
    if not out.empty:
        out = out.sort_values("Jours restants",
                              key=lambda s: pd.to_numeric(s, errors="coerce"))
    return out


def _corps_html(df: pd.DataFrame, seuil: int) -> str:
    if df.empty:
        return "<p>Aucune pièce en alerte. Flotte à jour ✅</p>"
    lignes = "".join(
        f"<tr><td>{r['Immatriculation']}</td><td>{r['Pièce']}</td>"
        f"<td>{r['Échéance']}</td><td style='text-align:center'>{r['Jours restants']}</td>"
        f"<td>{r['État']}</td></tr>" for _, r in df.iterrows())
    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;color:#2a2f25">
      <h2 style="color:#6f7d3f">VigieFlotte — Pièces à traiter (≤ {seuil} jours)</h2>
      <p>{len(df)} pièce(s) nécessitent une action. Généré le {date.today().strftime('%d/%m/%Y')}.</p>
      <table style="border-collapse:collapse;width:100%" border="1" cellpadding="6">
        <thead style="background:#6f7d3f;color:#fff">
          <tr><th>Véhicule</th><th>Pièce</th><th>Échéance</th><th>Jours</th><th>État</th></tr>
        </thead><tbody>{lignes}</tbody>
      </table>
    </div>"""


def envoyer(seuil_jours: int | None = None) -> dict:
    seuil = int(seuil_jours or _conf("SEUIL_JOURS", 60) or 60)
    df = pieces_en_alerte(seuil)

    host = _conf("SMTP_HOST"); port = int(_conf("SMTP_PORT", 587) or 587)
    user = _conf("SMTP_USER"); pwd = _conf("SMTP_PASSWORD")
    exp = _conf("EMAIL_FROM", user)
    dest = _conf("EMAIL_TO", "")
    destinataires = [d.strip() for d in str(dest).split(",") if d.strip()]

    if not (host and exp and destinataires):
        return {"ok": False, "raison": "Configuration SMTP incomplète",
                "nb": len(df)}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[VigieFlotte] {len(df)} pièce(s) à traiter sous {seuil} jours"
    msg["From"] = exp
    msg["To"] = ", ".join(destinataires)
    msg.attach(MIMEText(_corps_html(df, seuil), "html", "utf-8"))

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        if user and pwd:
            s.login(user, pwd)
        s.sendmail(exp, destinataires, msg.as_string())
    return {"ok": True, "nb": len(df), "destinataires": destinataires}


if __name__ == "__main__":
    res = envoyer()
    print(res)
