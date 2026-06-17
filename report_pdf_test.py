# -*- coding: utf-8 -*-
"""
report_pdf.py
--------------
Genera el informe de diagnóstico SEO & GEO en PDF, con la marca de la
empresa, a partir del diccionario `report` producido por
`seo_geo_audit.audit_domain()` (ya con `scores` y `recommendations`).

Uso:
    from report_pdf import generate_pdf
    generate_pdf(report, lead, "informe.pdf", branding=BRANDING)
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable,
    ListItem, Image, HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# ----------------------------------------------------------------------
# Branding por defecto (sobreescribible por variables de entorno / dict)
# ----------------------------------------------------------------------
DEFAULT_BRANDING = {
    "company_name": os.environ.get("COMPANY_NAME", "Tu Agencia SEO"),
    "primary_color": os.environ.get("BRAND_PRIMARY_COLOR", "#2E5395"),
    "accent_color": os.environ.get("BRAND_ACCENT_COLOR", "#F2A20C"),
    "logo_path": os.environ.get("BRAND_LOGO_PATH", ""),  # ruta a un PNG/JPG
    "cta_text": os.environ.get(
        "BRAND_CTA_TEXT",
        "¿Quieres mejorar estos resultados? Agenda una asesoría gratuita con "
        "nuestro equipo de SEO y descubre cómo posicionar mejor tu sitio en "
        "buscadores y en respuestas de IA.",
    ),
    "cta_url": os.environ.get("BRAND_CTA_URL", "https://tu-sitio.com/contacto"),
    "contact_email": os.environ.get("BRAND_CONTACT_EMAIL", "contacto@tu-sitio.com"),
}


def _score_color(score):
    if score >= 80:
        return colors.HexColor("#2E7D32")  # verde
    if score >= 50:
        return colors.HexColor("#F2A20C")  # naranja
    return colors.HexColor("#C62828")  # rojo


def _styles(branding):
    styles = getSampleStyleSheet()
    primary = colors.HexColor(branding["primary_color"])

    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], textColor=primary,
        fontSize=20, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", parent=styles["Normal"], fontSize=11,
        textColor=colors.HexColor("#555555"), spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", parent=styles["Heading2"], textColor=primary,
        spaceBefore=14, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Body", parent=styles["BodyText"], fontSize=10, leading=14,
    ))
    styles.add(ParagraphStyle(
        name="ScoreBig", parent=styles["Normal"], fontSize=28, alignment=TA_CENTER,
        leading=32,
    ))
    styles.add(ParagraphStyle(
        name="ScoreLabel", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
    ))
    styles.add(ParagraphStyle(
        name="CTA", parent=styles["BodyText"], fontSize=11, leading=15,
        textColor=colors.white, alignment=TA_LEFT,
    ))
    return styles


def _score_box(label, score, styles, width):
    color = _score_color(score)
    cell = [
        Paragraph(f'<font color="#{color.hexval()[2:]}"><b>{score}</b></font>', styles["ScoreBig"]),
        Paragraph(label, styles["ScoreLabel"]),
    ]
    t = Table([[cell[0]], [cell[1]]], colWidths=[width])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#DDDDDD")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def generate_pdf(report, lead, output_path, branding=None):
    """
    report: dict producido por audit_domain() + score_section() + recommendations
    lead: dict con datos del cliente, ej. {"nombre": ..., "email": ..., "empresa": ...}
    output_path: ruta del PDF a generar
    branding: dict opcional para sobreescribir DEFAULT_BRANDING
    """
    b = dict(DEFAULT_BRANDING)
    if branding:
        b.update(branding)

    styles = _styles(b)
    story = []

    # --- Encabezado / branding ---
    if b.get("logo_path") and os.path.exists(b["logo_path"]):
        story.append(Image(b["logo_path"], width=4 * cm, height=1.5 * cm))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(f"Diagnóstico SEO &amp; GEO", styles["ReportTitle"]))
    story.append(Paragraph(
        f"Dominio analizado: <b>{report.get('domain')}</b> &nbsp;|&nbsp; "
        f"Generado: {report.get('fetched_at')}",
        styles["ReportSubtitle"],
    ))
    if lead and lead.get("nombre"):
        story.append(Paragraph(
            f"Preparado para: <b>{lead.get('nombre')}</b>"
            + (f" — {lead['empresa']}" if lead.get("empresa") else ""),
            styles["ReportSubtitle"],
        ))
    story.append(HRFlowable(width="100%", color=colors.HexColor(b["primary_color"]), thickness=1.2))
    story.append(Spacer(1, 0.4 * cm))

    # --- Resumen de puntajes ---
    scores = report.get("scores", {})
    story.append(Paragraph("Resumen de resultados", styles["SectionHeading"]))
    box_width = 4.2 * cm
    score_table = Table(
        [[
            _score_box("Promedio general", scores.get("promedio_general", 0), styles, box_width),
            _score_box("SEO técnico", scores.get("seo_tecnico", 0), styles, box_width),
            _score_box("GEO (IA generativa)", scores.get("geo", 0), styles, box_width),
            _score_box("Contenido", scores.get("contenido", 0), styles, box_width),
        ]],
        colWidths=[box_width] * 4,
    )
    score_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(score_table)
    story.append(Spacer(1, 0.5 * cm))

    # --- Datos generales ---
    story.append(Paragraph("Datos generales", styles["SectionHeading"]))
    general_rows = [
        ["URL analizada", report.get("final_url", "-")],
        ["Código de estado HTTP", str(report.get("status_code", "-"))],
        ["HTTPS", "Sí" if report.get("https") else "No"],
        ["Tiempo de respuesta", f"{report.get('response_time_seconds', '-')} s"],
        ["Tamaño de página", f"{report.get('page_size_kb', '-')} KB"],
    ]
    story.append(_info_table(general_rows))
    story.append(Spacer(1, 0.3 * cm))

    # --- SEO técnico ---
    onpage = report.get("onpage", {})
    story.append(Paragraph("SEO técnico on-page", styles["SectionHeading"]))
    seo_rows = [
        ["Title", f"{onpage.get('title')} ({onpage.get('title_length')} car.)"],
        ["Meta description", f"{(onpage.get('meta_description') or '—')[:160]}"],
        ["H1 / encabezados", f"H1: {onpage.get('h1_count')} | Total encabezados: {sum(onpage.get('headings', {}).values())}"],
        ["Mobile-friendly (viewport)", "Sí" if onpage.get("viewport_present") else "No"],
        ["Canonical", onpage.get("canonical") or "No definido"],
        ["Imágenes sin texto alternativo", str(onpage.get("images_missing_alt", 0))],
        ["Sitemap.xml", "Sí" if report.get("sitemap", {}).get("exists") else "No encontrado"],
        ["robots.txt", "Sí" if report.get("robots_txt", {}).get("exists") else "No encontrado"],
        ["Palabras en la página", str(onpage.get("word_count", 0))],
    ]
    story.append(_info_table(seo_rows))
    story.append(Spacer(1, 0.3 * cm))

    # --- GEO ---
    geo = report.get("geo_signals", {})
    sd = report.get("structured_data", {})
    story.append(Paragraph("Señales GEO — visibilidad en motores de IA generativa", styles["SectionHeading"]))
    geo_rows = [
        ["Bots de IA bloqueados en robots.txt", ", ".join(geo.get("ai_bots_explicitly_blocked", [])) or "Ninguno"],
        ["Archivo llms.txt", "Presente" if geo.get("llms_txt_present") else "No encontrado"],
        ["Datos estructurados (Schema.org)", ", ".join(sd.get("types_found", [])) or "No encontrados"],
        ["Schema FAQPage", "Sí" if sd.get("has_faqpage") else "No"],
        ["Schema Organization", "Sí" if sd.get("has_organization") else "No"],
        ["Contenido visible sin JS", "Bajo (riesgo)" if geo.get("likely_js_heavy") else "Adecuado"],
    ]
    story.append(_info_table(geo_rows))
    story.append(Spacer(1, 0.3 * cm))

    # --- Contenido / keywords ---
    content = report.get("content", {})
    story.append(Paragraph("Contenido y palabras clave", styles["SectionHeading"]))
    kw = ", ".join(f"{w} ({c})" for w, c in content.get("top_keywords", [])[:10])
    story.append(Paragraph(f"<b>Palabras totales:</b> {content.get('word_count', 0)}", styles["Body"]))
    story.append(Paragraph(f"<b>Palabras clave más frecuentes:</b> {kw or '—'}", styles["Body"]))
    story.append(Spacer(1, 0.3 * cm))

    # --- Competencia ---
    story.append(Paragraph("Competencia y backlinks", styles["SectionHeading"]))
    story.append(Paragraph(report.get("competition_backlinks", {}).get("note", ""), styles["Body"]))

    # --- Recomendaciones ---
    story.append(PageBreak())
    story.append(Paragraph("Recomendaciones priorizadas", styles["SectionHeading"]))
    recs = report.get("recommendations", [])
    items = [ListItem(Paragraph(r, styles["Body"]), leftIndent=12) for r in recs]
    if items:
        story.append(ListFlowable(items, bulletType="1", start="1"))
    else:
        story.append(Paragraph("No se encontraron problemas críticos. ¡Buen trabajo!", styles["Body"]))

    # --- CTA final ---
    story.append(Spacer(1, 0.6 * cm))
    cta_table = Table(
        [[Paragraph(b["cta_text"] + f"<br/><br/><b>{b['cta_url']}</b> &nbsp;|&nbsp; {b['contact_email']}", styles["CTA"])]],
        colWidths=[16.5 * cm],
    )
    cta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(b["primary_color"])),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(cta_table)

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        f"Informe generado automáticamente por {b['company_name']} — "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles["ScoreLabel"],
    ))

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=f"Diagnóstico SEO & GEO - {report.get('domain')}",
    )
    doc.build(story)
    return output_path


def _info_table(rows):
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(name="Cell", parent=styles["BodyText"], fontSize=9, leading=12)
    data = [[Paragraph(f"<b>{k}</b>", cell_style), Paragraph(str(v), cell_style)] for k, v in rows]
    t = Table(data, colWidths=[5.5 * cm, 11 * cm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EEEEEE")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F7FA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t