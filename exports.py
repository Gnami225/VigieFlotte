"""
exports.py — Génération des livrables : Excel (multi-feuilles) et PDF (synthèse).
"""
from __future__ import annotations
from io import BytesIO
from datetime import date
import pandas as pd

import rules


def _synthese(enr: pd.DataFrame) -> dict:
    total = len(enr)
    conf = int(enr["etat"].isin(rules.CONFORMES).sum()) if total else 0
    return {
        "total_pieces": total,
        "conformes": conf,
        "taux": round(100 * conf / total, 1) if total else 0.0,
        "expirees": int((enr["etat"] == rules.EXPIRE).sum()),
        "a_renouveler": int((enr["etat"] == rules.A_RENOUVELER).sum()),
        "a_renseigner": int((enr["etat"] == rules.A_RENSEIGNER).sum()),
    }


def build_excel(veh, enr, couples_enr, paiements) -> bytes:
    """Classeur Excel : synthèse, échéances, véhicules, coûts."""
    buf = BytesIO()
    syn = _synthese(enr)
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        pd.DataFrame([
            ["Généré le", date.today().strftime("%d/%m/%Y")],
            ["Véhicules", len(veh)],
            ["Pièces suivies", syn["total_pieces"]],
            ["Taux de conformité (%)", syn["taux"]],
            ["Pièces expirées", syn["expirees"]],
            ["À renouveler", syn["a_renouveler"]],
            ["À renseigner", syn["a_renseigner"]],
        ], columns=["Indicateur", "Valeur"]).to_excel(xl, sheet_name="Synthèse", index=False)

        ech = enr[enr["echeance"].notna()].copy()
        if not ech.empty:
            ech = ech[["immatriculation", "type_vehicule", "doc_label", "etat_label",
                       "echeance", "jours_restants"]].sort_values("jours_restants")
            ech.columns = ["Immatriculation", "Type", "Pièce", "État", "Échéance", "Jours restants"]
            ech.to_excel(xl, sheet_name="Échéances", index=False)

        if not veh.empty:
            veh[["categorie", "code_interne", "immatriculation", "type_vehicule",
                 "marque", "id_chassis"]].to_excel(xl, sheet_name="Véhicules", index=False)

        if couples_enr is not None and not couples_enr.empty:
            cc = couples_enr.copy()
            cc["Couple"] = cc["vehicule_a"] + " & " + cc["vehicule_b"]
            cc[["Couple", "date_expiration", "etat_label", "jours_restants"]].rename(
                columns={"date_expiration": "Échéance", "etat_label": "État",
                         "jours_restants": "Jours"}).to_excel(
                xl, sheet_name="Porte-chars", index=False)

        if paiements is not None and not paiements.empty:
            paiements.to_excel(xl, sheet_name="Coûts", index=False)
    return buf.getvalue()


def build_pdf(veh, enr, couples_enr) -> bytes | None:
    """Synthèse PDF d'une page. Retourne None si reportlab indisponible."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                        TableStyle)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except Exception:
        return None

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    olive = colors.HexColor("#6f7d3f")
    h = ParagraphStyle("h", parent=styles["Title"], textColor=olive, fontSize=20)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor("#5b6354"))
    el = [Paragraph("VigieFlotte — Synthèse de conformité", h),
          Paragraph(f"Édité le {date.today().strftime('%d/%m/%Y')}", sub),
          Spacer(1, 10 * mm)]

    syn = _synthese(enr)
    kpi = [["Véhicules", str(len(veh))],
           ["Pièces suivies", str(syn["total_pieces"])],
           ["Taux de conformité", f"{syn['taux']} %"],
           ["Pièces expirées", str(syn["expirees"])],
           ["À renouveler", str(syn["a_renouveler"])],
           ["À renseigner", str(syn["a_renseigner"])]]
    t = Table(kpi, colWidths=[70 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f4ea")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2a2f25")),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8dcc8")),
        ("PADDING", (0, 0), (-1, -1), 6)]))
    el += [t, Spacer(1, 8 * mm)]

    ech = enr[enr["echeance"].notna()].copy()
    ech = ech[(ech["jours_restants"].notna()) & (ech["jours_restants"] <= 90)] \
        .sort_values("jours_restants").head(25)
    el.append(Paragraph("Échéances sous 90 jours", styles["Heading2"]))
    if ech.empty:
        el.append(Paragraph("Aucune échéance imminente.", sub))
    else:
        rows = [["Immat.", "Pièce", "Échéance", "Jours"]]
        for _, r in ech.iterrows():
            rows.append([str(r["immatriculation"]), str(r["doc_label"]),
                         r["echeance"].strftime("%d/%m/%Y") if r["echeance"] else "",
                         str(int(r["jours_restants"]))])
        t2 = Table(rows, colWidths=[35 * mm, 65 * mm, 35 * mm, 20 * mm], repeatRows=1)
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), olive),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8dcc8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8f2")]),
            ("PADDING", (0, 0), (-1, -1), 4)]))
        el.append(t2)

    doc.build(el)
    return buf.getvalue()
