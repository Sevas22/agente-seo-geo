# -*- coding: utf-8 -*-
"""
ai_summary.py
--------------
Genera un resumen ejecutivo personalizado a partir de los datos del
diagnóstico SEO/GEO, usando Groq (por defecto) o Anthropic.

Es completamente OPCIONAL: si no hay API key configurada o el proveedor
falla, simplemente no se genera y el informe se produce igual, sin esa
sección extra (igual que el correo SMTP).

Variables de entorno relevantes:
    ENABLE_AI_SUMMARY=true|false   (por defecto false)
    AI_PROVIDER=groq|anthropic     (por defecto groq)

    # Si AI_PROVIDER=groq
    GROQ_API_KEY=gsk_...
    AI_MODEL=llama-3.3-70b-versatile   (por defecto)

    # Si AI_PROVIDER=anthropic
    ANTHROPIC_API_KEY=sk-ant-...
    AI_MODEL=claude-haiku-4-5-20251001 (por defecto)
"""

import json
import os

DEFAULT_MODEL_GROQ = "llama-3.3-70b-versatile"
DEFAULT_MODEL_ANTHROPIC = "claude-haiku-4-5-20251001"

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

PROMPT_TEMPLATE = """Eres un consultor SEO senior. A continuación tienes los resultados de un \
diagnóstico técnico automatizado de SEO y GEO (visibilidad en buscadores de \
IA generativa como ChatGPT, Gemini o Perplexity) del sitio "{dominio}", \
perteneciente a {empresa}.

Datos del análisis (formato JSON):
{datos}

Escribe un RESUMEN EJECUTIVO en español, en tono profesional pero cercano, \
dirigido al dueño del negocio (no es un experto técnico). Debe incluir:

1. Un párrafo inicial con una valoración general honesta del estado del sitio.
2. Las 3 prioridades más importantes a resolver, explicadas en lenguaje \
sencillo y conectadas con el impacto de negocio (por ejemplo: "esto afecta \
a que tus clientes te encuentren en Google y en herramientas como ChatGPT").
3. Un cierre breve y motivador que invite a solicitar ayuda profesional para \
implementar las mejoras.

Máximo 280 palabras. Escribe solo párrafos de texto corrido, sin listas con \
viñetas ni formato markdown (el resultado se insertará directamente en un \
PDF)."""


def _build_context(report, scores, recommendations, lead):
    return {
        "dominio": report.get("domain"),
        "puntajes": scores,
        "https": report.get("https"),
        "onpage": report.get("onpage"),
        "robots_txt": report.get("robots_txt"),
        "llms_txt": report.get("llms_txt"),
        "geo_signals": report.get("geo_signals"),
        "structured_data": report.get("structured_data"),
        "content": {
            "word_count": (report.get("content") or {}).get("word_count"),
            "top_keywords": (report.get("content") or {}).get("top_keywords", [])[:10],
        },
        "recomendaciones_tecnicas": recommendations,
    }


def _generar_con_groq(prompt):
    """Llama a la API de Groq (compatible con OpenAI). Devuelve texto o None."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[ai_summary] AI_PROVIDER=groq pero falta GROQ_API_KEY.")
        return None

    try:
        import requests
    except ImportError:
        print("[ai_summary] El paquete 'requests' no esta instalado.")
        return None

    model = os.environ.get("AI_MODEL", DEFAULT_MODEL_GROQ)

    resp = requests.post(
        GROQ_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 900,
            "temperature": 0.6,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    texto = (data["choices"][0]["message"]["content"] or "").strip()
    return texto or None


def _generar_con_anthropic(prompt):
    """Llama a la API de Anthropic. Devuelve texto o None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ai_summary] AI_PROVIDER=anthropic pero falta ANTHROPIC_API_KEY.")
        return None

    try:
        import anthropic
    except ImportError:
        print("[ai_summary] El paquete 'anthropic' no esta instalado "
              "(agrega 'anthropic' a requirements.txt y reinstala).")
        return None

    model = os.environ.get("AI_MODEL", DEFAULT_MODEL_ANTHROPIC)
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    texto = "".join(
        block.text for block in message.content
        if getattr(block, "type", "") == "text"
    ).strip()
    return texto or None


def generar_resumen_ia(report, scores, recommendations, lead):
    """
    Devuelve un texto (str) con el resumen ejecutivo generado por IA, o
    None si la funcion esta desactivada, no hay API key, falta el paquete
    necesario, o ocurre algun error (modo silencioso, no rompe el flujo
    principal de generacion del informe).
    """
    if os.environ.get("ENABLE_AI_SUMMARY", "false").lower() != "true":
        return None

    provider = os.environ.get("AI_PROVIDER", "groq").strip().lower()

    contexto = _build_context(report, scores, recommendations, lead)
    prompt = PROMPT_TEMPLATE.format(
        dominio=contexto["dominio"],
        empresa=lead.get("empresa") or "esta empresa",
        datos=json.dumps(contexto, ensure_ascii=False, indent=2, default=str),
    )

    try:
        if provider == "anthropic":
            return _generar_con_anthropic(prompt)
        if provider == "groq":
            return _generar_con_groq(prompt)
        print(f"[ai_summary] AI_PROVIDER desconocido: '{provider}'. Usa 'groq' o 'anthropic'.")
        return None
    except Exception as exc:
        print(f"[ai_summary] Error generando resumen con IA ({provider}): {exc}")
        return None
