# -*- coding: utf-8 -*-
"""
report_pdf.py
--------------
Genera el informe de diagnóstico SEO & GEO PREMIUM en PDF, con la marca de
la empresa, a partir del diccionario `report` producido por
`seo_geo_audit.audit_domain()` (con `scores` y `recommendations`) y, si está
disponible, `report["ai_summary"]` con el análisis estratégico de IA.

Estructura (inspirada en un informe consultor premium):
    1. Portada: marca + score global + badges + KPIs + resumen ejecutivo +
       diagnóstico por área + lo que funciona / lo que frena.
    2. Problemas críticos (impacto · solución · dificultad · resultado).
    3. Quick wins (<30 días) + diagnóstico GEO.
    4. Diagnóstico técnico (tabla Elemento·Estado·Hallazgo·Acción·Prioridad).
    5. Análisis competitivo + oportunidades de keywords.
    6. Roadmap 30/60/90 + KPIs a 6 meses + próximos pasos.
    7. Conclusión ejecutiva.

Las secciones estratégicas (2, 3, 5, 6, 7 y partes de la 1) provienen de la
IA y solo se renderizan si están presentes. Los datos técnicos (4 y los
puntajes) son siempre medidos por el motor, sin IA.

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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import ImageReader


# ----------------------------------------------------------------------
# Branding
# ----------------------------------------------------------------------
DEFAULT_BRANDING = {
    "company_name": os.environ.get("COMPANY_NAME", "Tu Agencia SEO"),
    "primary_color": os.environ.get("BRAND_PRIMARY_COLOR", "#1F3A5F"),
    "accent_color": os.environ.get("BRAND_ACCENT_COLOR", "#F2A20C"),
    "logo_path": os.environ.get("BRAND_LOGO_PATH", ""),
    "cta_text": os.environ.get(
        "BRAND_CTA_TEXT",
        "¿Quieres que ejecutemos este plan contigo? Agenda una sesión de "
        "estrategia y empecemos por los quick wins de la semana 1.",
    ),
    "cta_url": os.environ.get("BRAND_CTA_URL", "https://tu-sitio.com/contacto"),
    "contact_email": os.environ.get("BRAND_CONTACT_EMAIL", "contacto@tu-sitio.com"),
}

# Paleta
COL_OK = colors.HexColor("#1E8E4E")
COL_WARN = colors.HexColor("#E08600")
COL_FAIL = colors.HexColor("#C62828")
COL_INK = colors.HexColor("#1B2430")
COL_MUTED = colors.HexColor("#5C6B7A")
COL_LIGHT = colors.HexColor("#F4F6F9")
COL_BORDER = colors.HexColor("#DBE1E8")
COL_DARK = colors.HexColor("#2C3A4B")

ESTADO_COLOR = {"ok": COL_OK, "warn": COL_WARN, "fail": COL_FAIL}
ESTADO_LABEL = {"ok": "OK", "warn": "MEJORAR", "fail": "CRÍTICO"}

SEV_COLOR = {"crítico": COL_FAIL, "critico": COL_FAIL, "alto": COL_WARN,
             "medio": COL_WARN, "bajo": COL_OK}
NIVEL_COLOR = {"alto": COL_OK, "media": COL_WARN, "medio": COL_WARN,
               "baja": COL_MUTED, "bajo": COL_MUTED,
               "alta": COL_FAIL, "máxima": COL_FAIL, "maxima": COL_FAIL,
               "muy baja": COL_OK, "excelente": COL_OK, "bueno": COL_OK,
               "básico": COL_WARN, "basico": COL_WARN, "nulo": COL_FAIL,
               "parcial": COL_WARN, "presente": COL_OK}
ESFUERZO_COLOR = {"bajo": COL_OK, "baja": COL_OK, "medio": COL_WARN,
                  "media": COL_WARN, "alto": COL_FAIL, "alta": COL_FAIL}

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _score_color(score):
    if score >= 80:
        return COL_OK
    if score >= 50:
        return COL_WARN
    return COL_FAIL


def _score_label_auto(p):
    if p >= 85:
        return "Excelente"
    if p >= 70:
        return "Bueno"
    if p >= 50:
        return "Aceptable"
    if p >= 35:
        return "Limitado"
    return "Crítico"


def _fecha_legible(fetched_at):
    try:
        dt = datetime.strptime((fetched_at or "")[:10], "%Y-%m-%d")
        return f"{MESES[dt.month]} {dt.year}"
    except Exception:
        return datetime.now().strftime("%B %Y")


def _hx(c):
    return "#" + c.hexval()[2:]


# --- Coerción defensiva de la salida de la IA (puede venir malformada) ---
def _as_dict(v):
    return v if isinstance(v, dict) else {}


def _as_str(v):
    return v if isinstance(v, str) else ""


def _as_dict_list(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _as_str_list(v):
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, str) and x.strip()]


def _logo_flowable(path, max_w, max_h):
    """Devuelve un Image escalado para caber en max_w x max_h conservando
    la proporción original, o None si el archivo no se puede leer.
    Si `path` es relativo, también se intenta resolver respecto a la carpeta
    del proyecto (útil al desplegar en Linux/Render)."""
    if not path:
        return None
    if not os.path.exists(path):
        alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        if os.path.exists(alt):
            path = alt
        else:
            return None
    try:
        iw, ih = ImageReader(path).getSize()
        ratio = iw / float(ih)
        w, h = max_w, max_w / ratio
        if h > max_h:
            h, w = max_h, max_h * ratio
        return Image(path, width=w, height=h)
    except Exception:
        return None


# ----------------------------------------------------------------------
# Estilos
# ----------------------------------------------------------------------
def _styles(b):
    s = getSampleStyleSheet()
    primary = colors.HexColor(b["primary_color"])

    def add(name, **kw):
        s.add(ParagraphStyle(name=name, **kw))

    add("Eyebrow", parent=s["Normal"], fontSize=8.5, textColor=colors.white,
        leading=11, alignment=TA_LEFT)
    add("CoverTitle", parent=s["Title"], fontSize=26, leading=29,
        textColor=colors.white, alignment=TA_LEFT, spaceAfter=0)
    add("CoverMeta", parent=s["Normal"], fontSize=9, leading=13,
        textColor=colors.HexColor("#C9D4E3"))
    add("CoverMetaBig", parent=s["Normal"], fontSize=13, leading=16,
        textColor=colors.white)
    add("H2", parent=s["Heading2"], fontSize=15, leading=18, textColor=primary,
        spaceBefore=14, spaceAfter=2)
    add("H2sub", parent=s["Normal"], fontSize=9.5, leading=13, textColor=COL_MUTED,
        spaceAfter=8)
    add("Body", parent=s["BodyText"], fontSize=9.5, leading=14, textColor=COL_INK)
    add("BodyTight", parent=s["BodyText"], fontSize=9, leading=12.5, textColor=COL_INK)
    add("ScoreHuge", parent=s["Normal"], fontSize=44, leading=46,
        textColor=colors.white, alignment=TA_CENTER)
    add("ScoreUnit", parent=s["Normal"], fontSize=10, leading=12,
        textColor=colors.HexColor("#C9D4E3"), alignment=TA_CENTER)
    add("ScoreLbl", parent=s["Normal"], fontSize=11, leading=13,
        textColor=colors.white, alignment=TA_CENTER)
    add("KpiVal", parent=s["Normal"], fontSize=16, leading=18, textColor=COL_INK)
    add("KpiLbl", parent=s["Normal"], fontSize=7.5, leading=9.5, textColor=COL_MUTED)
    add("Pill", parent=s["Normal"], fontSize=7.5, leading=9, textColor=colors.white,
        alignment=TA_CENTER)
    add("Badge", parent=s["Normal"], fontSize=8, leading=10, textColor=colors.white,
        alignment=TA_CENTER)
    add("Cell", parent=s["Normal"], fontSize=8.5, leading=11.5, textColor=COL_INK)
    add("CellMuted", parent=s["Normal"], fontSize=8, leading=11, textColor=COL_MUTED)
    add("CellHead", parent=s["Normal"], fontSize=7.8, leading=10, textColor=colors.white)
    add("CardTitle", parent=s["Normal"], fontSize=10.5, leading=13, textColor=COL_INK)
    add("CardLabel", parent=s["Normal"], fontSize=7, leading=9, textColor=COL_MUTED)
    add("CardVal", parent=s["Normal"], fontSize=8.5, leading=11, textColor=COL_INK)
    add("CalloutTitle", parent=s["Normal"], fontSize=9.5, leading=12, textColor=colors.white)
    add("CTA", parent=s["BodyText"], fontSize=11, leading=15, textColor=colors.white)
    add("Caption", parent=s["Normal"], fontSize=7.5, textColor=colors.HexColor("#9AA7B4"))
    add("Lead", parent=s["Normal"], fontSize=9.5, leading=14.5, textColor=COL_INK)
    return s


# ----------------------------------------------------------------------
# Componentes reutilizables
# ----------------------------------------------------------------------
def _pill(text, color, styles, width=None):
    t = Table([[Paragraph(text, styles["Pill"])]], colWidths=[width] if width else None)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _nivel_color(valor, mapa=NIVEL_COLOR, default=COL_MUTED):
    return mapa.get((valor or "").strip().lower(), default)


def _section_header(num, titulo, subtitulo, styles, primary, width):
    badge = Table([[Paragraph(f"<b>{num}</b>", styles["ScoreLbl"])]], colWidths=[0.8 * cm],
                  rowHeights=[0.8 * cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    txt = [Paragraph(titulo, styles["H2"])]
    if subtitulo:
        txt.append(Paragraph(subtitulo, styles["H2sub"]))
    row = Table([[badge, txt]], colWidths=[1.1 * cm, width - 1.1 * cm])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return row


def _score_bar(label, score, styles, total_width):
    score = max(0, min(100, int(score or 0)))
    bar_w = total_width - 5.0 * cm
    filled = max(0.05 * cm, bar_w * score / 100.0)
    rest = max(0.0, bar_w - filled)
    color = _score_color(score)
    bar = Table([["", ""]], colWidths=[filled, rest], rowHeights=[0.4 * cm])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E7EBF0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    row = Table([[Paragraph(label, styles["Cell"]), bar,
                  Paragraph(f'<font color="{_hx(color)}"><b>{score}</b></font>/100', styles["Cell"])]],
                colWidths=[3.4 * cm, bar_w, 1.6 * cm])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return row


def _generic_table(headers, rows, col_widths, styles, pill_cols=None, pill_color_fn=None):
    """Tabla genérica con encabezado oscuro y filas alternas.
    pill_cols: índices de columnas que se renderizan como pill coloreada."""
    pill_cols = pill_cols or {}
    head = [Paragraph(f"<b>{h}</b>", styles["CellHead"]) for h in headers]
    data = [head]
    pill_meta = []  # (row_idx, col_idx, color)
    for r in rows:
        cells = []
        for ci, val in enumerate(r):
            if ci in pill_cols:
                color = pill_color_fn(ci, val) if pill_color_fn else COL_MUTED
                cells.append(Paragraph(str(val), styles["Pill"]))
                pill_meta.append((len(data), ci, color))
            else:
                cells.append(Paragraph(str(val), styles["Cell"]))
        data.append(cells)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), COL_DARK),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, COL_BORDER),
        ("BOX", (0, 0), (-1, -1), 0.5, COL_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), COL_LIGHT))
    for ci in pill_cols:
        style.append(("ALIGN", (ci, 1), (ci, -1), "CENTER"))
    for (ri, ci, color) in pill_meta:
        style.append(("BACKGROUND", (ci, ri), (ci, ri), color))
    t.setStyle(TableStyle(style))
    return t


# ----------------------------------------------------------------------
# Diagnóstico técnico (datos MEDIDOS, sin IA)
# ----------------------------------------------------------------------
def _technical_rows(report):
    onpage = report.get("onpage", {})
    sd = report.get("structured_data", {})
    geo = report.get("geo_signals", {})
    rows = []

    def add(elem, estado, hallazgo, accion):
        prioridad = {"ok": "—", "warn": "Media", "fail": "Alta"}[estado]
        rows.append([elem, ESTADO_LABEL[estado], hallazgo, accion, prioridad, estado])

    tl = onpage.get("title_length", 0)
    add("HTTPS / SSL", "ok" if report.get("https") else "fail",
        "Activo y funcional" if report.get("https") else "El sitio no usa HTTPS",
        "Mantener activo" if report.get("https") else "Migrar a HTTPS de inmediato")
    add("Title homepage", "ok" if (onpage.get("title") and 10 <= tl <= 60) else "warn",
        f'"{(onpage.get("title") or "—")[:48]}" ({tl} car.)',
        "Mantener" if (onpage.get("title") and 10 <= tl <= 60)
        else "Incluir keyword principal, 50-60 caracteres")
    add("H1 homepage", "ok" if onpage.get("h1_count") == 1 else "warn",
        f"{onpage.get('h1_count', 0)} H1 detectados",
        "Mantener un H1 con keyword" if onpage.get("h1_count") == 1
        else "Usar un único H1 con la keyword principal")
    add("Meta description", "ok" if onpage.get("meta_description") else "warn",
        f"{onpage.get('meta_description_length', 0)} caracteres" if onpage.get("meta_description") else "Ausente",
        "Añadir CTA y diferenciador" if onpage.get("meta_description")
        else "Redactar meta description de 50-160 car. con CTA")
    og = onpage.get("open_graph_tags") or {}
    add("Open Graph", "ok" if og else "warn",
        f"{len(og)} etiquetas og:" if og else "Sin Open Graph",
        "Mantener actualizado" if og else "Añadir og:title, og:description, og:image")
    add("Schema markup", "ok" if sd.get("jsonld_present") else "fail",
        ", ".join(sd.get("types_found", [])[:5]) or "Sin datos estructurados",
        "Mantener y ampliar (FAQPage)" if sd.get("jsonld_present")
        else "Implementar JSON-LD: Organization + Service")
    add("Sitemap XML", "ok" if report.get("sitemap", {}).get("exists") else "fail",
        "Encontrado" if report.get("sitemap", {}).get("exists") else "No encontrado",
        "Mantener y enviar a Search Console" if report.get("sitemap", {}).get("exists")
        else "Crear sitemap.xml y enviarlo a GSC")
    add("robots.txt", "ok" if report.get("robots_txt", {}).get("exists") else "warn",
        "Presente" if report.get("robots_txt", {}).get("exists") else "No encontrado",
        "Revisar acceso de bots de IA" if report.get("robots_txt", {}).get("exists")
        else "Crear robots.txt en la raíz")
    add("Canonical / URL", "ok" if onpage.get("canonical") else "warn",
        "Canónica definida" if onpage.get("canonical") else "Sin canonical",
        "Mantener" if onpage.get("canonical") else "Definir URL canónica")
    add("Mobile (viewport)", "ok" if onpage.get("viewport_present") else "fail",
        "Responsive" if onpage.get("viewport_present") else "Sin viewport",
        "Mantener" if onpage.get("viewport_present") else "Añadir meta viewport")
    blocked = geo.get("ai_bots_explicitly_blocked", [])
    add("Acceso de bots IA", "ok" if not blocked else "fail",
        "Permitido" if not blocked else f"Bloquea: {', '.join(blocked)}",
        "Mantener acceso abierto" if not blocked else "Permitir GPTBot/ClaudeBot/PerplexityBot")
    add("llms.txt", "ok" if geo.get("llms_txt_present") else "warn",
        "Presente" if geo.get("llms_txt_present") else "Ausente",
        "Mantener" if geo.get("llms_txt_present") else "Crear llms.txt (resumen del sitio)")
    add("Imágenes con alt", "ok" if onpage.get("images_missing_alt", 0) == 0 else "warn",
        f"{onpage.get('images_missing_alt', 0)} de {onpage.get('images_total', 0)} sin alt",
        "Mantener" if onpage.get("images_missing_alt", 0) == 0 else "Añadir texto alternativo descriptivo")
    rt = report.get("response_time_seconds", 99)
    add("Velocidad respuesta", "ok" if rt < 1.5 else "warn",
        f"{rt} s", "Mantener" if rt < 1.5 else "Optimizar caché/CDN e imágenes")
    return rows


# ----------------------------------------------------------------------
# Pie de página
# ----------------------------------------------------------------------
def _make_footer(b):
    company = b["company_name"]

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(COL_MUTED)
        canvas.drawString(1.5 * cm, 0.9 * cm,
                          f"{company} · Diagnóstico SEO + GEO Premium · Confidencial")
        canvas.drawRightString(letter[0] - 1.5 * cm, 0.9 * cm, f"Página {doc.page}")
        canvas.setStrokeColor(COL_BORDER)
        canvas.line(1.5 * cm, 1.2 * cm, letter[0] - 1.5 * cm, 1.2 * cm)
        canvas.restoreState()

    return _footer


# ----------------------------------------------------------------------
# Documento principal
# ----------------------------------------------------------------------
def generate_pdf(report, lead, output_path, branding=None):
    b = dict(DEFAULT_BRANDING)
    if branding:
        b.update(branding)
    styles = _styles(b)
    primary = colors.HexColor(b["primary_color"])
    W = letter[0] - 3.0 * cm  # ancho útil

    scores = report.get("scores", {})
    promedio = scores.get("promedio_general", 0)
    ai = report.get("ai_summary") or {}
    if isinstance(ai, str):
        ai = {"resumen_ejecutivo": {"situacion_actual": ai}}
    if not isinstance(ai, dict):
        ai = {}
    # Normalizar tipos para tolerar cualquier forma que devuelva el LLM
    _re = ai.get("resumen_ejecutivo")
    ai = {
        "negocio": _as_dict(ai.get("negocio")),
        "score_label": _as_str(ai.get("score_label")),
        "potencial": _as_str(ai.get("potencial")),
        "badges": _as_str_list(ai.get("badges")),
        "kpis_destacados": _as_dict_list(ai.get("kpis_destacados")),
        "resumen_ejecutivo": _re if isinstance(_re, (dict, str)) else {},
        "lo_que_funciona": _as_str(ai.get("lo_que_funciona")),
        "lo_que_frena": _as_str(ai.get("lo_que_frena")),
        "problemas_criticos": _as_dict_list(ai.get("problemas_criticos")),
        "quick_wins": _as_dict_list(ai.get("quick_wins")),
        "geo": _as_dict(ai.get("geo")),
        "competidores": _as_dict_list(ai.get("competidores")),
        "keywords": _as_dict_list(ai.get("keywords")),
        "roadmap": _as_dict_list(ai.get("roadmap")),
        "kpis_6_meses": _as_dict_list(ai.get("kpis_6_meses")),
        "proximos_pasos": _as_dict_list(ai.get("proximos_pasos")),
        "conclusion": _as_str(ai.get("conclusion")),
        "veredicto": _as_str(ai.get("veredicto")),
    }
    negocio = ai.get("negocio") or {}

    story = []

    # =================================================================
    # PORTADA
    # =================================================================
    eyebrow = Paragraph(
        f"{b['company_name'].upper()} · DIAGNÓSTICO SEO + GEO PREMIUM", styles["Eyebrow"])
    titulo = Paragraph("Informe de crecimiento orgánico<br/>+ presencia en IA", styles["CoverTitle"])

    descriptor = negocio.get("descriptor") or ""
    if not descriptor and negocio:
        partes = [negocio.get("sector"), negocio.get("ubicacion"), negocio.get("modelo")]
        descriptor = " · ".join(p for p in partes if p)
    meta_block = [
        Paragraph("FECHA DE ANÁLISIS", styles["CoverMeta"]),
        Paragraph(_fecha_legible(report.get("fetched_at")), styles["CoverMetaBig"]),
        Spacer(1, 0.2 * cm),
        Paragraph("DOMINIO ANALIZADO", styles["CoverMeta"]),
        Paragraph(f"<b>{report.get('domain')}</b>", styles["CoverMetaBig"]),
    ]
    if descriptor:
        meta_block.append(Spacer(1, 0.1 * cm))
        meta_block.append(Paragraph(descriptor, styles["CoverMeta"]))
    if lead and lead.get("nombre"):
        meta_block.append(Spacer(1, 0.1 * cm))
        prep = f"Preparado para: {lead['nombre']}"
        if lead.get("empresa"):
            prep += f" — {lead['empresa']}"
        meta_block.append(Paragraph(prep, styles["CoverMeta"]))

    score_col = _score_color(promedio)
    score_label = ai.get("score_label") or _score_label_auto(promedio)
    badge_inner = Table(
        [[Paragraph(f"<b>{promedio}</b>", styles["ScoreHuge"])],
         [Paragraph("/ 100", styles["ScoreUnit"])],
         [Paragraph("Score SEO + GEO", styles["ScoreUnit"])],
         [Paragraph(f"<b>{score_label}</b>", styles["ScoreLbl"])]],
        colWidths=[4.4 * cm])
    badge_inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 2), score_col),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#00000022")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 10), ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
        ("TOPPADDING", (0, 3), (-1, 3), 6), ("BOTTOMPADDING", (0, 3), (-1, 3), 6),
    ]))

    left_col = []
    logo = _logo_flowable(b.get("logo_path"), 4.6 * cm, 1.8 * cm)
    if logo:
        left_col += [logo, Spacer(1, 0.3 * cm)]
    left_col += [eyebrow, Spacer(1, 0.25 * cm), titulo, Spacer(1, 0.4 * cm)] + meta_block

    cover = Table([[left_col, badge_inner]],
                  colWidths=[W - 5.2 * cm, 5.2 * cm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 18), ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 20), ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(cover)
    story.append(Spacer(1, 0.35 * cm))

    # Badges
    badges = ai.get("badges") or []
    if badges:
        neg_words = ("sin", "limitad", "nulo", "crític", "critic", "bajo", "ausente", "débil", "debil")
        cells, widths = [], []
        for bd in badges[:6]:
            color = COL_WARN if any(w in bd.lower() for w in neg_words) else COL_DARK
            cells.append(_pill(bd, color, styles))
            widths.append((W - 0.8 * cm) / min(len(badges[:6]), 6))
        brow = Table([cells], colWidths=widths)
        brow.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        story.append(brow)
        story.append(Spacer(1, 0.35 * cm))

    # KPIs destacados
    kpis = ai.get("kpis_destacados") or []
    if kpis:
        cards = []
        for k in kpis[:8]:
            est = (k.get("estado") or "warn").lower()
            col = ESTADO_COLOR.get(est, COL_MUTED)
            valor = k.get("valor", "—")
            if isinstance(valor, bool):
                valor = "Sí" if valor else "No"
            elif str(valor).strip().lower() in ("true", "false"):
                valor = "Sí" if str(valor).strip().lower() == "true" else "No"
            cell = Table([[Paragraph(f'<font color="{_hx(col)}"><b>{valor}</b></font>', styles["KpiVal"])],
                          [Paragraph(k.get("etiqueta", ""), styles["KpiLbl"])]],
                         colWidths=[(W - 0.9 * cm) / 4])
            cell.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, COL_BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 2, col),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (0, 0), 6), ("BOTTOMPADDING", (0, 1), (0, 1), 6),
            ]))
            cards.append(cell)
        # filas de 4
        for i in range(0, len(cards), 4):
            fila = cards[i:i + 4]
            while len(fila) < 4:
                fila.append("")
            grid = Table([fila], colWidths=[(W - 0.9 * cm) / 4] * 4)
            grid.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                      ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                                      ("TOPPADDING", (0, 0), (-1, -1), 0),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                                      ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(grid)
        story.append(Spacer(1, 0.3 * cm))

    # Resumen ejecutivo
    re_ = ai.get("resumen_ejecutivo") or {}
    if isinstance(re_, str):
        re_ = {"situacion_actual": re_}
    if any(re_.values()):
        story.append(Paragraph("Resumen ejecutivo", styles["H2"]))
        story.append(Paragraph("Para el director o dueño del negocio", styles["H2sub"]))
        for etiqueta, clave in [("Situación actual", "situacion_actual"),
                                ("Oportunidad principal", "oportunidad_principal"),
                                ("Proyección a 6 meses", "proyeccion_6_meses")]:
            if re_.get(clave):
                story.append(Paragraph(f'<b><font color="{_hx(primary)}">{etiqueta} — </font></b>{re_[clave]}',
                                       styles["Lead"]))
                story.append(Spacer(1, 0.12 * cm))

    # Diagnóstico por área (MEDIDO)
    story.append(Paragraph("Estado general por área", styles["H2"]))
    story.append(Paragraph("Puntajes medidos por el motor de análisis (0-100).", styles["H2sub"]))
    story.append(_score_bar("SEO técnico", scores.get("seo_tecnico", 0), styles, W))
    story.append(_score_bar("GEO / visibilidad en IA", scores.get("geo", 0), styles, W))
    story.append(_score_bar("Contenido", scores.get("contenido", 0), styles, W))
    story.append(Spacer(1, 0.25 * cm))

    # Lo que funciona / frena
    lf, lq = ai.get("lo_que_funciona"), ai.get("lo_que_frena")
    if lf or lq:
        col1 = Table([[Paragraph("LO QUE FUNCIONA", styles["CalloutTitle"])],
                      [Paragraph(lf or "—", styles["BodyTight"])]], colWidths=[(W - 0.4 * cm) / 2])
        col1.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COL_OK), ("BACKGROUND", (0, 1), (-1, 1), COL_LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        col2 = Table([[Paragraph("LO QUE FRENA TODO", styles["CalloutTitle"])],
                      [Paragraph(lq or "—", styles["BodyTight"])]], colWidths=[(W - 0.4 * cm) / 2])
        col2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COL_FAIL), ("BACKGROUND", (0, 1), (-1, 1), COL_LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        twocol = Table([[col1, col2]], colWidths=[(W - 0.4 * cm) / 2 + 0.2 * cm] * 2)
        twocol.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (0, 0), 8),
                                    ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(Spacer(1, 0.15 * cm))
        story.append(twocol)

    # =================================================================
    # 2 · PROBLEMAS CRÍTICOS
    # =================================================================
    problemas = ai.get("problemas_criticos") or []
    if problemas:
        story.append(PageBreak())
        story.append(_section_header("2", "Problemas críticos",
                                     "Acción inmediata requerida", styles, primary, W))
        story.append(Spacer(1, 0.2 * cm))
        for p in problemas[:6]:
            sev = (p.get("severidad") or "Alto")
            sev_col = SEV_COLOR.get(sev.lower(), COL_WARN)
            top = Table([[Paragraph(f"<b>{p.get('titulo','')}</b>", styles["CardTitle"]),
                          _pill(sev.upper(), sev_col, styles, 2.0 * cm)]],
                        colWidths=[W - 2.2 * cm, 2.0 * cm])
            top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            cuerpo = [top, Spacer(1, 0.1 * cm)]
            if p.get("impacto_negocio"):
                cuerpo.append(Paragraph(f"<b>Impacto en negocio:</b> {p['impacto_negocio']}", styles["BodyTight"]))
            if p.get("solucion"):
                cuerpo.append(Paragraph(f"<b>Solución:</b> {p['solucion']}", styles["BodyTight"]))
            # fila inferior: dificultad / resultado / prioridad
            def minicol(lbl, val, color=COL_INK):
                return Table([[Paragraph(lbl, styles["CardLabel"])],
                              [Paragraph(f'<font color="{_hx(color)}"><b>{val}</b></font>', styles["CardVal"])]],
                             colWidths=[(W - 0.6 * cm) / 3])
            mc = Table([[minicol("DIFICULTAD", p.get("dificultad", "—")),
                         minicol("RESULTADO ESPERADO", p.get("resultado_esperado", "—"), COL_OK),
                         minicol("PRIORIDAD", p.get("prioridad", "—"), sev_col)]],
                       colWidths=[(W - 0.6 * cm) / 3] * 3)
            mc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("TOPPADDING", (0, 0), (-1, -1), 4)]))
            cuerpo.append(Spacer(1, 0.05 * cm))
            cuerpo.append(mc)
            card = Table([[cuerpo]], colWidths=[W])
            card.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, COL_BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3, sev_col),
                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
            story.append(KeepTogether(card))
            story.append(Spacer(1, 0.2 * cm))

    # =================================================================
    # 3 · QUICK WINS + GEO
    # =================================================================
    quick = ai.get("quick_wins") or []
    geo_ai = ai.get("geo") or {}
    if quick or geo_ai:
        story.append(PageBreak())
    if quick:
        story.append(_section_header("3", "Quick wins",
                                     "Impacto en menos de 30 días", styles, primary, W))
        story.append(Spacer(1, 0.2 * cm))
        qcards = []
        for i, q in enumerate(quick[:6], 1):
            imp = (q.get("impacto") or "Medio")
            cuerpo = [
                Paragraph(f'<font color="{_hx(primary)}"><b>{i}. {q.get("titulo","")}</b></font>', styles["CardVal"]),
                Paragraph(q.get("descripcion", ""), styles["CellMuted"]),
            ]
            if q.get("resultado"):
                cuerpo.append(Paragraph(f'<font color="{_hx(COL_OK)}">»{q["resultado"]}</font>', styles["CellMuted"]))
            cuerpo.append(Spacer(1, 0.05 * cm))
            cuerpo.append(Table([[_pill(f"{imp} impacto", _nivel_color(imp), styles),
                                  _pill(f"Esfuerzo: {q.get('esfuerzo','—')}", COL_DARK, styles)]],
                                colWidths=[2.6 * cm, 3.0 * cm],
                                style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                                  ("RIGHTPADDING", (0, 0), (0, 0), 4)])))
            cell = Table([[cuerpo]], colWidths=[(W - 0.4 * cm) / 2])
            cell.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, COL_BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            qcards.append(cell)
        for i in range(0, len(qcards), 2):
            fila = qcards[i:i + 2]
            while len(fila) < 2:
                fila.append("")
            grid = Table([fila], colWidths=[(W - 0.4 * cm) / 2 + 0.2 * cm] * 2)
            grid.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                      ("RIGHTPADDING", (0, 0), (0, 0), 8),
                                      ("TOPPADDING", (0, 0), (-1, -1), 0),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                                      ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(grid)

    if geo_ai:
        story.append(Spacer(1, 0.2 * cm))
        story.append(_section_header("4", "Diagnóstico GEO",
                                     "Visibilidad en ChatGPT · Gemini · Perplexity", styles, primary, W))
        story.append(Spacer(1, 0.15 * cm))
        if geo_ai.get("que_es"):
            story.append(Paragraph(f"<b>¿Qué es GEO y por qué importa?</b> {geo_ai['que_es']}", styles["Body"]))
            story.append(Spacer(1, 0.1 * cm))
        if geo_ai.get("estado_actual"):
            story.append(Paragraph(f"<b>Estado actual:</b> {geo_ai['estado_actual']}", styles["Body"]))
            story.append(Spacer(1, 0.1 * cm))
        nec = geo_ai.get("que_necesita")
        nec = nec if isinstance(nec, list) else []
        if nec:
            story.append(Paragraph("<b>Qué necesita el sitio para aparecer en IAs:</b>", styles["Body"]))
            for n in nec:
                story.append(Paragraph(f'• {n}', styles["BodyTight"]))

    # =================================================================
    # 5 · DIAGNÓSTICO TÉCNICO (MEDIDO)
    # =================================================================
    story.append(PageBreak())
    story.append(_section_header("5", "Diagnóstico técnico",
                                 "Verificado directamente sobre el sitio", styles, primary, W))
    story.append(Spacer(1, 0.2 * cm))
    rows = _technical_rows(report)
    table_rows = [[r[0], r[1], r[2], r[3], r[4]] for r in rows]
    prio_color = {"—": COL_MUTED, "media": COL_WARN, "alta": COL_FAIL}
    est_map = {"OK": COL_OK, "MEJORAR": COL_WARN, "CRÍTICO": COL_FAIL}

    def _pcolor(ci, val):
        v = str(val).strip()
        if ci == 1:  # estado
            return est_map.get(v, COL_MUTED)
        if ci == 4:  # prioridad
            return prio_color.get(v.lower(), COL_MUTED)
        return COL_MUTED

    story.append(_generic_table(
        ["ELEMENTO", "ESTADO", "HALLAZGO ESPECÍFICO", "ACCIÓN RECOMENDADA", "PRIOR."],
        table_rows, [2.7 * cm, 1.7 * cm, 5.0 * cm, 5.3 * cm, 1.6 * cm],
        styles, pill_cols={1, 4}, pill_color_fn=_pcolor))

    # =================================================================
    # 6 · COMPETIDORES + KEYWORDS
    # =================================================================
    comps = ai.get("competidores") or []
    kws = ai.get("keywords") or []
    if comps or kws:
        story.append(PageBreak())
    if comps:
        story.append(_section_header("6", "Análisis competitivo",
                                     "Estimación experta del panorama digital del sector", styles, primary, W))
        story.append(Spacer(1, 0.2 * cm))
        crows = [[c.get("dominio", "—"), c.get("especializacion", "—"),
                  c.get("visibilidad", "—"), c.get("seo", "—"), c.get("geo", "—")] for c in comps[:6]]

        def _ccolor(ci, val):
            return _nivel_color(val)
        story.append(_generic_table(
            ["DOMINIO", "ESPECIALIZACIÓN", "VISIBILIDAD", "SEO", "GEO"],
            crows, [4.2 * cm, 5.0 * cm, 3.0 * cm, 1.9 * cm, 2.2 * cm],
            styles, pill_cols={3, 4}, pill_color_fn=_ccolor))
        story.append(Paragraph("Datos de competencia estimados por IA (no medidos con herramientas de pago).",
                               styles["Caption"]))
    if kws:
        story.append(Spacer(1, 0.3 * cm))
        story.append(_section_header("7", "Oportunidades de keywords",
                                     "Temas con mayor potencial de posicionamiento", styles, primary, W))
        story.append(Spacer(1, 0.2 * cm))
        krows = [[k.get("keyword", "—"), k.get("intencion", "—"), k.get("volumen", "—"),
                  k.get("competencia", "—"), k.get("tipo_pagina", "—"), k.get("prioridad", "—")] for k in kws[:9]]

        def _kcolor(ci, val):
            return _nivel_color(val)
        story.append(_generic_table(
            ["KEYWORD / TEMA", "INTENCIÓN", "VOLUMEN", "COMPETENCIA", "TIPO PÁGINA", "PRIOR."],
            krows, [4.4 * cm, 2.7 * cm, 2.3 * cm, 2.3 * cm, 2.6 * cm, 1.6 * cm],
            styles, pill_cols={5}, pill_color_fn=_kcolor))
        story.append(Paragraph("Volúmenes y competencia estimados por IA.", styles["Caption"]))

    # =================================================================
    # 8 · ROADMAP + KPIs + PRÓXIMOS PASOS
    # =================================================================
    roadmap = ai.get("roadmap") or []
    kpis6 = ai.get("kpis_6_meses") or []
    pasos = ai.get("proximos_pasos") or []
    if roadmap or kpis6 or pasos:
        story.append(PageBreak())
    if roadmap:
        story.append(_section_header("8", "Roadmap de implementación",
                                     "Plan 30 / 60 / 90 días", styles, primary, W))
        story.append(Spacer(1, 0.2 * cm))
        for fase in roadmap[:4]:
            items = fase.get("items")
            items = items if isinstance(items, list) else []
            cuerpo = [Paragraph(f"<b>{fase.get('fase','')}</b>", styles["CalloutTitle"])]
            inner = [Paragraph(f'• {it}', styles["BodyTight"]) for it in items]
            head = Table([[cuerpo[0]]], colWidths=[W])
            head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), primary),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                      ("TOPPADDING", (0, 0), (-1, -1), 4),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            body = Table([[inner]], colWidths=[W])
            body.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), COL_LIGHT),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                      ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                      ("TOPPADDING", (0, 0), (-1, -1), 6),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            blk = [head, body]
            if fase.get("resultado"):
                res = Table([[Paragraph(f'»{fase["resultado"]}', styles["CellMuted"])]], colWidths=[W])
                res.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 10),
                                         ("TOPPADDING", (0, 0), (-1, -1), 3),
                                         ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
                blk.append(res)
            story.append(KeepTogether(blk))
            story.append(Spacer(1, 0.18 * cm))

    if kpis6:
        story.append(Spacer(1, 0.1 * cm))
        story.append(_section_header("9", "KPIs y metas a 6 meses", "", styles, primary, W))
        story.append(Spacer(1, 0.15 * cm))
        krows = [[k.get("metrica", "—"), k.get("hoy", "—"), k.get("meta", "—")] for k in kpis6[:6]]
        story.append(_generic_table(["MÉTRICA", "HOY", "META A 6 MESES"],
                                    krows, [6.0 * cm, 5.2 * cm, 5.4 * cm], styles))

    if pasos:
        story.append(Spacer(1, 0.3 * cm))
        story.append(_section_header("10", "Próximos pasos acordados", "", styles, primary, W))
        story.append(Spacer(1, 0.15 * cm))
        prows = [[str(i), p.get("accion", "—"), p.get("responsable", "—"),
                  p.get("plazo", "—"), p.get("estado", "Pendiente")]
                 for i, p in enumerate(pasos[:10], 1)]
        story.append(_generic_table(["#", "ACCIÓN", "RESPONSABLE", "PLAZO", "ESTADO"],
                                    prows, [0.8 * cm, 8.6 * cm, 3.0 * cm, 2.2 * cm, 2.0 * cm], styles))

    # =================================================================
    # CONCLUSIÓN + CTA
    # =================================================================
    conclusion = ai.get("conclusion")
    story.append(PageBreak())
    if conclusion:
        story.append(_section_header("11", "Conclusión ejecutiva", b["company_name"], styles, primary, W))
        story.append(Spacer(1, 0.2 * cm))
        for parr in (conclusion.split("\n") if isinstance(conclusion, str) else []):
            if parr.strip():
                story.append(Paragraph(parr.strip(), styles["Body"]))
                story.append(Spacer(1, 0.12 * cm))

    story.append(Spacer(1, 0.3 * cm))
    cta = Table([[Paragraph(b["cta_text"] + f'<br/><br/><b>{b["cta_url"]}</b> &nbsp;|&nbsp; {b["contact_email"]}',
                            styles["CTA"])]], colWidths=[W])
    cta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14)]))
    story.append(KeepTogether(cta))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(
        f"Informe generado por {b['company_name']} · {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        f"Datos técnicos medidos automáticamente; análisis estratégico asistido por IA.",
        styles["Caption"]))

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=1.5 * cm, bottomMargin=1.6 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=f"Diagnóstico SEO + GEO Premium - {report.get('domain')}",
        author=b["company_name"])
    footer = _make_footer(b)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output_path
