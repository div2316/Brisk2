"""PDF report for one assessment (ReportLab)."""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BAND_COLOR = {"Low": colors.HexColor("#16a34a"), "Moderate": colors.HexColor("#d97706"), "High": colors.HexColor("#dc2626")}
VIOLET = colors.HexColor("#6d28d9")


def pretty(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


def _gauge(risk: float, band: str) -> Drawing:
    w, h = 170 * mm, 14 * mm
    d = Drawing(w, h)
    d.add(Rect(0, 4 * mm, w, 5 * mm, fillColor=colors.HexColor("#e5e7eb"), strokeColor=None))
    d.add(Rect(0, 4 * mm, w * min(risk, 100) / 100, 5 * mm, fillColor=BAND_COLOR.get(band, VIOLET), strokeColor=None))
    for x in (20, 50):
        d.add(Line(w * x / 100, 3 * mm, w * x / 100, 10 * mm, strokeColor=colors.HexColor("#6b7280")))
    d.add(String(0, 0, "0%", fontSize=7))
    d.add(String(w * .2 - 6, 0, "20%", fontSize=7)); d.add(String(w * .5 - 6, 0, "50%", fontSize=7))
    d.add(String(w - 16, 0, "100%", fontSize=7))
    return d


def _factor_chart(factors: list[dict]) -> Drawing:
    rows = factors[:8]
    w, rh = 170 * mm, 7 * mm
    h = max(len(rows), 1) * rh + 4 * mm
    d = Drawing(w, h)
    mid, half = w * 0.62, w * 0.3
    top = max([abs(f["contribution_pct_points"]) for f in rows] + [0.1])
    d.add(Line(mid, 0, mid, h, strokeColor=colors.HexColor("#9ca3af")))
    for i, f in enumerate(rows):
        y = h - (i + 1) * rh
        v = f["contribution_pct_points"]
        length = half * abs(v) / top
        up = v >= 0
        d.add(Rect(mid if up else mid - length, y + 1.5 * mm, max(length, 0.6), 4 * mm, strokeColor=None,
                   fillColor=colors.HexColor("#dc2626") if up else colors.HexColor("#16a34a")))
        d.add(String(0, y + 2.2 * mm, f.get("label") or pretty(f["factor"]), fontSize=8))
        d.add(String(mid + (length + 2 if up else -length - 2) if up else mid - length - 2, y + 2.2 * mm,
                     f"{v:+.1f} pts", fontSize=7, textAnchor="start" if up else "end"))
    return d


def build_pdf(user: dict, assessment: dict) -> bytes:
    p = assessment["payload"]
    pred, patient = p["prediction"], p["patient"]
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=VIOLET, fontSize=20, alignment=0)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#111827"), spaceBefore=10)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#4b5563"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title="BRISK2 risk report", author="BRISK2")
    story = [Paragraph("BRISK2 | Cardiovascular risk report", h1),
             Paragraph(f"Prepared for {user['name']} ({user['email']}) · assessment #{assessment['id']} · "
                       f"{assessment['created_at'].replace('T', ' ')[:16]} UTC", small), Spacer(1, 6 * mm)]

    band = pred["stratum"]
    big = ParagraphStyle("big", parent=body, fontSize=30, leading=34, textColor=BAND_COLOR.get(band, VIOLET))
    t = Table([[Paragraph(f"<b>{pred['risk_pct']:.1f}%</b>", big),
                Paragraph(f"<b>{band} risk band</b><br/>Estimated probability from the model for the values you entered. "
                          f"The average in the training data is about {pred.get('baseline_risk_pct', 0):.1f}%.", body)]],
              colWidths=[55 * mm, 115 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#d1d5db")),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")), ("PADDING", (0, 0), (-1, -1), 8)]))
    story += [t, Spacer(1, 3 * mm), _gauge(pred["risk_pct"], band)]

    story += [Paragraph("What contributed to this estimate", h2),
              Paragraph("Each bar shows how many percentage points the estimate changes compared with the average person in the training data because of that input. "
                        "Red bars push the estimate up, green bars pull it down. This describes the model, "
                        "not the cause of disease.", body), Spacer(1, 2 * mm), _factor_chart(pred["all_factors"])]

    rows = [["Factor", "Your value", "Effect on estimate"]]
    for f in pred["all_factors"][:8]:
        rows.append([f.get("label") or pretty(f["factor"]), str(f.get("value_text", f["value"])), f"{f['contribution_pct_points']:+.1f} points ({f['direction']})"])
    tab = Table(rows, colWidths=[62 * mm, 40 * mm, 68 * mm], repeatRows=1)
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), VIOLET), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                             ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#d1d5db")),
                             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")])]))
    story += [Spacer(1, 3 * mm), tab]

    story.append(Paragraph("Values you entered", h2))
    lookup = {f["factor"]: (f.get("label") or pretty(f["factor"]), str(f.get("value_text", f["value"])))
              for f in pred["all_factors"]}
    items = [(k, v) for k, v in patient.items()]
    half = (len(items) + 1) // 2
    grid = []
    for i in range(half):
        l, r = items[i], items[i + half] if i + half < len(items) else ("", "")
        lk = lambda it: lookup.get(it[0], (pretty(it[0]) if it[0] else "", str(it[1])))
        grid.append([lk(l)[0], lk(l)[1], lk(r)[0] if r[0] else "", lk(r)[1] if r[0] else ""])
    g = Table(grid, colWidths=[48 * mm, 35 * mm, 48 * mm, 35 * mm])
    g.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("LINEBELOW", (0, 0), (-1, -1), .25, colors.HexColor("#e5e7eb"))]))
    story.append(g)

    story += [Spacer(1, 8 * mm),
              Paragraph("<b>Important.</b> BRISK2 is a research prototype and not a medical device. The percentage is a model "
                        "estimate, it is not a diagnosis, and it must not be used to start, change or stop treatment. "
                        "Please discuss any health concern with a doctor.", small),
              Paragraph(f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.", small)]
    doc.build(story)
    return buf.getvalue()
