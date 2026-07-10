"""
ui.py — Helpers partagés : calcul des états sur DataFrame, tableau type Excel
(streamlit-aggrid avec repli st.dataframe), badges et palette (thème clair).
"""
from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st

import rules

# Import AgGrid robuste : on n'exige que le cœur (AgGrid/GridOptionsBuilder/JsCode).
# GridUpdateMode a changé d'emplacement selon les versions -> import optionnel.
HAS_AGGRID = False
GridUpdateMode = None
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
    HAS_AGGRID = True
    try:
        from st_aggrid import GridUpdateMode
    except Exception:
        try:
            from st_aggrid.shared import GridUpdateMode
        except Exception:
            GridUpdateMode = None
except Exception:
    HAS_AGGRID = False


# --- Palette premium clair ---------------------------------------------------
PALETTE = {
    "vert": "#15803d", "ambre": "#b45309", "rouge": "#b91c1c",
    "gris": "#64748b", "ardoise": "#7c6510",
    "fond": "#f6f7f9", "carte": "#ffffff", "bordure": "#e6e8ec",
    "accent": "#b0892c", "texte": "#1f2733", "texte2": "#5b6470",
}
# Couleurs d'état adaptées au fond clair (réutilisées AgGrid + Plotly + badges)
ETAT_COULEUR = {
    rules.A_JOUR: "#15803d", rules.A_RENOUVELER: "#b45309", rules.EXPIRE: "#b91c1c",
    rules.DETENU: "#15803d", rules.NON_DETENU: "#64748b", rules.A_RENSEIGNER: "#a16207",
}
ETAT_ORDRE = [rules.EXPIRE, rules.A_RENOUVELER, rules.A_RENSEIGNER,
              rules.NON_DETENU, rules.A_JOUR, rules.DETENU]


def badge(code_etat: str) -> str:
    label = rules.ETAT_LABEL.get(code_etat, code_etat)
    coul = ETAT_COULEUR.get(code_etat, "#64748b")
    return (f"<span style='background:{coul}14;color:{coul};"
            f"padding:3px 12px;border-radius:999px;font-size:0.8rem;"
            f"font-weight:600;white-space:nowrap;border:1px solid {coul}33'>{label}</span>")


def enrich_documents(df_vehicles: pd.DataFrame, df_docs: pd.DataFrame,
                     today: date | None = None) -> pd.DataFrame:
    """Jointure véhicules×documents enrichie : état, échéance, jours restants."""
    today = today or date.today()
    if df_docs.empty:
        return pd.DataFrame()
    df = df_docs.merge(
        df_vehicles[["id", "categorie", "code_interne", "immatriculation",
                     "type_vehicule", "marque"]],
        left_on="vehicle_id", right_on="id", suffixes=("", "_veh"),
    )
    etats, echs, jours = [], [], []
    for _, r in df.iterrows():
        de = r["date_expiration"]
        de = pd.to_datetime(de).date() if pd.notna(de) and de is not None else None
        possede = r["possede"]
        possede = None if pd.isna(possede) else bool(possede)
        code, ech, j = rules.compute_etat(r["type_doc"], possede, de, today)
        etats.append(code); echs.append(ech); jours.append(j)
    df["etat"] = etats
    df["echeance"] = echs
    df["jours_restants"] = jours
    df["etat_label"] = df["etat"].map(rules.ETAT_LABEL)
    df["doc_label"] = df["type_doc"].map(
        lambda t: rules.DOC_TYPES.get(t, {}).get("label", t))
    return df


def pivot_etats(df_enr: pd.DataFrame, df_vehicles: pd.DataFrame,
                categorie: str) -> pd.DataFrame:
    """Vue large : 1 ligne/véhicule, 1 colonne/type de document, valeur = état."""
    base_cols = ["code_interne", "immatriculation", "type_vehicule", "marque"]
    veh = df_vehicles[df_vehicles["categorie"] == categorie].copy()
    if veh.empty:
        return pd.DataFrame()
    sub = df_enr[df_enr["categorie"] == categorie]
    types = [t for t, c in rules.DOC_TYPES.items() if categorie in c["cats"]]
    wide = veh[["id"] + base_cols].copy()
    for t in types:
        lab = rules.DOC_TYPES[t]["label"]
        m = (sub[sub["type_doc"] == t]
             .set_index("vehicle_id")["etat_label"].to_dict())
        wide[lab] = wide["id"].map(m).fillna("—")
    return wide.drop(columns=["id"])


def _jscode_etat():
    """Style conditionnel des cellules d'état (puces colorées, fond clair)."""
    couleurs = {
        "À jour": "#15803d", "Détenu": "#15803d",
        "À renouveler": "#b45309", "À renseigner": "#a16207",
        "Expiré": "#b91c1c", "Non détenu": "#64748b",
    }
    mapping = ",".join(f"'{k}':'{v}'" for k, v in couleurs.items())
    return JsCode(f"""
    function(params) {{
        const m = {{{mapping}}};
        const c = m[params.value];
        if (c) {{
            return {{'color': c, 'fontWeight': '600',
                     'backgroundColor': c + '12'}};
        }}
        return {{'color': '#94a3b8'}};
    }}
    """)


def tableau_excel(df: pd.DataFrame, colonnes_etat=None, hauteur=520, key="grid"):
    """Tableau type Excel (filtres flottants, tri, redimension, pagination).
    Repli automatique sur st.dataframe si AgGrid indisponible."""
    colonnes_etat = colonnes_etat or []
    if not HAS_AGGRID:
        st.info("Mode tableau simplifié. Pour le confort Excel complet "
                "(filtres par colonne, tri, coloration), installez le composant : "
                "`pip install streamlit-aggrid` puis relancez l'application.")
        st.dataframe(df, use_container_width=True, height=hauteur, hide_index=True)
        return None

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        filter=True, sortable=True, resizable=True, editable=False,
        floatingFilter=True, minWidth=120,
    )
    gb.configure_grid_options(domLayout="normal", enableRangeSelection=True,
                              pagination=True, paginationPageSize=25,
                              rowHeight=34, headerHeight=38)
    for col in colonnes_etat:
        if col in df.columns:
            gb.configure_column(col, cellStyle=_jscode_etat())

    kwargs = dict(gridOptions=gb.build(), height=hauteur,
                  allow_unsafe_jscode=True, fit_columns_on_grid_load=False,
                  theme="balham", key=key)
    if GridUpdateMode is not None:
        kwargs["update_mode"] = GridUpdateMode.NO_UPDATE
    return AgGrid(df, **kwargs)
