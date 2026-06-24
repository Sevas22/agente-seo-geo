# -*- coding: utf-8 -*-
"""
ai_summary.py
--------------
Genera un ANÁLISIS EJECUTIVO ESTRUCTURADO usando una API de IA, a partir
de los datos del diagnóstico SEO/GEO.

Soporta varios proveedores (se elige con AI_PROVIDER):
    - gemini     -> Google Gemini (tiene nivel GRATUITO, recomendado para MVP)
    - groq       -> Groq / Llama (también gratis)
    - anthropic  -> Claude (de pago, mayor calidad)

Devuelve un diccionario con:
    - veredicto:          una frase de valoración general
    - resumen_ejecutivo:  2-3 párrafos dirigidos al dueño del negocio
    - prioridades:        lista de {titulo, explicacion, impacto_negocio}
    - plan_accion:        lista de {accion, area, impacto, esfuerzo}

Es completamente OPCIONAL: si no hay key (o falla la llamada), devuelve
None y el informe se genera igual, sin esa sección extra.

Variables de entorno relevantes:
    ENABLE_AI_SUMMARY=true|false   (por defecto false)
    AI_PROVIDER=gemini|groq|anthropic   (por defecto: autodetecta según la key disponible)
    AI_MODEL=...                   (opcional; cada proveedor tiene su modelo por defecto)

    # Según el proveedor:
    GEMINI_API_KEY=...        (https://aistudio.google.com — gratis, sin tarjeta)
    GROQ_API_KEY=...          (https://console.groq.com — gratis)
    ANTHROPIC_API_KEY=sk-ant-...
"""

import json
import os

import requests

# Modelo por defecto para cada proveedor
DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-haiku-4-5-20251001",
}

# El informe premium es extenso y detallado; presupuesto amplio de salida.
MAX_TOKENS = 12000

SYSTEM_PROMPT = (
    "Eres un consultor SEO y GEO (Generative Engine Optimization) senior de una "
    "agencia digital premium, especializado en visibilidad de sitios web tanto en "
    "buscadores tradicionales (Google) como en motores de IA generativa (ChatGPT, "
    "Gemini, Perplexity, Claude). Produces informes ejecutivos EXTENSOS y MUY "
    "DETALLADOS por los que el cliente PAGA: deben sentirse como una consultoría "
    "profesional completa, no como un resumen. Cada hallazgo se explica a fondo "
    "(varias frases), conectándolo con su impacto comercial (visibilidad, leads, "
    "tráfico calificado, autoridad, ingresos). Dirigido al director o dueño del "
    "negocio (NO experto técnico): claro, estratégico y accionable. Infieres el "
    "sector, modelo de negocio y ubicación leyendo el contenido del sitio. Para "
    "datos que no puedes medir (volúmenes de búsqueda, competidores, Domain Rating) "
    "haces ESTIMACIONES razonables de consultor experto, sin afirmar como medido "
    "algo estimado. Nunca repites la misma frase; cada punto aporta valor nuevo y "
    "específico al sector. Evitas relleno genérico."
)

PROMPT_TEMPLATE = """Eres el consultor que redacta un INFORME DE DIAGNÓSTICO SEO + GEO PREMIUM \
para el sitio "{dominio}" (empresa: {empresa}).

Tienes los resultados de un análisis técnico automatizado del sitio:
{datos}

A partir de esos datos —y de tu inferencia experta del sector/negocio leyendo el \
contenido del sitio— redacta el informe completo. Devuelve SOLO un JSON válido \
(sin texto ni markdown alrededor) con EXACTAMENTE esta estructura:

{{
  "negocio": {{
    "nombre": "Nombre del negocio inferido",
    "sector": "Sector/industria inferido (ej: Consultoría energética B2B)",
    "ubicacion": "Ciudad/país inferido o '—' si no se deduce",
    "modelo": "B2B | B2C | Mixto",
    "descriptor": "Una línea que describa el negocio y su mercado"
  }},
  "score_label": "Una palabra del estado global: Crítico | Limitado | Aceptable | Bueno | Excelente",
  "potencial": "Una frase corta sobre el potencial de crecimiento (ej: 'Alto potencial, competencia digital débil').",
  "badges": ["3 a 5 etiquetas muy cortas de estado, ej: 'SEO limitado', 'GEO sin implementar', 'Sector energético'"],
  "kpis_destacados": [
    {{"valor": "Valor corto (ej: 'Nulo', '0%', '2', '~15')", "etiqueta": "Qué mide (ej: 'GEO implementado')", "estado": "ok | warn | fail"}}
  ],
  "resumen_ejecutivo": {{
    "situacion_actual": "Párrafo honesto sobre dónde está el sitio hoy.",
    "oportunidad_principal": "Párrafo sobre la mayor oportunidad de crecimiento.",
    "proyeccion_6_meses": "Párrafo con proyección realista a 6 meses si se ejecuta el plan."
  }},
  "lo_que_funciona": "2-3 frases detallando lo que el sitio ya hace bien (basado en los datos medidos).",
  "lo_que_frena": "2-3 frases sobre lo que está frenando el posicionamiento y por qué importa.",
  "diagnostico_areas": [
    {{"area": "SEO técnico", "score": 0-100, "comentario": "Frase breve del estado del área"}},
    {{"area": "SEO On-Page", "score": 0-100, "comentario": "..."}},
    {{"area": "Contenido", "score": 0-100, "comentario": "..."}},
    {{"area": "Autoridad", "score": 0-100, "comentario": "..."}},
    {{"area": "GEO / IA", "score": 0-100, "comentario": "..."}},
    {{"area": "SEO Local", "score": 0-100, "comentario": "..."}}
  ],
  "problemas_criticos": [
    {{
      "titulo": "Título del problema (específico al sitio)",
      "severidad": "Crítico | Alto | Medio",
      "prioridad": "Prioridad 1 | Prioridad 2 | Prioridad 3",
      "impacto_negocio": "2-3 frases: el efecto comercial concreto (clientes, leads, ventas).",
      "impacto_seo": "1-2 frases: el efecto técnico/SEO estimado (rankings, CTR, indexación).",
      "solucion": "Solución concreta, específica y paso a paso (2-3 frases).",
      "dificultad": "Ej: 'Baja — 5 minutos' / 'Media — 2 meses'",
      "resultado_esperado": "Resultado medible esperado (ej: '+40% CTR en 30 días')"
    }}
  ],
  "quick_wins": [
    {{"titulo": "Acción rápida", "descripcion": "Qué hacer concretamente (2 frases).", "resultado": "Resultado esperado", "impacto": "Alto | Medio | Bajo", "esfuerzo": "Ej: '5 min', '1h', 'bajo'"}}
  ],
  "geo": {{
    "que_es": "2-3 frases explicando GEO y por qué es crítico para ESTE negocio en su sector.",
    "estado_actual": "2-3 frases del estado actual del sitio en IAs generativas, basado en los datos.",
    "pregunta_prueba": "Una pregunta real que un cliente potencial le haría a ChatGPT/Gemini en este sector.",
    "que_citan": "Qué tipo de fuentes citan las IAs (para que el dueño entienda qué falta).",
    "que_necesita": ["4-6 cosas concretas que el sitio necesita para aparecer citado en IAs"]
  }},
  "competidores": [
    {{"dominio": "competidor estimado o 'tú' para el propio sitio", "especializacion": "Su enfoque", "visibilidad": "Baja|Media|Alta", "seo": "Básico|Bueno|Excelente", "geo": "Nulo|Básico|Parcial|Presente"}}
  ],
  "insight_competitivo": "2-3 frases con el insight estratégico clave del panorama competitivo y dónde está la oportunidad.",
  "keywords": [
    {{"keyword": "keyword/tema oportuno", "intencion": "Transaccional|Informacional|Local", "volumen": "Rango estimado/mes (ej: '500–1K/mes')", "competencia": "Muy baja|Baja|Media|Alta", "tipo_pagina": "Homepage|Servicio|Blog|Landing local", "prioridad": "Alta|Media|Baja"}}
  ],
  "matriz": {{
    "ahora": ["Acciones de ALTO impacto y BAJO esfuerzo — hacer ya (3-5)"],
    "mes_2": ["Alto impacto, dificultad media (3-5)"],
    "mes_3": ["Alto impacto, alta dificultad (3-5)"],
    "mes_4_6": ["Consolidación y escala (3-4)"]
  }},
  "roadmap": [
    {{"fase": "Días 1–30 · Fundamentos", "items": ["4-6 acciones concretas"], "resultado": "Resultado esperado de la fase"}},
    {{"fase": "Días 31–60 · Contenido y autoridad", "items": ["4-6 acciones"], "resultado": "..."}},
    {{"fase": "Días 61–90 · GEO, backlinks y liderazgo", "items": ["4-6 acciones"], "resultado": "..."}}
  ],
  "kpis_6_meses": [
    {{"metrica": "Nombre de la métrica", "hoy": "Valor/estado actual", "meta": "Meta a 6 meses"}}
  ],
  "proximos_pasos": [
    {{"accion": "Acción acordada", "responsable": "Agencia | Cliente | Ambos", "plazo": "Ej: 'Semana 1', 'Mes 2'", "estado": "Pendiente"}}
  ],
  "conclusion": "3-4 párrafos de conclusión ejecutiva: situación, oportunidad de mercado, qué los hace únicos y un cierre motivador. Detallada y persuasiva."
}}

Reglas de cantidad y calidad (es un informe PAGO: debe ser EXTENSO y DETALLADO):
- badges: 4-5 · kpis_destacados: 8 · diagnostico_areas: las 6 indicadas · problemas_criticos: 5-7 (ordenados por severidad) · quick_wins: 6-8 · que_necesita: 4-6 · competidores: 5-6 (incluye el propio sitio como 'tú') · keywords: 8-12 · matriz: 3-5 items por bloque · roadmap: 3 fases con 4-6 items cada una · kpis_6_meses: 5-7 · proximos_pasos: 8-12.
- Cada campo de texto debe tener el detalle indicado (varias frases). NADA de respuestas de una línea ni frases genéricas vacías.
- Sé MUY específico al sector y negocio inferido; usa términos reales del sector.
- Los volúmenes de keywords, competidores y métricas son ESTIMACIONES expertas razonables; no inventes precisión falsa.
- Si en los datos viene "backlinks" con disponible=true (enlaces, dominios de referencia, rank), úsalos como DATOS REALES en el análisis de autoridad, competencia y conclusión. Si no está disponible, recomienda construir backlinks pero sin inventar cifras.
- Si viene "reputacion" con reseñas, menciónalas; si faltan, recomienda generar reseñas (Google, Trustpilot).
- Texto en español, sin markdown ni viñetas dentro de los strings.
- Responde ÚNICAMENTE con el JSON, completo y válido."""


def _build_context(report, scores, recommendations, lead):
    onpage = report.get("onpage") or {}
    content = report.get("content") or {}
    return {
        "dominio": report.get("domain"),
        "empresa_declarada": lead.get("empresa") or None,
        "puntajes": scores,
        "https": report.get("https"),
        "tiempo_respuesta_s": report.get("response_time_seconds"),
        "onpage": {
            "title": onpage.get("title"),
            "title_length": onpage.get("title_length"),
            "meta_description": onpage.get("meta_description"),
            "meta_description_length": onpage.get("meta_description_length"),
            "h1_count": onpage.get("h1_count"),
            "headings": onpage.get("headings"),
            "images_total": onpage.get("images_total"),
            "images_missing_alt": onpage.get("images_missing_alt"),
            "word_count": onpage.get("word_count"),
            "viewport_present": onpage.get("viewport_present"),
            "canonical": onpage.get("canonical"),
            "lang": onpage.get("lang"),
        },
        "robots_txt_existe": (report.get("robots_txt") or {}).get("exists"),
        "sitemap_existe": (report.get("sitemap") or {}).get("exists"),
        "llms_txt": report.get("llms_txt"),
        "geo_signals": report.get("geo_signals"),
        "structured_data": report.get("structured_data"),
        "reputacion": report.get("reputacion"),
        "backlinks": report.get("backlinks"),
        "content": {
            "word_count": content.get("word_count"),
            "top_keywords": content.get("top_keywords", [])[:12],
            "vista_previa_texto": content.get("first_paragraph_preview"),
        },
        "recomendaciones_tecnicas": recommendations,
    }


def _parse_json_lenient(texto):
    """Intenta parsear JSON aunque venga con texto/markdown alrededor."""
    if not texto:
        return None
    texto = texto.strip()
    # Quitar fences ```json ... ```
    if texto.startswith("```"):
        texto = texto.split("```", 2)[1] if texto.count("```") >= 2 else texto
        if texto.lstrip().lower().startswith("json"):
            texto = texto.lstrip()[4:]
    try:
        return json.loads(texto)
    except Exception:
        pass
    # Último recurso: extraer el primer bloque {...}
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio:fin + 1])
        except Exception:
            return None
    return None


def _detectar_proveedor():
    """Elige el proveedor según AI_PROVIDER o la primera key disponible."""
    explicit = os.environ.get("AI_PROVIDER", "").strip().lower()
    if explicit in DEFAULT_MODELS:
        return explicit
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def _call_gemini(system, prompt, model):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY (gratis en https://aistudio.google.com).")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": MAX_TOKENS,
                              "responseMimeType": "application/json"},
    }
    resp = requests.post(url, params={"key": api_key}, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        part.get("text", "")
        for part in data["candidates"][0]["content"]["parts"]
    ).strip()


def _call_groq(system, prompt, model):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GROQ_API_KEY (gratis en https://console.groq.com).")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0.5,
            "max_tokens": MAX_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_anthropic(system, prompt, model):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Falta ANTHROPIC_API_KEY.")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("El paquete 'anthropic' no está instalado.") from exc
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in message.content
        if getattr(block, "type", "") == "text"
    ).strip()


_PROVIDERS = {"gemini": _call_gemini, "groq": _call_groq, "anthropic": _call_anthropic}


def generar_resumen_ia(report, scores, recommendations, lead):
    """
    Devuelve un dict con el análisis ejecutivo estructurado generado por IA,
    o None si la función está desactivada, no hay key, o ocurre algún error
    (modo silencioso: nunca rompe el flujo de generación del informe).

    Devuelve la estructura premium completa (ver PROMPT_TEMPLATE): negocio,
    score_label, potencial, badges, kpis_destacados, resumen_ejecutivo,
    lo_que_funciona, lo_que_frena, problemas_criticos, quick_wins, geo,
    competidores, keywords, roadmap, kpis_6_meses, proximos_pasos, conclusion.
    Todos los campos son opcionales: el PDF renderiza solo los presentes.
    """
    if os.environ.get("ENABLE_AI_SUMMARY", "false").lower() != "true":
        return None

    proveedor = _detectar_proveedor()
    if not proveedor:
        print("[ai_summary] ENABLE_AI_SUMMARY=true pero no hay ninguna API key "
              "(GEMINI_API_KEY, GROQ_API_KEY o ANTHROPIC_API_KEY).")
        return None

    model = os.environ.get("AI_MODEL") or DEFAULT_MODELS[proveedor]
    contexto = _build_context(report, scores, recommendations, lead)

    prompt = PROMPT_TEMPLATE.format(
        dominio=contexto["dominio"],
        empresa=lead.get("empresa") or "esta empresa",
        datos=json.dumps(contexto, ensure_ascii=False, indent=2, default=str),
    )

    try:
        texto = _PROVIDERS[proveedor](SYSTEM_PROMPT, prompt, model)
    except Exception as exc:
        print(f"[ai_summary] Error generando análisis con IA ({proveedor}): {exc}")
        return None

    data = _parse_json_lenient(texto)
    if not isinstance(data, dict):
        # Si no se pudo parsear como JSON, usar el texto como resumen plano.
        return {"resumen_ejecutivo": {"situacion_actual": texto}} if texto else None

    # Se devuelve la estructura tal cual; el PDF accede con .get() de forma
    # defensiva, así que campos faltantes simplemente no se renderizan.
    return data
