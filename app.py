"""
app.py — VigieFlotte · Gestion des pièces administratives de flotte
Streamlit + Neon (PostgreSQL). Suivi documentaire des camions et engins (BTP) :
édition, alertes, coûts, pièces jointes, audit, exports et alertes e-mail.

Lancement local :  streamlit run app.py
"""
from __future__ import annotations
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import rules
import db as DB
import ui
import seed as SEED
import auth
import exports
import alertes_mail

APP_NOM = "VigieFlotte"

st.set_page_config(page_title=f"{APP_NOM} · Pièces administratives",
                   page_icon="🛡️", layout="wide",
                   initial_sidebar_state="expanded")

# --- Style global (premium clair · vert olive & blanc) ----------------------
OLIVE = "#6f7d3f"
OLIVE_FONCE = "#5a6733"
OLIVE_CLAIR = "#9aa86a"
CREME = "#f7f8f2"
ENCRE = "#2a2f25"
ENCRE2 = "#5b6354"

st.markdown(f"""
<style>
  :root {{ --olive:{OLIVE}; --olive-d:{OLIVE_FONCE}; --encre:{ENCRE}; }}
  .stApp {{background: {CREME} !important;}}
  .block-container {{padding-top: 1.6rem; max-width: 1500px;}}

  /* Texte foncé forcé partout (indépendant du thème actif) */
  .stApp, .stApp p, .stApp span, .stApp li, .stApp label, .stApp div,
  .stMarkdown, [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
  [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {{color: {ENCRE};}}
  h1, h2, h3, h4 {{color: {ENCRE} !important; letter-spacing: -0.01em;}}
  h1 {{font-weight: 700;}}
  [data-testid="stCaptionContainer"], .stApp small {{color: {ENCRE2} !important;}}

  /* Bandeau supérieur + en-tête : on retire le bleu/gradient par défaut */
  [data-testid="stDecoration"] {{
      background: linear-gradient(90deg, {OLIVE}, {OLIVE_CLAIR}) !important;}}
  [data-testid="stHeader"] {{background: rgba(247,248,242,0.85) !important;
      backdrop-filter: blur(6px);}}

  /* Barre latérale claire */
  section[data-testid="stSidebar"] {{background: #ffffff !important;
      border-right: 1px solid #e7e9dd;}}
  section[data-testid="stSidebar"] * {{color: {ENCRE} !important;}}
  /* item de navigation actif en olive */
  section[data-testid="stSidebar"] a[aria-current="page"] {{
      background: {OLIVE}14 !important; color: {OLIVE_FONCE} !important;
      border-radius: 10px;}}

  /* Cartes KPI */
  .kpi {{background: #ffffff; border: 1px solid #e7e9dd; border-radius: 16px;
        padding: 18px 20px; box-shadow: 0 1px 2px rgba(40,47,30,.05),
        0 6px 16px rgba(40,47,30,.04);}}
  .kpi .v {{font-size: 2rem; font-weight: 700; line-height: 1.05;}}
  .kpi .l {{font-size: 0.76rem; color: {ENCRE2} !important; text-transform: uppercase;
           letter-spacing: 0.06em; margin-top: 4px;}}

  /* Graphiques sur carte blanche */
  .stPlotlyChart {{background: #ffffff; border: 1px solid #e7e9dd;
      border-radius: 16px; padding: 10px 12px;
      box-shadow: 0 1px 2px rgba(40,47,30,.05), 0 6px 16px rgba(40,47,30,.04);}}

  /* Champs de saisie */
  .stTextInput input, .stDateInput input, .stNumberInput input,
  [data-baseweb="select"] > div {{background: #ffffff !important;
      color: {ENCRE} !important; border-color: #d6dac6 !important;}}
  [data-baseweb="select"] > div:focus-within {{border-color: {OLIVE} !important;
      box-shadow: 0 0 0 2px {OLIVE}33 !important;}}

  /* BOUTONS — tout en olive, plus aucun bleu ni transparence douteuse */
  .stButton button, [data-testid="stDownloadButton"] button,
  [data-testid="stFormSubmitButton"] button {{
      border-radius: 10px !important; font-weight: 600 !important;
      transition: all .15s ease;}}
  .stButton button[kind="primary"], [data-testid="stDownloadButton"] button,
  [data-testid="stFormSubmitButton"] button[kind="primary"] {{
      background: {OLIVE} !important; border: 1px solid {OLIVE} !important;
      color: #ffffff !important;}}
  .stButton button[kind="primary"]:hover, [data-testid="stDownloadButton"] button:hover {{
      background: {OLIVE_FONCE} !important; border-color: {OLIVE_FONCE} !important;}}
  .stButton button[kind="secondary"] {{
      background: #ffffff !important; border: 1px solid {OLIVE} !important;
      color: {OLIVE_FONCE} !important;}}
  .stButton button[kind="secondary"]:hover {{background: {OLIVE}10 !important;}}

  /* Onglets, curseur, cases : accent olive */
  .stTabs [data-baseweb="tab-list"] {{gap: 6px; border-bottom: 1px solid #e7e9dd;}}
  .stTabs [data-baseweb="tab"] {{color: {ENCRE2};}}
  .stTabs [aria-selected="true"] {{color: {OLIVE_FONCE} !important;}}
  .stTabs [data-baseweb="tab-highlight"] {{background: {OLIVE} !important;}}
  .stSlider [data-baseweb="slider"] div[role="slider"] {{background: {OLIVE} !important;}}
  .stSlider [data-baseweb="slider"] > div > div > div {{background: {OLIVE} !important;}}

  /* Alertes : info en olive (au lieu du bleu) ; succès/avertissement/erreur conservés */
  .stAlert:has([data-testid="stAlertContentInfo"]) {{
      background: {OLIVE}12 !important; border: 1px solid {OLIVE}33 !important;}}
  div[data-testid="stDataFrame"] {{border: 1px solid #e7e9dd; border-radius: 12px;}}
</style>
""", unsafe_allow_html=True)

# --- Plotly : style premium clair + interactivité ----------------------------
COULEURS_ETAT = {
    "À jour": "#3f7d3a", "Détenu": "#3f7d3a", "À renouveler": "#c0832b",
    "À renseigner": "#b08a2c", "Expiré": "#c0392b", "Non détenu": "#7a8270",
}
SEQ_OLIVE = ["#6f7d3f", "#9aa86a", "#bcc792", "#4f5a2c", "#d4dcb6"]
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True,
                 "scrollZoom": False, "doubleClick": "reset"}


def style_fig(fig, height=None, legend_bottom=False):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=ENCRE, size=12,
                  family="Inter, 'Segoe UI', system-ui, sans-serif"),
        margin=dict(t=14, b=14, l=12, r=12),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#d6dac6",
                        font=dict(color=ENCRE, size=12)),
        colorway=SEQ_OLIVE,
    )
    fig.update_xaxes(tickfont=dict(color=ENCRE2), title_font=dict(color=ENCRE2),
                     gridcolor="#edefe2", zerolinecolor="#e7e9dd",
                     linecolor="#e7e9dd", automargin=True)
    fig.update_yaxes(tickfont=dict(color=ENCRE2), title_font=dict(color=ENCRE2),
                     gridcolor="#edefe2", zerolinecolor="#e7e9dd",
                     linecolor="#e7e9dd", automargin=True)
    if legend_bottom:
        fig.update_layout(legend=dict(orientation="h", y=-0.16, x=0,
                                      font=dict(color=ENCRE)))
    else:
        fig.update_layout(legend=dict(font=dict(color=ENCRE)))
    if height:
        fig.update_layout(height=height)
    return fig


def show_chart(fig, **kw):
    # theme=None coupe l'injection du thème Streamlit (qui rendait le texte blanc)
    st.plotly_chart(fig, use_container_width=True, theme=None,
                    config=PLOTLY_CONFIG, **kw)


# --- Initialisation (schéma + seed au premier lancement) --------------------
@st.cache_resource
def _bootstrap():
    try:
        return SEED.run_seed(force=False)
    except Exception as e:
        return {"erreur": str(e), "vehicles": 0, "couples": 0}


def _kpi(col, valeur, libelle, couleur="#b0892c"):
    col.markdown(
        f"<div class='kpi'><div class='v' style='color:{couleur}'>{valeur}</div>"
        f"<div class='l'>{libelle}</div></div>", unsafe_allow_html=True)


def _data():
    veh = DB.load_vehicles()
    docs = DB.load_documents()
    couples = DB.load_couples()
    enr = ui.enrich_documents(veh, docs)
    return veh, docs, couples, enr


def _couples_enrichis(couples: pd.DataFrame) -> pd.DataFrame:
    if couples.empty:
        return couples
    df = couples.copy()
    etats, jours = [], []
    today = date.today()
    for _, r in df.iterrows():
        de = r["date_expiration"]
        de = pd.to_datetime(de).date() if pd.notna(de) and de is not None else None
        code, _, j = rules.compute_etat("porte_chars", True, de, today)
        etats.append(code)
        jours.append(j)
    df["etat"] = etats
    df["etat_label"] = df["etat"].map(rules.ETAT_LABEL)
    df["jours_restants"] = jours
    return df


def _completude(enr: pd.DataFrame) -> float:
    """% de pièces effectivement renseignées (hors état « à renseigner »)."""
    if enr.empty:
        return 0.0
    n_ok = int((enr["etat"] != rules.A_RENSEIGNER).sum())
    return round(100 * n_ok / len(enr), 1)


def _rapprochement_couples(veh: pd.DataFrame, couples: pd.DataFrame) -> list[str]:
    """Signale les immatriculations des couples absentes de la base camions."""
    if couples.empty:
        return []
    immats = set(str(x).strip().upper() for x in veh["immatriculation"].dropna())
    def _norm(x):
        return str(x or "").strip().upper()
    anomalies = []
    for _, r in couples.iterrows():
        for v in (r["vehicule_a"], r["vehicule_b"]):
            if _norm(v) and _norm(v) not in immats:
                anomalies.append(str(v).strip())
    # dédoublonnage en gardant l'ordre
    vus, uniques = set(), []
    for a in anomalies:
        if a.upper() not in vus:
            vus.add(a.upper())
            uniques.append(a)
    return uniques


# ============================================================================
# PAGE — TABLEAU DE BORD
# ============================================================================
def page_dashboard():
    st.title("Tableau de bord")
    veh, docs, couples, enr = _data()
    if veh.empty:
        st.warning("Aucune donnée. Utilisez la page **Import / Admin** pour charger les bases.")
        return

    couples_e = _couples_enrichis(couples)
    nb_total = len(veh)
    nb_camions = int((veh["categorie"] == "camion").sum())
    nb_engins = int((veh["categorie"] == "engin").sum())

    # Documents soumis à échéance (hors possession pure)
    docs_dates = enr[enr["echeance"].notna()]
    nb_expire = int((enr["etat"] == rules.EXPIRE).sum())
    nb_renouv = int((enr["etat"] == rules.A_RENOUVELER).sum())
    nb_conf = int(enr["etat"].isin(rules.CONFORMES).sum())
    taux = 100 * nb_conf / len(enr) if len(enr) else 0
    nb_alerte_pc = int((couples_e["etat"].isin([rules.A_RENOUVELER, rules.EXPIRE])).sum()) \
        if not couples_e.empty else 0

    c = st.columns(6)
    _kpi(c[0], nb_total, "Véhicules", "#b0892c")
    _kpi(c[1], f"{taux:.0f}%", "Pièces conformes", ui.PALETTE["vert"])
    _kpi(c[2], nb_expire, "Pièces expirées", ui.PALETTE["rouge"])
    _kpi(c[3], nb_renouv, "À renouveler", ui.PALETTE["ambre"])
    _kpi(c[4], nb_alerte_pc, "Alertes porte-chars", ui.PALETTE["rouge"])
    _kpi(c[5], f"{_completude(enr):.0f}%", "Complétude données", "#6f7d3f")

    # Rapprochement camions <-> couples porte-chars
    anomalies = _rapprochement_couples(veh, couples)
    if anomalies:
        st.warning("**Rapprochement porte-chars :** immatriculation(s) référencée(s) "
                   "dans les couples mais absente(s) de la base camions — "
                   + ", ".join(anomalies) + ". Vérifiez la saisie ou l'état du véhicule.")

    # Barre d'exports (livrables figés)
    e1, e2, e3 = st.columns([1.1, 1.1, 4])
    xls = exports.build_excel(veh, enr, couples_e, DB.load_paiements())
    e1.download_button("⬇️ Export Excel", xls,
                       file_name=f"vigieflotte_{date.today():%Y%m%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    pdf = exports.build_pdf(veh, enr, couples_e)
    if pdf:
        e2.download_button("⬇️ Export PDF", pdf,
                           file_name=f"vigieflotte_{date.today():%Y%m%d}.pdf",
                           mime="application/pdf")
    else:
        e2.caption("PDF indisponible (reportlab non installé).")

    st.markdown("")
    g1, g2 = st.columns([1, 1.3])
    cmap = COULEURS_ETAT

    # Donut répartition des états (tous documents)
    with g1:
        st.subheader("Répartition des états")
        rep = enr["etat_label"].value_counts().reset_index()
        rep.columns = ["etat", "n"]
        fig = px.pie(rep, names="etat", values="n", hole=0.62,
                     color="etat", color_discrete_map=cmap)
        fig.update_traces(
            textposition="outside", textinfo="percent+label",
            marker=dict(line=dict(color="#ffffff", width=2.5)),
            hovertemplate="<b>%{label}</b><br>%{value} pièces · %{percent}<extra></extra>",
            pull=[0.015] * len(rep))
        fig.add_annotation(text=f"<b>{len(enr)}</b><br>pièces", showarrow=False,
                           font=dict(size=18, color=ENCRE))
        fig.update_layout(showlegend=False)
        show_chart(style_fig(fig, height=360))

    # Barres empilées par type de document
    with g2:
        st.subheader("État par type de pièce")
        gp = (enr.groupby(["doc_label", "etat_label"]).size()
              .reset_index(name="n"))
        ordre = gp.groupby("doc_label")["n"].sum().sort_values().index.tolist()
        fig = px.bar(gp, x="n", y="doc_label", color="etat_label",
                     orientation="h", color_discrete_map=cmap,
                     category_orders={"doc_label": ordre})
        fig.update_traces(marker_line_width=0,
                          hovertemplate="%{y} · <b>%{x}</b> %{fullData.name}<extra></extra>")
        fig.update_layout(barmode="stack", legend_title="",
                          yaxis_title="", xaxis_title="Nombre de pièces",
                          bargap=0.35)
        fig.update_yaxes(automargin=True, tickfont=dict(size=13, color=ENCRE))
        show_chart(style_fig(fig, height=380, legend_bottom=True))

    g3, g4 = st.columns([1.35, 1])

    # Heatmap véhicules × types (camions) — visuel « statisticien »
    with g3:
        st.subheader("Carte de conformité — camions")
        st.caption("Vert = à jour · jaune/ambre = à renouveler ou à renseigner · "
                   "rouge = expiré. Survolez une case pour le détail.")
        wide = ui.pivot_etats(enr, veh, "camion")
        if not wide.empty:
            types = [rules.DOC_TYPES[t]["label"] for t in rules.DOC_TYPES
                     if "camion" in rules.DOC_TYPES[t]["cats"]]
            score = {"À jour": 3, "Détenu": 3, "À renouveler": 1.5,
                     "À renseigner": 0.6, "Non détenu": 0.6, "Expiré": 0, "—": None}
            wide2 = wide.set_index("immatriculation")
            M = wide2[types].replace(score).apply(pd.to_numeric, errors="coerce")
            labels = wide2[types].values
            fig = go.Figure(data=go.Heatmap(
                z=M.values, x=types, y=M.index.tolist(),
                customdata=labels,
                colorscale=[[0, "#c0392b"], [0.2, "#e07b39"],
                            [0.5, "#e9c46a"], [1, "#3f7d3a"]],
                showscale=False, xgap=3, ygap=3,
                hovertemplate="<b>%{y}</b><br>%{x} : %{customdata}<extra></extra>"))
            fig.update_layout(yaxis=dict(tickfont=dict(size=9),
                                         autorange="reversed"),
                              xaxis=dict(tickfont=dict(size=11), side="top"))
            show_chart(style_fig(fig, height=560))

    # Taux de conformité par catégorie
    with g4:
        st.subheader("Conformité par catégorie")
        rows = []
        for cat in ["camion", "engin"]:
            sub = enr[enr["categorie"] == cat]
            if len(sub):
                rows.append({"Catégorie": cat.capitalize(),
                             "Taux": 100 * sub["etat"].isin(rules.CONFORMES).sum() / len(sub)})
        if rows:
            dd = pd.DataFrame(rows)
            fig = px.bar(dd, x="Catégorie", y="Taux", color="Catégorie",
                         color_discrete_sequence=[OLIVE, OLIVE_CLAIR],
                         text=dd["Taux"].map(lambda v: f"{v:.0f}%"))
            fig.update_traces(textposition="outside", cliponaxis=False,
                              marker_line_width=0, width=0.55,
                              hovertemplate="%{x} · <b>%{y:.0f}%</b> conforme<extra></extra>")
            fig.update_layout(showlegend=False, yaxis_range=[0, 112],
                              yaxis_title="% conforme", xaxis_title="", bargap=0.4)
            show_chart(style_fig(fig, height=300))

        st.subheader("Échéances imminentes")
        proch = (docs_dates[docs_dates["jours_restants"].notna()
                            & (docs_dates["jours_restants"] <= 90)]
                 .sort_values("jours_restants"))
        if proch.empty:
            st.caption("Aucune échéance dans les 90 prochains jours.")
        else:
            view = proch[["immatriculation", "doc_label", "echeance", "jours_restants"]].head(12)
            view = view.rename(columns={"immatriculation": "Immat.",
                                        "doc_label": "Pièce", "echeance": "Échéance",
                                        "jours_restants": "Jours"})
            st.dataframe(view, use_container_width=True, hide_index=True, height=300)


# ============================================================================
# PAGE — VÉHICULES (générique camion / engin)
# ============================================================================
# ============================================================================
# PAGE — VÉHICULES (tableau de gestion éditable : camion / engin)
# ============================================================================
# Colonnes d'identité éditables -> colonne DB (propres à chaque catégorie)
IDENTITE_CAMION = {
    "Code": "code_interne", "Immat.": "immatriculation", "Type": "type_vehicule",
    "Marque": "marque", "Couleur": "couleur", "N° châssis": "id_chassis",
}
IDENTITE_ENGIN = {
    "Matricule": "code_interne", "Type": "type_vehicule", "Marque": "marque",
    "Distinction": "modele", "N° châssis": "id_chassis",
}


def _identite(categorie):
    return IDENTITE_ENGIN if categorie == "engin" else IDENTITE_CAMION
# Pièces éditables par catégorie : (type_doc, libellé colonne, nature)
#   nature "poss" -> liste Oui/Non/—   ;   nature "date" -> date d'échéance
DOC_COLS = {
    "camion": [
        ("carte_grise", "Carte grise", "poss"),
        ("carte_transport", "Transport — échéance", "date"),
        ("carte_stationnement", "Stationnement", "poss"),
        ("visite_technique", "Visite tech. — échéance", "date"),
        ("patente", "Patente", "poss"),
        ("assurance", "Assurance — échéance", "date"),
    ],
    "engin": [
        ("douanes", "Douanes", "poss"),
        ("assurance", "Assurance", "poss"),
    ],
}
_POSS_AFF = {True: "Oui", False: "Non", None: "—"}
_POSS_VAL = {"Oui": True, "Non": False, "—": None, "": None, None: None}


def _to_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    ts = pd.to_datetime(v, errors="coerce", dayfirst=True)
    return ts.date() if pd.notna(ts) else None


def _build_edit_df(veh, docs, categorie):
    identite = _identite(categorie)
    sub = veh[veh["categorie"] == categorie].copy()
    dmap = {}
    for r in docs.itertuples():
        dmap[(r.vehicle_id, r.type_doc)] = r
    rows = []
    for v in sub.itertuples():
        row = {"id": int(v.id)}
        for aff, col in identite.items():
            row[aff] = getattr(v, col, None)
        for key, label, nature in DOC_COLS[categorie]:
            d = dmap.get((int(v.id), key))
            if nature == "poss":
                pv = None if d is None or pd.isna(d.possede) else bool(d.possede)
                row[label] = _POSS_AFF[pv]
            else:
                row[label] = _to_date(d.date_expiration) if d is not None else None
        rows.append(row)
    cols = ["id"] + list(identite.keys()) + [l for _, l, _ in DOC_COLS[categorie]]
    df = pd.DataFrame(rows, columns=cols)
    # Force le type texte sur l'identité (évite l'inférence FLOAT sur colonnes vides)
    for aff in identite:
        df[aff] = df[aff].astype("string")
    return df


def _col_config(categorie):
    cfg = {"id": None}
    for aff in _identite(categorie):
        cfg[aff] = st.column_config.TextColumn(aff, width="small")
    for key, label, nature in DOC_COLS[categorie]:
        if nature == "poss":
            cfg[label] = st.column_config.SelectboxColumn(
                label, options=["Oui", "Non", "—"], required=False, width="small")
        else:
            cfg[label] = st.column_config.DateColumn(
                label, format="DD/MM/YYYY", width="small")
    return cfg


def _persist_edits(edited, original, shown_ids, categorie):
    """Écrit uniquement les lignes modifiées, créées ou supprimées."""
    identite = _identite(categorie)
    doc_labels = [l for _, l, _ in DOC_COLS[categorie]]
    orig_by_id = {int(r["id"]): r for _, r in original.iterrows()
                  if pd.notna(r["id"])}
    seen = set()
    crees = maj = suppr = 0

    def _norm(v):
        d = _to_date(v)
        if d is not None:
            return d.isoformat()
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        return str(v).strip()

    for _, row in edited.iterrows():
        vid = row.get("id")
        vals = {identite[a]: (str(row[a]).strip() or None)
                if pd.notna(row.get(a)) and str(row.get(a)).strip() != "" else None
                for a in identite}
        est_nouveau = pd.isna(vid)
        if est_nouveau and not any(vals.values()):
            continue

        if est_nouveau:
            vid = DB.insert_vehicle({"categorie": categorie, **vals})
            crees += 1
            _ecrire_docs(vid, row, categorie)
            continue

        vid = int(vid)
        seen.add(vid)
        orig = orig_by_id.get(vid)
        # Détecte un changement sur l'identité ou les pièces
        change = False
        if orig is not None:
            for a in identite:
                if _norm(row.get(a)) != _norm(orig.get(a)):
                    change = True
                    break
            if not change:
                for label in doc_labels:
                    if _norm(row.get(label)) != _norm(orig.get(label)):
                        change = True
                        break
        else:
            change = True
        if change:
            DB.update_vehicle_fields(vid, vals)
            _ecrire_docs(vid, row, categorie)
            maj += 1

    for vid in shown_ids - seen:
        DB.delete_vehicle(int(vid))
        suppr += 1
    return crees, maj, suppr


def _ecrire_docs(vid, row, categorie):
    for key, label, nature in DOC_COLS[categorie]:
        val = row.get(label)
        if nature == "poss":
            DB.upsert_document(vid, key,
                               _POSS_VAL.get(str(val) if val is not None else None), None)
        else:
            de = _to_date(val)
            DB.upsert_document(vid, key, True if de else None, de)


def page_vehicules(categorie: str, titre: str):
    st.title(titre)
    veh, docs, couples, enr = _data()
    sub = veh[veh["categorie"] == categorie]
    if sub.empty and veh.empty:
        st.warning("Aucune donnée chargée. Voir la page **Import / Admin**.")
        return

    editable = auth.peut_editer()
    tab_edit, tab_vue, tab_pj = st.tabs(
        ["📝 Tableau de gestion", "🎨 Vue conformité (filtres)", "📎 Pièces jointes"])

    # -------- Onglet édition : modifier, ajouter, supprimer --------
    with tab_edit:
        if editable:
            st.caption("Modifiez directement les cellules, ajoutez des lignes avec « + » "
                       "en bas du tableau, cochez une ligne pour la supprimer, puis "
                       "cliquez sur **Enregistrer**. Possession : Oui / Non / — (à renseigner). "
                       "Les échéances se saisissent au calendrier.")
        else:
            st.info("Mode lecture seule : vous pouvez consulter et exporter, "
                    "mais pas modifier (rôle « lecteur »).")
        c1, c2 = st.columns([3, 1])
        recherche = c1.text_input("🔎 Filtrer (immatriculation, code, marque, type)",
                                  key=f"search_{categorie}")
        df = _build_edit_df(veh, docs, categorie)
        if recherche:
            r = recherche.strip().lower()
            cols_id = list(_identite(categorie).keys())
            mask = df[cols_id].apply(
                lambda col: col.astype(str).str.lower().str.contains(r, na=False))
            df = df[mask.any(axis=1)]
        c2.metric("Lignes affichées", len(df))

        shown_ids = set(int(x) for x in df["id"].dropna().tolist())
        edited = st.data_editor(
            df, column_config=_col_config(categorie), hide_index=True,
            num_rows="dynamic" if editable else "fixed", disabled=not editable,
            use_container_width=True, height=560, key=f"editor_{categorie}")

        b1, b2, b3 = st.columns([1.2, 1, 3])
        if editable and b1.button("💾 Enregistrer les modifications", type="primary",
                                  key=f"save_{categorie}"):
            crees, maj, suppr = _persist_edits(edited, df, shown_ids, categorie)
            st.success(f"Enregistré : {maj} mise(s) à jour, {crees} création(s), "
                       f"{suppr} suppression(s).")
            st.rerun()
        b2.download_button("⬇️ Exporter (CSV)",
                           df.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
                           file_name=f"gestion_{categorie}.csv", mime="text/csv",
                           key=f"exp_{categorie}")

        if editable:
            with st.expander("🔄 Renouvellement rapide (calcule la prochaine échéance)"):
                sub2 = veh[veh["categorie"] == categorie].copy()
                sub2["lbl"] = sub2["immatriculation"].fillna("?") + " — " + \
                    sub2["code_interne"].fillna("?")
                datent = [(k, l) for k, l, n in DOC_COLS[categorie] if n == "date"]
                if datent:
                    e = st.columns([2, 1.5, 1])
                    sel = e[0].selectbox("Véhicule", sub2["lbl"].tolist(),
                                         key=f"rn_v_{categorie}")
                    doc = e[1].selectbox("Pièce", [l for _, l in datent],
                                         key=f"rn_d_{categorie}")
                    if e[2].button("Renouveler", key=f"rn_b_{categorie}"):
                        vid = int(sub2[sub2["lbl"] == sel].iloc[0]["id"])
                        key = [k for k, l in datent if l == doc][0]
                        cur = docs[(docs["vehicle_id"] == vid) & (docs["type_doc"] == key)]
                        base = date.today()
                        if not cur.empty and pd.notna(cur.iloc[0]["date_expiration"]):
                            base = _to_date(cur.iloc[0]["date_expiration"]) or date.today()
                        nd = rules.prochaine_echeance(key, base)
                        DB.upsert_document(vid, key, True, nd)
                        st.success(f"{doc} renouvelée jusqu'au {nd.strftime('%d/%m/%Y')}.")
                        st.rerun()
                else:
                    st.caption("Aucune pièce à échéance datée pour cette catégorie.")

    # -------- Onglet consultation coloré + filtres AgGrid --------
    with tab_vue:
        wide = ui.pivot_etats(enr, veh, categorie)
        cols_etat = [rules.DOC_TYPES[t]["label"] for t in rules.DOC_TYPES
                     if categorie in rules.DOC_TYPES[t]["cats"]]
        wide = wide.rename(columns={"code_interne": "Code", "immatriculation": "Immat.",
                                    "type_vehicule": "Type", "marque": "Marque"})
        st.caption(f"{len(wide)} véhicule(s) — filtres par colonne, tri et "
                   "redimensionnement directement dans le tableau.")
        ui.tableau_excel(wide, colonnes_etat=cols_etat, key=f"grid_{categorie}")

    # -------- Onglet pièces jointes (scans) --------
    with tab_pj:
        _onglet_pieces_jointes(veh, categorie, editable)


def _onglet_pieces_jointes(veh, categorie, editable):
    st.caption("Rattachez les scans (carte grise, assurance, visite…) à chaque "
               "véhicule : PDF ou image. Ils restent accessibles pour un contrôle "
               "ou un audit.")
    sub = veh[veh["categorie"] == categorie].copy()
    if sub.empty:
        st.info("Aucun véhicule.")
        return
    sub["lbl"] = sub["immatriculation"].fillna("?") + " — " + sub["code_interne"].fillna("?")
    sel = st.selectbox("Véhicule", sub["lbl"].tolist(), key=f"pj_sel_{categorie}")
    vid = int(sub[sub["lbl"] == sel].iloc[0]["id"])
    types = [(t, rules.DOC_TYPES[t]["label"]) for t in rules.DOC_TYPES
             if categorie in rules.DOC_TYPES[t]["cats"]]

    if editable:
        cc = st.columns([1.6, 2])
        td = cc[0].selectbox("Type de pièce", [l for _, l in types], key=f"pj_td_{categorie}")
        up = cc[1].file_uploader("Fichier (PDF ou image)",
                                 type=["pdf", "png", "jpg", "jpeg"], key=f"pj_up_{categorie}")
        if up is not None and st.button("📎 Joindre le fichier", key=f"pj_add_{categorie}"):
            key = [t for t, l in types if l == td][0]
            DB.insert_piece_jointe(vid, key, up.name, up.type or "application/octet-stream",
                                   up.getvalue())
            st.success(f"« {up.name} » rattaché.")
            st.rerun()

    meta = DB.load_pieces_jointes_meta(vid)
    st.markdown("##### Pièces rattachées à ce véhicule")
    if meta.empty:
        st.caption("Aucune pièce jointe pour l'instant.")
    else:
        label_map = dict(types)
        for _, r in meta.iterrows():
            cols = st.columns([3, 2, 1.4, 1])
            cols[0].write(f"**{r['nom_fichier']}**")
            cols[1].write(label_map.get(r["type_doc"], r["type_doc"]))
            taille = f"{(r['taille'] or 0)/1024:.0f} Ko"
            cols[2].caption(taille)
            pj = DB.get_piece_jointe(int(r["id"]))
            if pj and pj["contenu"] is not None:
                cols[3].download_button("⬇️", pj["contenu"], file_name=pj["nom"],
                                        mime=pj["mime"], key=f"dl_{r['id']}")
            if editable:
                if cols[3].button("🗑️", key=f"delpj_{r['id']}"):
                    DB.delete_piece_jointe(int(r["id"]))
                    st.rerun()


# ============================================================================
# PAGE — PORTE-CHARS (couples)
# ============================================================================
def page_porte_chars():
    st.title("Autorisations porte-chars")
    st.caption("Autorisations de circulation hors-gabarit par couple de véhicules. "
               "Renouvellement tous les 6 mois — alerte 1 mois avant échéance. "
               "Modifiez les cellules, ajoutez des lignes avec « + », puis enregistrez.")
    _, _, couples, _ = _data()
    ce = _couples_enrichis(couples)

    # État courant (consultation rapide, coloré)
    if not ce.empty:
        etat_map = dict(zip(ce["id"], ce["etat_label"]))

    base = couples.copy() if not couples.empty else pd.DataFrame(
        columns=["id", "vehicule_a", "vehicule_b", "date_expiration"])
    df = pd.DataFrame({
        "id": base["id"] if "id" in base else [],
        "Véhicule A": base["vehicule_a"] if "vehicule_a" in base else [],
        "Véhicule B": base["vehicule_b"] if "vehicule_b" in base else [],
        "Échéance": [_to_date(x) for x in base["date_expiration"]] if "date_expiration" in base else [],
    })
    df["État"] = df["id"].map(etat_map) if not ce.empty else "—"

    editable = auth.peut_editer()
    shown_ids = set(int(x) for x in df["id"].dropna().tolist())
    edited = st.data_editor(
        df, hide_index=True, num_rows="dynamic" if editable else "fixed",
        disabled=not editable, use_container_width=True, height=340,
        key="editor_pc",
        column_config={
            "id": None,
            "Véhicule A": st.column_config.TextColumn("Véhicule A"),
            "Véhicule B": st.column_config.TextColumn("Véhicule B"),
            "Échéance": st.column_config.DateColumn("Échéance", format="DD/MM/YYYY"),
            "État": st.column_config.TextColumn("État", disabled=True),
        })

    # Rapprochement : couples référençant une immatriculation inconnue
    veh_all = DB.load_vehicles()
    anomalies = _rapprochement_couples(veh_all, couples)
    if anomalies:
        st.warning("Immatriculation(s) inconnue(s) de la base camions : "
                   + ", ".join(anomalies) + ".")

    c = st.columns([1.3, 1.4, 3])
    if editable and c[0].button("💾 Enregistrer", type="primary", key="save_pc"):
        seen = set()
        crees = maj = suppr = 0
        for _, row in edited.iterrows():
            a = str(row.get("Véhicule A") or "").strip()
            b = str(row.get("Véhicule B") or "").strip()
            de = _to_date(row.get("Échéance"))
            cid = row.get("id")
            if pd.isna(cid):
                if a and b:
                    DB.upsert_couple(a, b, de)
                    crees += 1
            else:
                cid = int(cid)
                seen.add(cid)
                DB.upsert_couple(a, b, de, couple_id=cid)
                maj += 1
        for cid in shown_ids - seen:
            DB.delete_couple(int(cid))
            suppr += 1
        st.success(f"Enregistré : {maj} mise(s) à jour, {crees} création(s), "
                   f"{suppr} suppression(s).")
        st.rerun()

    if editable:
        with c[1].popover("🔄 Renouveler (+6 mois)"):
            if not couples.empty:
                ce2 = couples.copy()
                ce2["lbl"] = ce2["vehicule_a"].fillna("?") + " & " + ce2["vehicule_b"].fillna("?")
                sel = st.selectbox("Couple", ce2["lbl"].tolist(), key="pc_renew_sel")
                row = ce2[ce2["lbl"] == sel].iloc[0]
                base_d = _to_date(row["date_expiration"]) or date.today()
                if st.button("Confirmer le renouvellement", key="pc_renew_btn"):
                    nd = rules.prochaine_echeance("porte_chars", base_d)
                    DB.upsert_couple(row["vehicule_a"], row["vehicule_b"], nd,
                                     couple_id=int(row["id"]))
                    st.success(f"Renouvelé jusqu'au {nd.strftime('%d/%m/%Y')}.")
                    st.rerun()


# ============================================================================
# PAGE — ALERTES
# ============================================================================
def page_alertes():
    st.title("Alertes & échéances")
    veh, docs, couples, enr = _data()
    ce = _couples_enrichis(couples)

    seuil = st.slider("Horizon d'alerte (jours)", 7, 180, 60, step=7)
    today = date.today()

    docs_a = enr[(enr["etat"].isin([rules.A_RENOUVELER, rules.EXPIRE]))
                 | ((enr["jours_restants"].notna()) & (enr["jours_restants"] <= seuil))]
    docs_a = docs_a.sort_values("jours_restants", na_position="last")

    c = st.columns(3)
    _kpi(c[0], int((enr["etat"] == rules.EXPIRE).sum()), "Pièces expirées", ui.PALETTE["rouge"])
    _kpi(c[1], int((docs_a["jours_restants"].fillna(999) <= seuil).sum()),
         f"Sous {seuil} jours", ui.PALETTE["ambre"])
    pc_a = int((ce["etat"].isin([rules.A_RENOUVELER, rules.EXPIRE])).sum()) if not ce.empty else 0
    _kpi(c[2], pc_a, "Couples porte-chars", ui.PALETTE["rouge"])

    st.subheader("Pièces à traiter")
    if docs_a.empty:
        st.success("Aucune pièce en alerte sur cet horizon.")
    else:
        v = docs_a[["immatriculation", "type_vehicule", "doc_label",
                    "etat_label", "echeance", "jours_restants"]].copy()
        v = v.rename(columns={"immatriculation": "Immat.", "type_vehicule": "Type",
                              "doc_label": "Pièce", "etat_label": "État",
                              "echeance": "Échéance", "jours_restants": "Jours"})
        ui.tableau_excel(v, colonnes_etat=["État"], hauteur=420, key="grid_alertes")
        st.download_button("Exporter les alertes (CSV)",
                           v.to_csv(index=False).encode("utf-8"),
                           file_name="alertes_flotte.csv", mime="text/csv")

    st.subheader("Porte-chars en alerte")
    if ce.empty or pc_a == 0:
        st.caption("Aucun couple en alerte.")
    else:
        pc = ce[ce["etat"].isin([rules.A_RENOUVELER, rules.EXPIRE])].copy()
        pc["Couple"] = pc["vehicule_a"] + " & " + pc["vehicule_b"]
        st.dataframe(pc[["Couple", "date_expiration", "etat_label", "jours_restants"]]
                     .rename(columns={"date_expiration": "Échéance",
                                      "etat_label": "État", "jours_restants": "Jours"}),
                     use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Alertes par e-mail")
    st.caption("Envoie la liste des pièces à traiter aux destinataires configurés. "
               "L'envoi peut aussi être automatisé (voir README : cron / GitHub Actions).")
    if st.button("✉️ Envoyer l'alerte maintenant"):
        try:
            res = alertes_mail.envoyer(seuil)
            if res.get("ok"):
                st.success(f"E-mail envoyé à {', '.join(res['destinataires'])} "
                           f"({res['nb']} pièce(s)).")
            else:
                st.warning(f"Non envoyé : {res.get('raison')}. "
                           "Configurez la section [email] dans les secrets.")
        except Exception as e:
            st.error(f"Échec de l'envoi : {e}")


# ============================================================================
# PAGE — COÛTS (suivi budgétaire)
# ============================================================================
def page_couts():
    st.title("Coûts & budget documentaire")
    st.caption("Enregistrez le montant de chaque renouvellement pour piloter la "
               "dépense annuelle par pièce et par mois.")
    veh = DB.load_vehicles()
    pai = DB.load_paiements()
    editable = auth.peut_editer()

    if editable:
        with st.expander("➕ Enregistrer un paiement", expanded=pai.empty):
            veh2 = veh.copy()
            veh2["lbl"] = veh2["immatriculation"].fillna("?") + " — " + veh2["code_interne"].fillna("?")
            cc = st.columns([2, 1.4, 1.2, 1.4])
            sel = cc[0].selectbox("Véhicule", ["(aucun)"] + veh2["lbl"].tolist())
            typ = cc[1].selectbox("Pièce", [rules.DOC_TYPES[t]["label"] for t in rules.DOC_TYPES])
            montant = cc[2].number_input("Montant (FCFA)", min_value=0, step=5000, value=0)
            dpai = cc[3].date_input("Date de paiement", value=date.today(), format="DD/MM/YYYY")
            if st.button("Enregistrer le paiement", type="primary"):
                vid = None
                if sel != "(aucun)":
                    vid = int(veh2[veh2["lbl"] == sel].iloc[0]["id"])
                key = [t for t in rules.DOC_TYPES if rules.DOC_TYPES[t]["label"] == typ][0]
                DB.insert_paiement(vid, key, float(montant), dpai)
                st.success("Paiement enregistré.")
                st.rerun()

    if pai.empty:
        st.info("Aucun paiement enregistré pour l'instant.")
        return

    # Enrichissement libellés
    pai = pai.copy()
    pai["date_paiement"] = pd.to_datetime(pai["date_paiement"], errors="coerce")
    pai["mois"] = pai["date_paiement"].dt.to_period("M").astype(str)
    pai["piece"] = pai["type_doc"].map(lambda t: rules.DOC_TYPES.get(t, {}).get("label", t))
    imm = dict(zip(veh["id"], veh["immatriculation"]))
    pai["vehicule"] = pai["vehicle_id"].map(imm).fillna("—")

    total = pai["montant"].sum()
    annee = date.today().year
    total_an = pai[pai["date_paiement"].dt.year == annee]["montant"].sum()
    k = st.columns(3)
    _kpi(k[0], f"{total:,.0f}".replace(",", " "), "Total enregistré (FCFA)", "#6f7d3f")
    _kpi(k[1], f"{total_an:,.0f}".replace(",", " "), f"Dépense {annee} (FCFA)", "#b0892c")
    _kpi(k[2], len(pai), "Paiements")

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Dépense par mois")
        pm = pai.groupby("mois")["montant"].sum().reset_index()
        fig = px.bar(pm, x="mois", y="montant", color_discrete_sequence=[OLIVE])
        fig.update_traces(hovertemplate="%{x} · <b>%{y:,.0f} FCFA</b><extra></extra>")
        fig.update_layout(xaxis_title="", yaxis_title="FCFA", bargap=0.35)
        show_chart(style_fig(fig, height=340))
    with g2:
        st.subheader("Dépense par type de pièce")
        pt = pai.groupby("piece")["montant"].sum().reset_index().sort_values("montant")
        fig = px.bar(pt, x="montant", y="piece", orientation="h",
                     color_discrete_sequence=[OLIVE_CLAIR])
        fig.update_traces(hovertemplate="%{y} · <b>%{x:,.0f} FCFA</b><extra></extra>")
        fig.update_layout(xaxis_title="FCFA", yaxis_title="")
        fig.update_yaxes(automargin=True)
        show_chart(style_fig(fig, height=340))

    st.subheader("Historique des paiements")
    vue = pai[["date_paiement", "vehicule", "piece", "montant", "notes"]].copy()
    vue["date_paiement"] = vue["date_paiement"].dt.strftime("%d/%m/%Y")
    vue = vue.rename(columns={"date_paiement": "Date", "vehicule": "Véhicule",
                              "piece": "Pièce", "montant": "Montant (FCFA)", "notes": "Notes"})
    ui.tableau_excel(vue, hauteur=320, key="grid_couts")
    st.download_button("⬇️ Exporter les coûts (CSV)",
                       vue.to_csv(index=False).encode("utf-8"),
                       file_name="couts_flotte.csv", mime="text/csv")


# ============================================================================
# PAGE — JOURNAL D'AUDIT (admin)
# ============================================================================
def page_journal():
    st.title("Journal d'audit")
    st.caption("Traçabilité des opérations : qui a modifié quoi et quand.")
    df = DB.load_audit(1000)
    if df.empty:
        st.info("Aucune opération enregistrée pour l'instant.")
        return
    df = df.copy()
    if "horodatage" in df:
        df["horodatage"] = pd.to_datetime(df["horodatage"], errors="coerce").dt.strftime(
            "%d/%m/%Y %H:%M")
    vue = df[["horodatage", "utilisateur", "action", "cible", "details"]].rename(
        columns={"horodatage": "Date", "utilisateur": "Utilisateur", "action": "Action",
                 "cible": "Cible", "details": "Détails"})
    c = st.columns(3)
    _kpi(c[0], len(df), "Opérations tracées")
    _kpi(c[1], df["utilisateur"].nunique(), "Utilisateurs")
    _kpi(c[2], df["action"].nunique(), "Types d'action")
    ui.tableau_excel(vue, hauteur=520, key="grid_audit")
    st.download_button("⬇️ Exporter le journal (CSV)",
                       vue.to_csv(index=False).encode("utf-8"),
                       file_name="journal_audit.csv", mime="text/csv")


# ============================================================================
# PAGE — IMPORT / ADMIN
# ============================================================================
def page_admin():
    st.title("Import / Administration")
    veh, docs, couples, enr = _data()

    st.subheader("État de la base")
    c = st.columns(4)
    _kpi(c[0], len(veh), "Véhicules")
    _kpi(c[1], int((veh["categorie"] == "camion").sum()), "Camions")
    _kpi(c[2], int((veh["categorie"] == "engin").sum()), "Engins")
    _kpi(c[3], len(couples), "Couples porte-chars")
    st.caption(("Connexion : **Neon PostgreSQL**" if DB.is_postgres()
                else "Connexion : **SQLite local** (repli — configurez le secret `neon` "
                "pour basculer sur le cloud)."))

    st.divider()
    st.subheader("Import d'un fichier Excel / CSV")
    st.markdown("Importez une feuille de mise à jour. Le fichier doit contenir une "
                "colonne d'identifiant (`immatriculation` ou `code_interne`) ; les "
                "colonnes reconnues mettent à jour les pièces correspondantes.")

    cat = st.radio("Catégorie cible", ["camion", "engin"], horizontal=True)
    up = st.file_uploader("Fichier (.xlsx ou .csv)", type=["xlsx", "csv"])

    # Mapping souple : libellés sources -> type_doc
    alias = {
        "carte grise": "carte_grise", "carte de transport": "carte_transport",
        "carte de stationement": "carte_stationnement",
        "carte de stationnement": "carte_stationnement",
        "visite technique": "visite_technique", "patente": "patente",
        "pantente": "patente", "assurance": "assurance", "douanes": "douanes",
        "papiers": "douanes",
    }
    exp_alias = {
        "expiration assurance": ("assurance", "date"),
        "expiration carte de transport": ("carte_transport", "date"),
        "expiration visite. et vignete": ("visite_technique", "date"),
    }

    if up is not None:
        try:
            if up.name.lower().endswith(".csv"):
                dfimp = pd.read_csv(up, dtype=str)
            else:
                dfimp = pd.read_excel(up, dtype=str)
        except Exception as e:
            st.error(f"Lecture impossible : {e}")
            dfimp = None

        if dfimp is not None:
            dfimp.columns = [str(c).strip().lower() for c in dfimp.columns]
            st.markdown("**Aperçu :**")
            st.dataframe(dfimp.head(8), use_container_width=True)

            idcol = None
            for cand in ["immatriculation", "immatriculation (id)", "code_interne",
                         "id interne", "matricule"]:
                if cand in dfimp.columns:
                    idcol = cand
                    break
            if idcol is None:
                st.error("Aucune colonne d'identifiant trouvée "
                         "(immatriculation / code_interne / matricule).")
            elif st.button("Lancer l'import", type="primary"):
                veh_idx = veh.set_index(
                    veh["immatriculation"].fillna("").str.upper())
                code_idx = veh.set_index(veh["code_interne"].fillna("").str.upper())
                maj, crees, lignes = 0, 0, 0

                for _, row in dfimp.iterrows():
                    ident = str(row.get(idcol, "")).strip()
                    if not ident:
                        continue
                    lignes += 1
                    key = ident.upper()
                    vid = None
                    if key in veh_idx.index:
                        vid = int(veh_idx.loc[key, "id"]) if not isinstance(
                            veh_idx.loc[key, "id"], pd.Series) else int(
                            veh_idx.loc[key, "id"].iloc[0])
                    elif key in code_idx.index:
                        v = code_idx.loc[key, "id"]
                        vid = int(v if not isinstance(v, pd.Series) else v.iloc[0])
                    if vid is None:
                        vid = DB.insert_vehicle({
                            "categorie": cat, "immatriculation": ident,
                            "code_interne": str(row.get("code_interne", "") or ident)})
                        crees += 1

                    # Dates d'expiration
                    exp_map = {}
                    for col, (td, _) in exp_alias.items():
                        if col in dfimp.columns:
                            exp_map[td] = SEED.to_date(row.get(col))
                    # Possession
                    for col, td in alias.items():
                        if col in dfimp.columns and rules.DOC_TYPES.get(td) \
                                and cat in rules.DOC_TYPES[td]["cats"]:
                            DB.upsert_document(vid, td, SEED.to_bool(row.get(col)),
                                               exp_map.get(td))
                            maj += 1
                    # Pièces datées sans colonne possession explicite
                    for td, de in exp_map.items():
                        if td not in [alias[a] for a in alias if a in dfimp.columns]:
                            DB.upsert_document(vid, td, True, de)

                st.success(f"Import terminé : {lignes} ligne(s) traitée(s), "
                           f"{crees} véhicule(s) créé(s), {maj} pièce(s) mise(s) à jour.")
                st.rerun()

    st.divider()
    st.subheader("Réinitialisation")
    if not auth.est_admin():
        st.caption("Réservé à l'administrateur.")
    else:
        st.caption("Recharge les bases initiales (engins, camions, couples). "
                   "À utiliser avec précaution.")
        if st.checkbox("Je confirme vouloir réinitialiser depuis les fichiers fournis"):
            if st.button("♻️ Réinitialiser la base", type="secondary"):
                eng = DB.get_engine()
                from sqlalchemy import text as _t
                with eng.begin() as conn:
                    conn.execute(_t("DELETE FROM documents"))
                    conn.execute(_t("DELETE FROM porte_chars_couples"))
                    conn.execute(_t("DELETE FROM vehicles"))
                DB._flush()
                SEED.run_seed(force=True)
                st.success("Base réinitialisée.")
                st.rerun()


# ============================================================================
# NAVIGATION
# ============================================================================
def main():
    boot = _bootstrap()

    # Garde d'authentification (mode ouvert si aucun compte configuré)
    if not auth.login_gate():
        return

    u = auth.utilisateur_courant() or {"nom": "Utilisateur", "role": "admin"}
    with st.sidebar:
        st.markdown(f"## 🛡️ {APP_NOM}")
        st.caption("Pièces administratives de flotte")
        st.markdown(
            f"<div style='background:#6f7d3f14;border:1px solid #6f7d3f33;"
            f"border-radius:10px;padding:8px 12px;margin:6px 0'>"
            f"👤 <b>{u['nom']}</b><br><span style='font-size:0.8rem;color:#5b6354'>"
            f"{auth.ROLE_LABELS.get(u['role'], u['role'])}</span></div>",
            unsafe_allow_html=True)
        if auth.utilisateur_courant() and auth._comptes():
            if st.button("Se déconnecter", key="logout"):
                auth.logout()
        st.markdown("---")

    if boot.get("data_manquante") and boot.get("vehicles", 0) == 0:
        st.warning(
            "Le dossier **data/** (engins.psv, camions.psv, couples.psv) est "
            "introuvable à côté de `app.py`, donc aucune base n'a pu être chargée. "
            "Placez le dossier `data/` dans le même répertoire que `app.py`, puis "
            "rechargez la page — ou chargez vos feuilles via **Import / Admin**.")

    pages = {
        "Pilotage": [
            st.Page(page_dashboard, title="Tableau de bord", icon="📊", default=True),
            st.Page(page_alertes, title="Alertes & échéances", icon="🔔"),
            st.Page(page_couts, title="Coûts & budget", icon="💰"),
        ],
        "Flotte": [
            st.Page(lambda: page_vehicules("camion", "Camions"),
                    title="Camions", icon="🚚", url_path="camions"),
            st.Page(lambda: page_vehicules("engin", "Engins"),
                    title="Engins", icon="🏗️", url_path="engins"),
            st.Page(page_porte_chars, title="Porte-chars", icon="🔗"),
        ],
        "Données": [
            st.Page(page_admin, title="Import / Admin", icon="⚙️"),
        ],
    }
    # Journal d'audit réservé à l'administrateur
    if auth.est_admin():
        pages["Données"].append(
            st.Page(page_journal, title="Journal d'audit", icon="📜"))

    nav = st.navigation(pages)
    nav.run()


if __name__ == "__main__":
    main()
