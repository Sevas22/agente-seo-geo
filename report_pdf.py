# -*- coding: utf-8 -*-
"""
report_pdf.py
--------------
Genera el informe de diagnóstico SEO & GEO en PDF, completo y detallado,
a partir del diccionario `report` producido por seo_geo_audit.audit_domain().

Secciones generadas:
  1. Portada con scores y estado general
  2. Resumen ejecutivo (IA o plantilla automática)
  3. Diagnóstico técnico SEO (tabla detallada)
  4. Señales GEO — visibilidad en IA generativa
  5. Análisis de contenido y palabras clave
  6. Estructura del sitio (enlaces, encabezados)
  7. Presencia social (Open Graph)
  8. Plan de acción priorizado
  9. Roadmap 30 / 60 / 90 días
 10. CTA final
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    ListFlowable, ListItem, Image, HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# -----------------------------------------------------------------------
# Branding por defecto
# -----------------------------------------------------------------------
DEFAULT_BRANDING = {
    "company_name": os.environ.get("COMPANY_NAME", "Agencia IDP"),
    "primary_color": os.environ.get("BRAND_PRIMARY_COLOR", "#1C1C1C"),
    "accent_color": os.environ.get("BRAND_ACCENT_COLOR", "#F4511E"),
    "cyan_color": "#29B6F6",
    "logo_path": os.environ.get("BRAND_LOGO_PATH", ""),
    "cta_text": os.environ.get(
        "BRAND_CTA_TEXT",
        "¿Quieres que ejecutemos este plan contigo? Agenda una sesión de "
        "estrategia y empecemos por los quick wins de la semana 1.",
    ),
    "cta_url": os.environ.get("BRAND_CTA_URL", "https://agenciaidp.co"),
    "contact_email": os.environ.get("BRAND_CONTACT_EMAIL", "seo@agenciaidp.com"),
}

# Colores comunes
C_OK      = colors.HexColor("#2E7D32")
C_WARN    = colors.HexColor("#F4511E")
C_ERROR   = colors.HexColor("#C62828")
C_LIGHT   = colors.HexColor("#F5F5F5")
C_BORDER  = colors.HexColor("#E0E0E0")
C_DARK    = colors.HexColor("#1C1C1C")
C_GRAY    = colors.HexColor("#666666")
C_CYAN    = colors.HexColor("#29B6F6")


def _hex(color_str):
    return colors.HexColor(color_str)


def _score_color(score):
    if score >= 75:
        return C_OK
    if score >= 50:
        return C_WARN
    return C_ERROR


def _score_label(score):
    if score >= 75:
        return "Bueno"
    if score >= 50:
        return "Regular"
    return "Crítico"


# -----------------------------------------------------------------------
# Estilos
# -----------------------------------------------------------------------
def _styles(b):
    styles = getSampleStyleSheet()
    accent = _hex(b["accent_color"])
    primary = _hex(b["primary_color"])

    styles.add(ParagraphStyle("ReportTitle", parent=styles["Title"],
        textColor=colors.white, fontSize=26, spaceAfter=6, leading=30))
    styles.add(ParagraphStyle("ReportSubtitle", parent=styles["Normal"],
        textColor=colors.HexColor("#CCCCCC"), fontSize=12, spaceAfter=4))
    styles.add(ParagraphStyle("SectionHeading", parent=styles["Heading2"],
        textColor=primary, spaceBefore=16, spaceAfter=6, fontSize=13,
        borderPad=2))
    styles.add(ParagraphStyle("SubHeading", parent=styles["Heading3"],
        textColor=C_GRAY, spaceBefore=10, spaceAfter=4, fontSize=11))
    styles.add(ParagraphStyle("Body", parent=styles["BodyText"],
        fontSize=9.5, leading=14))
    styles.add(ParagraphStyle("BodySmall", parent=styles["BodyText"],
        fontSize=8.5, leading=12, textColor=C_GRAY))
    styles.add(ParagraphStyle("CTA", parent=styles["BodyText"],
        fontSize=11, leading=15, textColor=colors.white))
    styles.add(ParagraphStyle("Caption", parent=styles["Normal"],
        fontSize=7.5, textColor=C_GRAY))
    styles.add(ParagraphStyle("ScoreCover", parent=styles["Normal"],
        fontSize=44, alignment=TA_CENTER, textColor=colors.white,
        leading=48, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("ScoreLabel", parent=styles["Normal"],
        fontSize=9, alignment=TA_CENTER, textColor=C_GRAY))
    styles.add(ParagraphStyle("Keyword", parent=styles["Normal"],
        fontSize=9, textColor=C_DARK))
    styles.add(ParagraphStyle("RoadmapTitle", parent=styles["Normal"],
        fontSize=10, fontName="Helvetica-Bold", textColor=colors.white))
    styles.add(ParagraphStyle("RoadmapBody", parent=styles["Normal"],
        fontSize=9, textColor=colors.white, leading=13))
    return styles


# -----------------------------------------------------------------------
# Helpers de tablas
# -----------------------------------------------------------------------
def _info_table(rows, col_widths=None):
    styles = getSampleStyleSheet()
    key_style = ParagraphStyle("K", parent=styles["BodyText"],
        fontSize=9, fontName="Helvetica-Bold", leading=12)
    val_style = ParagraphStyle("V", parent=styles["BodyText"],
        fontSize=9, leading=12)

    col_widths = col_widths or [5.5 * cm, 11 * cm]
    data = [[Paragraph(str(k), key_style), Paragraph(str(v), val_style)]
            for k, v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",  (0, 0), (-1, -1), 0.3, C_BORDER),
        ("BACKGROUND", (0, 0), (0, -1),  C_LIGHT),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    return t


def _status_badge(status):
    """Retorna texto con color para OK / MEJORAR / CRÍTICO."""
    if status == "OK":
        return f'<font color="#2E7D32"><b>✓ OK</b></font>'
    if status == "MEJORAR":
        return f'<font color="#F4511E"><b>▲ MEJORAR</b></font>'
    return f'<font color="#C62828"><b>✗ CRÍTICO</b></font>'


def _priority_badge(p):
    if p == "Alta":
        return f'<font color="#C62828"><b>Alta</b></font>'
    if p == "Media":
        return f'<font color="#F4511E"><b>Media</b></font>'
    return f'<font color="#2E7D32">Baja</font>'


def _diagnostic_table(rows_data, col_widths=None):
    """
    rows_data: list of (elemento, status, hallazgo, accion, prioridad)
    status: "OK" | "MEJORAR" | "CRÍTICO"
    prioridad: "Alta" | "Media" | "Baja" | ""
    """
    ss = getSampleStyleSheet()
    hdr = ParagraphStyle("H", parent=ss["BodyText"], fontSize=8,
        fontName="Helvetica-Bold", textColor=colors.white, leading=11)
    cell = ParagraphStyle("C", parent=ss["BodyText"], fontSize=8.5, leading=12)

    cw = col_widths or [3.5*cm, 1.8*cm, 4.5*cm, 5.0*cm, 1.6*cm]

    header = [
        Paragraph("ELEMENTO", hdr),
        Paragraph("ESTADO", hdr),
        Paragraph("HALLAZGO", hdr),
        Paragraph("ACCIÓN RECOMENDADA", hdr),
        Paragraph("PRIOR.", hdr),
    ]
    data = [header]
    for elem, status, hallazgo, accion, prio in rows_data:
        data.append([
            Paragraph(str(elem), cell),
            Paragraph(_status_badge(status), cell),
            Paragraph(str(hallazgo), cell),
            Paragraph(str(accion), cell),
            Paragraph(_priority_badge(prio) if prio else "—", cell),
        ])

    t = Table(data, colWidths=cw)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_DARK),
        ("BOX",        (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID",  (0, 0), (-1, -1), 0.3, C_BORDER),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]
    # Alternar filas
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), C_LIGHT))
    t.setStyle(TableStyle(style))
    return t


def _score_mini(label, score, styles, width=4.0*cm):
    sc = _score_color(score)
    lb = _score_label(score)
    # Barra de progreso como tabla
    bar_w = width - 0.4*cm
    filled = max(0.1*cm, bar_w * score / 100)
    empty  = max(0, bar_w - filled)

    bar = Table([[""]], colWidths=[filled])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), sc),
        ("ROWHEIGHT",  (0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]))

    ss = getSampleStyleSheet()
    score_p = ParagraphStyle("SP", parent=ss["Normal"],
        fontSize=22, fontName="Helvetica-Bold", alignment=TA_CENTER,
        textColor=sc, leading=26)
    lbl_p = ParagraphStyle("LP", parent=ss["Normal"],
        fontSize=8, alignment=TA_CENTER, textColor=C_GRAY)
    badge_p = ParagraphStyle("BP", parent=ss["Normal"],
        fontSize=8, alignment=TA_CENTER, textColor=sc,
        fontName="Helvetica-Bold")

    cell_content = [
        Paragraph(f"<b>{score}</b>/100", score_p),
        Paragraph(label, lbl_p),
        bar,
        Paragraph(lb, badge_p),
    ]
    t = Table([[c] for c in cell_content], colWidths=[width])
    t.setStyle(TableStyle([
        ("BOX",          (0,0), (-1,-1), 0.5, C_BORDER),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("LEFTPADDING",  (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    return t


# -----------------------------------------------------------------------
# generate_pdf — función principal
# -----------------------------------------------------------------------
def generate_pdf(report, lead, output_path, branding=None):
    b = dict(DEFAULT_BRANDING)
    if branding:
        b.update(branding)

    styles = _styles(b)
    story  = []
    W = 16.5 * cm   # ancho útil

    onpage  = report.get("onpage", {})
    geo     = report.get("geo_signals", {})
    sd      = report.get("structured_data", {})
    content = report.get("content", {})
    scores  = report.get("scores", {})
    robots  = report.get("robots_txt", {})
    sitemap = report.get("sitemap", {})
    llms    = report.get("llms_txt", {})
    domain  = report.get("domain", "-")
    fecha   = report.get("fetched_at", datetime.now().strftime("%Y-%m-%d %H:%M"))

    nombre_lead = (lead or {}).get("nombre", "")
    empresa_lead = (lead or {}).get("empresa", "")

    # ==================================================================
    # 1. PORTADA
    # ==================================================================
    # Bloque oscuro de portada
    cover_data = [[
        Paragraph(
            f'<font color="#F4511E">AGENCIA IDP · DIAGNÓSTICO SEO + GEO PREMIUM</font>',
            styles["BodySmall"]),
    ]]
    cover_top = Table(cover_data, colWidths=[W])
    cover_top.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_DARK),
        ("LEFTPADDING",  (0,0), (-1,-1), 16),
        ("TOPPADDING",   (0,0), (-1,-1), 20),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
    ]))

    # Logo + título
    logo_path = b.get("logo_path", "")
    logo_elem = ""
    if logo_path and os.path.exists(logo_path):
        logo_elem = Image(logo_path, width=3.5*cm, height=1.3*cm)

    score_gen = scores.get("promedio_general", 0)
    sc_color  = _score_color(score_gen)

    cover_main_left = []
    if logo_elem:
        cover_main_left.append(logo_elem)
        cover_main_left.append(Spacer(1, 0.2*cm))
    cover_main_left.append(Paragraph("Informe de crecimiento<br/>orgánico<br/>+ presencia en IA",
        styles["ReportTitle"]))
    cover_main_left.append(Spacer(1, 0.3*cm))
    cover_main_left.append(Paragraph(
        f'<font color="#888888">FECHA DE ANÁLISIS</font>', styles["BodySmall"]))
    cover_main_left.append(Paragraph(
        datetime.now().strftime("%B %Y").capitalize(), styles["ReportSubtitle"]))
    cover_main_left.append(Paragraph(
        f'<font color="#888888">DOMINIO ANALIZADO</font>', styles["BodySmall"]))
    cover_main_left.append(Paragraph(
        f'<b>{domain}</b>', styles["ReportSubtitle"]))
    if nombre_lead:
        etiqueta = nombre_lead + (f" — {empresa_lead}" if empresa_lead else "")
        cover_main_left.append(Paragraph(
            f'Preparado para: {etiqueta}', styles["BodySmall"]))

    # Score box derecho
    sc_hex = sc_color.hexval()[2:]
    score_box_content = [
        Paragraph(f'<font color="#{sc_hex}"><b>{score_gen}</b></font>',
            styles["ScoreCover"]),
        Paragraph("/ 100", ParagraphStyle("sl", parent=styles["BodySmall"],
            alignment=TA_CENTER, textColor=colors.HexColor("#AAAAAA"), fontSize=11)),
        Paragraph("Score SEO + GEO", ParagraphStyle("sl2", parent=styles["BodySmall"],
            alignment=TA_CENTER, textColor=colors.white, fontSize=9,
            fontName="Helvetica-Bold")),
        Spacer(1, 4),
        Table([[Paragraph(_score_label(score_gen),
            ParagraphStyle("sl3", parent=styles["BodySmall"],
                alignment=TA_CENTER, textColor=C_DARK,
                fontName="Helvetica-Bold", fontSize=10))]],
            colWidths=[3.8*cm]),
    ]
    score_box_content[-1].setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), sc_color),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    score_box = Table([[c] for c in score_box_content], colWidths=[4.2*cm])
    score_box.setStyle(TableStyle([
        ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#444444")),
        ("BACKGROUND",   (0,0),(-1,-1), colors.HexColor("#2A2A2A")),
        ("ALIGN",        (0,0),(-1,-1), "CENTER"),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 6),
        ("RIGHTPADDING", (0,0),(-1,-1), 6),
    ]))

    cover_main = Table(
        [[cover_main_left, score_box]],
        colWidths=[11.5*cm, 4.5*cm],
    )
    cover_main.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), C_DARK),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0), (0,-1),  16),
        ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ("TOPPADDING",   (0,0), (-1,-1), 14),
        ("BOTTOMPADDING",(0,0), (-1,-1), 20),
    ]))

    story.append(cover_top)
    story.append(cover_main)
    story.append(Spacer(1, 0.5*cm))

    # Barras de scores por área
    story.append(Paragraph("Estado general por área",
        ParagraphStyle("SGA", parent=styles["SectionHeading"],
            spaceBefore=4, spaceAfter=2)))
    story.append(Paragraph("Puntajes medidos por el motor de análisis (0-100).",
        styles["BodySmall"]))
    story.append(Spacer(1, 0.25*cm))

    def _bar_row(label, score):
        sc = _score_color(score)
        sc_h = sc.hexval()[2:]
        bar_total = 10.5*cm
        filled = max(0.3*cm, bar_total * score / 100)
        bar_fill = Table([[""]], colWidths=[filled])
        bar_fill.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), sc),
            ("ROWHEIGHT",  (0,0),(-1,-1), 14),
            ("LEFTPADDING",  (0,0),(-1,-1), 0),
            ("RIGHTPADDING", (0,0),(-1,-1), 0),
            ("TOPPADDING",   (0,0),(-1,-1), 0),
            ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ]))
        ss = getSampleStyleSheet()
        lbl_s = ParagraphStyle("BL", parent=ss["Normal"], fontSize=9,
            textColor=C_DARK, leading=12)
        sc_s = ParagraphStyle("BS", parent=ss["Normal"], fontSize=9,
            textColor=sc, fontName="Helvetica-Bold", alignment=TA_RIGHT,
            leading=12)
        return [
            Paragraph(label, lbl_s),
            bar_fill,
            Paragraph(f'<font color="#{sc_h}"><b>{score}</b></font>/100', sc_s),
        ]

    bar_data = [
        _bar_row("SEO técnico",          scores.get("seo_tecnico", 0)),
        _bar_row("GEO / visibilidad en IA", scores.get("geo", 0)),
        _bar_row("Contenido",            scores.get("contenido", 0)),
    ]
    bar_table = Table(bar_data, colWidths=[4.0*cm, 10.5*cm, 2.0*cm])
    bar_table.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    story.append(bar_table)

    # ==================================================================
    # 2. RESUMEN EJECUTIVO
    # ==================================================================
    story.append(Spacer(1, 0.4*cm))
    ai_summary = report.get("ai_summary")
    if ai_summary and ai_summary.strip():
        story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
        story.append(Paragraph("Resumen ejecutivo", styles["SectionHeading"]))
        for parrafo in ai_summary.strip().split("\n"):
            p = parrafo.strip()
            if p:
                story.append(Paragraph(p, styles["Body"]))
                story.append(Spacer(1, 0.1*cm))
        story.append(Paragraph(
            "Resumen generado automáticamente con IA a partir del análisis técnico.",
            styles["Caption"]))
    else:
        # Resumen automático basado en datos
        story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
        story.append(Paragraph("Resumen ejecutivo", styles["SectionHeading"]))
        problemas = []
        logros = []

        if not report.get("https"):
            problemas.append("el sitio no usa HTTPS")
        else:
            logros.append("HTTPS activo y funcional")

        tl = onpage.get("title_length", 0)
        if tl < 10 or tl > 60:
            problemas.append(f"el title tiene {tl} caracteres (ideal: 50-60)")
        else:
            logros.append("etiqueta title bien optimizada")

        if onpage.get("h1_count", 0) != 1:
            problemas.append(f"hay {onpage.get('h1_count',0)} etiquetas H1 (debe ser exactamente 1)")
        else:
            logros.append("estructura H1 correcta")

        if not llms.get("exists"):
            problemas.append("no existe llms.txt para visibilidad en IAs")

        if not sd.get("has_faqpage"):
            problemas.append("no hay schema FAQPage, lo que reduce la visibilidad en AI Overviews")

        if sd.get("jsonld_present"):
            logros.append(f"datos estructurados Schema.org presentes: {', '.join(sd.get('types_found', [])[:4])}")

        rt = report.get("response_time_seconds", 0)
        if rt < 1.5:
            logros.append(f"tiempo de respuesta excelente ({rt}s)")
        else:
            problemas.append(f"tiempo de respuesta lento ({rt}s)")

        resumen = (
            f"El análisis de <b>{domain}</b> arroja un puntaje general de "
            f"<b>{score_gen}/100</b>. "
        )
        if logros:
            resumen += f"El sitio tiene fortalezas claras: {'; '.join(logros)}. "
        if problemas:
            resumen += (
                f"Sin embargo, se detectaron oportunidades de mejora importantes: "
                f"{'; '.join(problemas)}. "
            )
        resumen += (
            f"El plan de acción detallado en este informe permite mejorar el "
            f"posicionamiento en Google y la presencia en herramientas de IA "
            f"(ChatGPT, Gemini, Perplexity) en un plazo de 30 a 90 días."
        )
        story.append(Paragraph(resumen, styles["Body"]))

    # ==================================================================
    # 3. DIAGNÓSTICO TÉCNICO SEO (tabla detallada)
    # ==================================================================
    story.append(Spacer(1, 0.3*cm))
    story.append(PageBreak())

    num_section = [0]
    def section(title, subtitle=""):
        num_section[0] += 1
        n = num_section[0]
        badge = Table([[Paragraph(str(n), ParagraphStyle("N",
            parent=styles["Body"], fontName="Helvetica-Bold",
            textColor=colors.white, alignment=TA_CENTER))]],
            colWidths=[0.55*cm])
        badge.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), _hex(b["accent_color"])),
            ("TOPPADDING",   (0,0),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ]))
        sub_p = Paragraph(subtitle, styles["Caption"]) if subtitle else None
        title_p = Paragraph(title, styles["SectionHeading"])
        inner = [[badge, title_p]]
        tt = Table(inner, colWidths=[0.7*cm, W - 0.7*cm])
        tt.setStyle(TableStyle([
            ("VALIGN",      (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0),(-1,-1), 0),
            ("TOPPADDING",  (0,0),(-1,-1), 0),
            ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ]))
        story.append(tt)
        if sub_p:
            story.append(sub_p)

    section("Diagnóstico técnico", "Verificado directamente sobre el sitio")

    title_ok   = bool(onpage.get("title")) and 10 <= onpage.get("title_length", 0) <= 60
    meta_ok    = bool(onpage.get("meta_description")) and 50 <= onpage.get("meta_description_length", 0) <= 160
    h1_ok      = onpage.get("h1_count") == 1

    title_val  = f'"{onpage.get("title","—")}" ({onpage.get("title_length",0)} car.)'
    meta_val   = f'{onpage.get("meta_description_length",0)} caracteres'
    h1_val     = f'{onpage.get("h1_count",0)} H1 detectados'
    h1_act     = "Usar un único H1 con la keyword principal" if not h1_ok else "Mantener"
    title_act  = "Incluir keyword principal, 50-60 caracteres" if not title_ok else "Mantener"
    meta_act   = "Añadir CTA y diferenciador" if not meta_ok else "Mantener (añadir CTA)"

    og_count   = len(onpage.get("open_graph_tags", {}))
    rt_ok      = report.get("response_time_seconds", 99) < 1.5
    img_miss   = onpage.get("images_missing_alt", 0)
    img_ok     = img_miss == 0

    diag_rows = [
        ("HTTPS / SSL",      "OK" if report.get("https") else "CRÍTICO",
         "Activo y funcional" if report.get("https") else "No activo",
         "Mantener activo" if report.get("https") else "Migrar a HTTPS inmediatamente", ""),
        ("Title homepage",   "OK" if title_ok else "MEJORAR",
         title_val, title_act, "" if title_ok else "Media"),
        ("H1 homepage",      "OK" if h1_ok else "MEJORAR",
         h1_val, h1_act, "" if h1_ok else "Media"),
        ("Meta description", "OK" if meta_ok else "MEJORAR",
         meta_val, meta_act, ""),
        ("Open Graph",       "OK" if og_count >= 4 else "MEJORAR",
         f"{og_count} etiquetas og:", "Mantener actualizado" if og_count >= 4 else "Agregar og:title, og:description, og:image", ""),
        ("Schema markup",    "OK" if sd.get("jsonld_present") else "MEJORAR",
         ", ".join(sd.get("types_found", [])) or "No detectado",
         "Mantener y ampliar (FAQPage)" if sd.get("jsonld_present") else "Implementar Schema Organization + FAQPage",
         "" if sd.get("jsonld_present") else "Alta"),
        ("Sitemap XML",      "OK" if sitemap.get("exists") else "MEJORAR",
         "Encontrado" if sitemap.get("exists") else "No encontrado",
         "Mantener y enviar a Search Console" if sitemap.get("exists") else "Crear sitemap.xml", ""),
        ("robots.txt",       "OK" if robots.get("exists") else "CRÍTICO",
         "Presente" if robots.get("exists") else "No encontrado",
         "Revisar acceso de bots de IA" if robots.get("exists") else "Crear robots.txt", ""),
        ("Canonical / URL",  "OK" if onpage.get("canonical") else "MEJORAR",
         "Canónica definida" if onpage.get("canonical") else "No definida",
         "Mantener" if onpage.get("canonical") else "Agregar etiqueta canonical", ""),
        ("Mobile (viewport)","OK" if onpage.get("viewport_present") else "CRÍTICO",
         "Responsive" if onpage.get("viewport_present") else "No responsive",
         "Mantener" if onpage.get("viewport_present") else "Agregar meta viewport", ""),
        ("Acceso de bots IA","OK" if not geo.get("ai_bots_explicitly_blocked") else "MEJORAR",
         "Permitido" if not geo.get("ai_bots_explicitly_blocked") else f'Bloqueados: {", ".join(geo["ai_bots_explicitly_blocked"])}',
         "Mantener acceso abierto" if not geo.get("ai_bots_explicitly_blocked") else "Revisar política de bots", ""),
        ("llms.txt",         "OK" if llms.get("exists") else "MEJORAR",
         "Presente" if llms.get("exists") else "Ausente",
         "Mantener" if llms.get("exists") else "Crear llms.txt (resumen del sitio)", "Media"),
        ("Imágenes con alt", "OK" if img_ok else "MEJORAR",
         f"{img_miss} de {onpage.get('images_total',0)} sin alt",
         "Mantener" if img_ok else f"Agregar alt a {img_miss} imágenes", "" if img_ok else "Media"),
        ("Velocidad respuesta","OK" if rt_ok else "MEJORAR",
         f'{report.get("response_time_seconds","?")} s',
         "Mantener" if rt_ok else "Optimizar servidor / CDN / caché", "" if rt_ok else "Alta"),
    ]

    story.append(Spacer(1, 0.2*cm))
    story.append(_diagnostic_table(diag_rows))

    # ==================================================================
    # 4. REPUTACIÓN ONLINE Y AUTORIDAD
    # ==================================================================
    story.append(Spacer(1, 0.5*cm))

    rep_note = ParagraphStyle("RN", parent=styles["BodySmall"],
        textColor=C_GRAY, leading=12)
    story.append(Paragraph("Reputación online y autoridad",
        styles["SubHeading"]))
    story.append(Paragraph(
        "Reseñas (Trustpilot, Google) y perfil de enlaces.", styles["BodySmall"]))
    story.append(Spacer(1, 0.2*cm))

    has_review_schema = any("aggregaterating" in t.lower() or "review" in t.lower()
                            for t in sd.get("types_found", []))
    rep_data = [
        ("Reseñas en tu sitio (schema)",
         "OK" if has_review_schema else "MEJORAR",
         "Detectadas" if has_review_schema else "No detectadas — añadir schema AggregateRating"),
        ("Trustpilot",  "MEJORAR",
         "Requiere API de reseñas (DataForSEO) para verificar"),
        ("Google reviews", "MEJORAR",
         "Requiere API (Google Places / DataForSEO)"),
        ("Backlinks / autoridad", "MEJORAR",
         "Requiere API de SEO (DataForSEO / Ahrefs) para datos reales"),
    ]

    ss2 = getSampleStyleSheet()
    cs  = ParagraphStyle("cs", parent=ss2["BodyText"], fontSize=8.5, leading=12)
    hs  = ParagraphStyle("hs", parent=ss2["BodyText"], fontSize=8,
        fontName="Helvetica-Bold", textColor=colors.white)

    rep_header = [
        Paragraph("ELEMENTO", hs),
        Paragraph("ESTADO", hs),
        Paragraph("DETALLE", hs),
    ]
    rep_rows = [rep_header]
    for elem, status, detalle in rep_data:
        rep_rows.append([
            Paragraph(elem, cs),
            Paragraph(_status_badge(status), cs),
            Paragraph(detalle, cs),
        ])
    rep_t = Table(rep_rows, colWidths=[4.5*cm, 2.2*cm, 9.3*cm])
    rep_t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0),  C_DARK),
        ("BOX",          (0,0),(-1,-1), 0.5, C_BORDER),
        ("INNERGRID",    (0,0),(-1,-1), 0.3, C_BORDER),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 7),
        ("RIGHTPADDING", (0,0),(-1,-1), 7),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    for i in range(2, len(rep_rows), 2):
        rep_t.setStyle(TableStyle([("BACKGROUND", (0,i),(-1,i), C_LIGHT)]))
    story.append(rep_t)

    # ==================================================================
    # 5. SEÑALES GEO — VISIBILIDAD EN IA
    # ==================================================================
    story.append(PageBreak())
    section("Señales GEO — Visibilidad en motores de IA generativa",
            "ChatGPT · Gemini · Perplexity · AI Overviews")

    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "La GEO (Generative Engine Optimization) determina si tu sitio aparece "
        "como fuente citada en respuestas de inteligencia artificial. "
        "A diferencia del SEO tradicional, las IAs priorizan sitios con contenido "
        "estructurado, Schema.org y acceso libre a sus bots de rastreo.",
        styles["Body"]))
    story.append(Spacer(1, 0.3*cm))

    geo_diag = [
        ("Bots IA en robots.txt",
         "OK" if not geo.get("ai_bots_explicitly_blocked") else "MEJORAR",
         "Sin bloqueos detectados" if not geo.get("ai_bots_explicitly_blocked")
             else f'Bloqueados: {", ".join(geo["ai_bots_explicitly_blocked"])}',
         "Mantener acceso abierto a GPTBot, ClaudeBot, Perplexity, Google-Extended",
         "Alta" if geo.get("ai_bots_explicitly_blocked") else ""),
        ("llms.txt",
         "OK" if llms.get("exists") else "MEJORAR",
         "Presente" if llms.get("exists") else "Ausente",
         "Crear /llms.txt con resumen del negocio, servicios y contacto",
         "Media"),
        ("Schema Organization",
         "OK" if sd.get("has_organization") else "MEJORAR",
         "Presente" if sd.get("has_organization") else "No detectado",
         "Añadir schema Organization con nombre, URL, logo, contacto",
         "" if sd.get("has_organization") else "Alta"),
        ("Schema FAQPage",
         "OK" if sd.get("has_faqpage") else "MEJORAR",
         "Presente" if sd.get("has_faqpage") else "No detectado",
         "Crear sección FAQ + schema FAQPage para aparecer en AI Overviews",
         "" if sd.get("has_faqpage") else "Alta"),
        ("Contenido visible sin JS",
         "OK" if not geo.get("likely_js_heavy") else "MEJORAR",
         "Adecuado" if not geo.get("likely_js_heavy") else "Posible dependencia de JS",
         "Mantener SSR / pre-renderizado para que los crawlers lean el contenido",
         "" if not geo.get("likely_js_heavy") else "Alta"),
        ("Meta description",
         "OK" if onpage.get("meta_description") else "CRÍTICO",
         f'{onpage.get("meta_description_length",0)} caracteres'
             if onpage.get("meta_description") else "Ausente",
         "La meta description es usada por IAs como resumen del sitio",
         "" if onpage.get("meta_description") else "Alta"),
        ("Datos estructurados extra",
         "OK" if len(sd.get("types_found", [])) >= 3 else "MEJORAR",
         ", ".join(sd.get("types_found", [])) or "Ninguno",
         "Ampliar con LocalBusiness, Product, BreadcrumbList según el negocio",
         "Media"),
    ]

    story.append(_diagnostic_table(geo_diag,
        col_widths=[3.5*cm, 1.8*cm, 4.0*cm, 5.5*cm, 1.7*cm]))

    story.append(Spacer(1, 0.35*cm))
    story.append(Paragraph(
        "<b>¿Por qué importa la GEO?</b> Las búsquedas con IA (ChatGPT, Perplexity, "
        "Google AI Overviews) ya representan millones de consultas diarias. Los sitios "
        "citados en estas respuestas reciben tráfico de alta intención sin pagar publicidad. "
        "Optimizar la GEO hoy es una ventaja competitiva que la mayoría de empresas "
        "aún no aprovecha.",
        styles["Body"]))

    # ==================================================================
    # 6. ANÁLISIS DE CONTENIDO Y PALABRAS CLAVE
    # ==================================================================
    story.append(Spacer(1, 0.3*cm))
    story.append(PageBreak())
    section("Análisis de contenido y palabras clave",
            "Análisis de la página principal")

    story.append(Spacer(1, 0.2*cm))

    wc = content.get("word_count", 0)
    wc_status = "OK" if wc >= 300 else "MEJORAR"
    wc_msg = (f"<b>{wc} palabras</b> detectadas en la página principal. "
              + ("Buen volumen de contenido para indexación." if wc >= 600
                 else "Se recomienda al menos 300-600 palabras para posicionamiento efectivo." if wc >= 300
                 else "<b>Contenido escaso.</b> Ampliar a mínimo 600 palabras con temáticas relevantes."))
    story.append(Paragraph(wc_msg, styles["Body"]))
    story.append(Spacer(1, 0.2*cm))

    # Encabezados
    headings = onpage.get("headings", {})
    hdg_rows = [(f"Etiqueta {k.upper()}", str(v)) for k, v in headings.items() if v > 0]
    hdg_rows.insert(0, ("Links internos", str(onpage.get("internal_links", 0))))
    hdg_rows.insert(1, ("Links externos", str(onpage.get("external_links", 0))))
    hdg_rows.insert(0, ("Palabras totales", str(wc)))
    story.append(Paragraph("Estructura de contenido", styles["SubHeading"]))
    story.append(_info_table(hdg_rows, col_widths=[5.0*cm, 11.5*cm]))
    story.append(Spacer(1, 0.35*cm))

    # Keywords
    kws = content.get("top_keywords", [])
    if kws:
        story.append(Paragraph("Palabras clave más frecuentes en la página", styles["SubHeading"]))
        story.append(Paragraph(
            "Estas son las palabras que el motor de búsqueda e IA identificarán "
            "como temáticas principales de tu sitio. Verifica que coincidan con "
            "los servicios que ofreces y con lo que tus clientes buscan.",
            styles["Body"]))
        story.append(Spacer(1, 0.2*cm))

        # Tabla visual de keywords
        kw_style = ParagraphStyle("kw", parent=styles["Body"],
            fontSize=9, leading=12)
        max_count = max(c for _, c in kws) if kws else 1
        kw_data = []
        row = []
        for i, (word, count) in enumerate(kws[:15]):
            pct = int(100 * count / max_count)
            cell = Table([
                [Paragraph(f"<b>{word}</b>", kw_style)],
                [Paragraph(f"{count} veces", styles["Caption"])],
            ], colWidths=[4.5*cm])
            cell.setStyle(TableStyle([
                ("BOX",          (0,0),(-1,-1), 0.5, C_BORDER),
                ("BACKGROUND",   (0,0),(-1,-1), C_LIGHT),
                ("LEFTPADDING",  (0,0),(-1,-1), 8),
                ("TOPPADDING",   (0,0),(-1,-1), 5),
                ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ]))
            row.append(cell)
            if len(row) == 3 or i == len(kws[:15]) - 1:
                while len(row) < 3:
                    row.append(Paragraph("", styles["Body"]))
                kw_data.append(row)
                row = []

        if kw_data:
            kw_table = Table(kw_data, colWidths=[5.0*cm, 5.0*cm, 5.0*cm],
                hAlign="LEFT")
            kw_table.setStyle(TableStyle([
                ("LEFTPADDING",  (0,0),(-1,-1), 4),
                ("RIGHTPADDING", (0,0),(-1,-1), 4),
                ("TOPPADDING",   (0,0),(-1,-1), 4),
                ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ]))
            story.append(kw_table)

    # Preview de contenido
    preview = content.get("first_paragraph_preview", "")
    if preview:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Vista previa del contenido indexable", styles["SubHeading"]))
        story.append(Paragraph(f'"{preview}"', styles["BodySmall"]))

    # ==================================================================
    # 7. OPEN GRAPH / PRESENCIA SOCIAL
    # ==================================================================
    story.append(Spacer(1, 0.4*cm))
    section("Presencia social y Open Graph",
            "Cómo se ve tu sitio al compartirlo en redes sociales")

    og_tags = onpage.get("open_graph_tags", {})
    og_rows = []
    for key in ["og:title", "og:description", "og:image", "og:url", "og:type", "og:site_name"]:
        val = og_tags.get(key)
        og_rows.append((key, val[:100] if val else "⚠ No definido"))

    story.append(Spacer(1, 0.2*cm))
    story.append(_info_table(og_rows, col_widths=[4.5*cm, 12.0*cm]))
    story.append(Spacer(1, 0.15*cm))
    if og_count < 4:
        story.append(Paragraph(
            "Las etiquetas Open Graph controlan cómo se ve el enlace cuando alguien "
            "comparte tu sitio en WhatsApp, LinkedIn o Facebook. "
            "Sin ellas, el preview es genérico y poco atractivo, lo que reduce el click-through.",
            styles["Body"]))

    # ==================================================================
    # 8. PLAN DE ACCIÓN PRIORIZADO
    # ==================================================================
    story.append(PageBreak())
    section("Plan de acción priorizado",
            "Ordenado por impacto y facilidad de implementación")
    story.append(Spacer(1, 0.2*cm))

    recs = report.get("recommendations", [])
    alta   = [r for r in recs if any(w in r.lower() for w in ["https", "ssr", "schema", "h1", "faqpage", "organization"])]
    media  = [r for r in recs if r not in alta and any(w in r.lower() for w in ["title", "meta", "canonical", "alt", "velocidad", "llms", "backlinks"])]
    baja   = [r for r in recs if r not in alta and r not in media]

    def _priority_block(label, items, bg_color, text_color=C_DARK):
        if not items:
            return None
        ss3 = getSampleStyleSheet()
        lbl_s = ParagraphStyle("PL", parent=ss3["Normal"], fontSize=9,
            fontName="Helvetica-Bold", textColor=text_color)
        item_s = ParagraphStyle("PI", parent=ss3["Normal"], fontSize=8.5,
            leading=13, textColor=text_color)
        def _esc(t):
            return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        content_rows = [[Paragraph(_esc(label), lbl_s)]]
        for it in items:
            content_rows.append([Paragraph(f"&#8594; {_esc(it)}", item_s)])
        t = Table(content_rows, colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), bg_color),
            ("LEFTPADDING",  (0,0),(-1,-1), 12),
            ("RIGHTPADDING", (0,0),(-1,-1), 12),
            ("TOPPADDING",   (0,0),(-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
            ("BOX",          (0,0),(-1,-1), 0.5, C_BORDER),
        ]))
        return t

    b_alta  = _priority_block("🔴  PRIORIDAD ALTA — Resolver en los próximos 7 días",
                               alta, colors.HexColor("#FFF3F2"), C_DARK)
    b_media = _priority_block("🟠  PRIORIDAD MEDIA — Resolver en el mes 1",
                               media, colors.HexColor("#FFF8F0"), C_DARK)
    b_baja  = _priority_block("🟢  PRIORIDAD BAJA / OPTIMIZACIÓN — Mes 2-3",
                               baja, colors.HexColor("#F0FFF4"), C_DARK)

    for block in [b_alta, b_media, b_baja]:
        if block:
            story.append(block)
            story.append(Spacer(1, 0.3*cm))

    # ==================================================================
    # 9. ROADMAP 30 / 60 / 90 DÍAS
    # ==================================================================
    story.append(Spacer(1, 0.2*cm))
    section("Roadmap 30 / 60 / 90 días",
            "Plan de ejecución recomendado para maximizar resultados")
    story.append(Spacer(1, 0.2*cm))

    roadmap = [
        ("MES 1 — Quick wins", colors.HexColor("#1C1C1C"), [
            "Corregir title (50-60 car.) con keyword principal",
            "Ajustar a un único H1 por página",
            "Verificar/crear meta description con CTA",
            "Crear llms.txt con resumen del negocio y servicios",
            "Implementar schema Organization + FAQPage en JSON-LD",
            "Enviar sitemap.xml a Google Search Console",
            "Agregar alt a imágenes sin descripción",
        ]),
        ("MES 2 — Estructura y contenido", colors.HexColor("#F4511E"), [
            "Ampliar contenido de la home a 600+ palabras",
            "Crear/ampliar sección de Preguntas Frecuentes",
            "Completar etiquetas Open Graph (og:image de calidad)",
            "Auditar páginas internas con el mismo checklist",
            "Configurar Google Search Console y corregir errores de rastreo",
            "Iniciar estrategia de contenido mensual (1-2 artículos)",
        ]),
        ("MES 3 — Autoridad y GEO avanzada", colors.HexColor("#29B6F6"), [
            "Iniciar construcción de backlinks (directorios, alianzas, PR digital)",
            "Crear perfil en Trustpilot / Google Business y solicitar reseñas",
            "Ampliar schema: Product, LocalBusiness, BreadcrumbList",
            "Medir posicionamiento en AI Overviews (ChatGPT, Perplexity)",
            "Analizar keywords de competidores y ajustar contenido",
            "Evaluar resultados y ajustar plan para mes 4-6",
        ]),
    ]

    ss4 = getSampleStyleSheet()
    for title_r, bg, items_r in roadmap:
        rt_s = ParagraphStyle("RT", parent=ss4["Normal"], fontSize=10,
            fontName="Helvetica-Bold", textColor=colors.white, leading=13)
        ri_s = ParagraphStyle("RI", parent=ss4["Normal"], fontSize=8.5,
            textColor=colors.white, leading=13)
        rows = [[Paragraph(title_r, rt_s)]]
        for item in items_r:
            rows.append([Paragraph(f"  ✓  {item}", ri_s)])
        rt_table = Table(rows, colWidths=[W])
        rt_table.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,0),  bg),
            ("BACKGROUND",   (0,1),(-1,-1), colors.HexColor("#2A2A2A")),
            ("LEFTPADDING",  (0,0),(-1,-1), 14),
            ("RIGHTPADDING", (0,0),(-1,-1), 14),
            ("TOPPADDING",   (0,0),(-1,-1), 7),
            ("BOTTOMPADDING",(0,0),(-1,-1), 7),
            ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#444")),
        ]))
        story.append(rt_table)
        story.append(Spacer(1, 0.3*cm))

    # ==================================================================
    # 10. CTA FINAL
    # ==================================================================
    story.append(Spacer(1, 0.4*cm))
    cta_ss = getSampleStyleSheet()
    cta_title_s = ParagraphStyle("CTA_T", parent=cta_ss["Normal"],
        fontSize=13, fontName="Helvetica-Bold", textColor=colors.white,
        leading=16)
    cta_body_s = ParagraphStyle("CTA_B", parent=cta_ss["Normal"],
        fontSize=10, textColor=colors.HexColor("#DDDDDD"), leading=14)
    cta_link_s = ParagraphStyle("CTA_L", parent=cta_ss["Normal"],
        fontSize=10, textColor=colors.white, fontName="Helvetica-Bold",
        leading=14)

    cta_content = [
        Paragraph("¿Quieres que ejecutemos este plan contigo?", cta_title_s),
        Spacer(1, 4),
        Paragraph(b["cta_text"], cta_body_s),
        Spacer(1, 6),
        Paragraph(
            f'<b>{b["cta_url"]}</b> &nbsp;|&nbsp; {b["contact_email"]}',
            cta_link_s),
    ]
    cta_table = Table([[cta_content]], colWidths=[W])
    cta_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_DARK),
        ("BOX",          (0,0),(-1,-1), 2, _hex(b["accent_color"])),
        ("LEFTPADDING",  (0,0),(-1,-1), 18),
        ("RIGHTPADDING", (0,0),(-1,-1), 18),
        ("TOPPADDING",   (0,0),(-1,-1), 16),
        ("BOTTOMPADDING",(0,0),(-1,-1), 16),
    ]))
    story.append(cta_table)

    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f"Informe generado por {b['company_name']} · "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        "Datos técnicos medidos automáticamente; análisis estratégico asistido por IA.",
        styles["Caption"],
    ))

    # ==================================================================
    # BUILD
    # ==================================================================
    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_GRAY)
        canvas.drawString(1.5*cm, 0.8*cm,
            f"Agencia IDP · Diagnóstico SEO + GEO Premium · Confidencial")
        canvas.drawRightString(letter[0] - 1.5*cm, 0.8*cm,
            f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=1.5*cm, bottomMargin=1.8*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        title=f"Diagnóstico SEO & GEO Premium — {domain}",
    )
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return output_path
