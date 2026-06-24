#!/usr/bin/env python3
"""
seo_geo_audit.py
-----------------
Genera un diagnóstico automático de SEO técnico, GEO (visibilidad en
motores de IA generativa), contenido/keywords y notas de competencia
para un dominio dado.

Uso:
    python3 seo_geo_audit.py https://www.midominio.com --pagespeed-key TU_API_KEY

Salidas:
    - <dominio>_audit.json   (datos crudos, útiles para integraciones)
    - <dominio>_informe.md   (informe en markdown, listo para convertir a docx/pdf)

Requiere: requests, beautifulsoup4
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 SEO-GEO-Auditor/1.0"
)

# Bots de IA generativa relevantes para GEO
AI_BOTS = [
    "GPTBot",          # OpenAI / ChatGPT
    "OAI-SearchBot",   # OpenAI search
    "ChatGPT-User",
    "Google-Extended", # Gemini / AI Overviews
    "PerplexityBot",
    "Perplexity-User",
    "ClaudeBot",
    "anthropic-ai",
    "Claude-User",
    "CCBot",           # Common Crawl (alimenta muchos LLMs)
    "Applebot-Extended",
    "Bytespider",      # ByteDance / TikTok
    "Amazonbot",
]

STOPWORDS = set("""
de la que el en y a los del se las por un para con no una su al lo como mas
pero sus le ya o este si porque esta entre cuando muy sin sobre tambien me
hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese
eso ante ellos e esto mi antes algunos que sea estos era unos the and for are
with this that from your you our which their will can has have not all more
about into over than then them they were was been being our its
""".split())


VERIFY_SSL = True


def fetch(url, timeout=15, allow_redirects=True):
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=VERIFY_SSL,
        )
        return resp
    except requests.RequestException as exc:
        return exc


def normalize_domain(domain):
    if not domain.startswith("http://") and not domain.startswith("https://"):
        domain = "https://" + domain
    parsed = urlparse(domain)
    return f"{parsed.scheme}://{parsed.netloc}", parsed.netloc


def check_robots_txt(base_url):
    result = {"exists": False, "url": urljoin(base_url, "/robots.txt"),
              "ai_bots_blocked": [], "ai_bots_allowed": [], "sitemap_refs": [],
              "raw_excerpt": ""}
    resp = fetch(result["url"])
    if isinstance(resp, Exception) or resp.status_code != 200:
        return result

    result["exists"] = True
    text = resp.text
    result["raw_excerpt"] = text[:1500]

    # Sitemaps referenciados
    result["sitemap_refs"] = re.findall(r"(?im)^sitemap:\s*(\S+)", text)

    # Analizar bloques User-agent -> Disallow para bots de IA
    blocks = re.split(r"(?im)^user-agent:", text)
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        agent = lines[0].strip()
        disallow_all = any(
            re.match(r"(?i)disallow:\s*/\s*$", l.strip()) for l in lines[1:]
        )
        for bot in AI_BOTS:
            if bot.lower() == agent.lower():
                if disallow_all:
                    result["ai_bots_blocked"].append(bot)
                else:
                    result["ai_bots_allowed"].append(bot)
    return result


def check_llms_txt(base_url):
    url = urljoin(base_url, "/llms.txt")
    resp = fetch(url)
    exists = (not isinstance(resp, Exception)) and resp.status_code == 200
    return {"exists": exists, "url": url}


def check_sitemap(base_url, robots_info):
    candidates = list(robots_info.get("sitemap_refs", []))
    candidates.append(urljoin(base_url, "/sitemap.xml"))
    for url in candidates:
        resp = fetch(url)
        if not isinstance(resp, Exception) and resp.status_code == 200:
            return {"exists": True, "url": url}
    return {"exists": False, "url": candidates[-1]}


def extract_jsonld_types(soup):
    types = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                t = item.get("@type")
                if isinstance(t, list):
                    types.extend(t)
                elif t:
                    types.append(t)
                # @graph
                for g in item.get("@graph", []) if isinstance(item.get("@graph"), list) else []:
                    if isinstance(g, dict) and g.get("@type"):
                        gt = g["@type"]
                        types.extend(gt if isinstance(gt, list) else [gt])
    return types


def word_freq(text, top_n=15):
    words = re.findall(r"[a-záéíóúñü]{4,}", text.lower())
    words = [w for w in words if w not in STOPWORDS]
    return Counter(words).most_common(top_n)


def pagespeed_scores(url, api_key=None):
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    out = {}
    for strategy in ("mobile", "desktop"):
        params = {"url": url, "strategy": strategy, "category": ["performance", "seo", "accessibility", "best-practices"]}
        if api_key:
            params["key"] = api_key
        try:
            resp = requests.get(endpoint, params=params, timeout=60)
            data = resp.json()
            cats = data.get("lighthouseResult", {}).get("categories", {})
            out[strategy] = {k: round(v["score"] * 100) for k, v in cats.items() if v.get("score") is not None}
            cwv = data.get("loadingExperience", {}).get("metrics", {})
            out[strategy]["core_web_vitals"] = cwv
        except Exception as exc:
            out[strategy] = {"error": str(exc)}
    return out


def _extract_aggregate_rating(soup):
    """Busca un AggregateRating en el JSON-LD de una página."""
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            agg = item.get("aggregateRating")
            if not agg and item.get("@type") == "AggregateRating":
                agg = item
            if isinstance(agg, dict) and agg.get("ratingValue"):
                return {
                    "rating": agg.get("ratingValue"),
                    "reviews": agg.get("reviewCount") or agg.get("ratingCount"),
                }
    return None


def check_reputation(hostname):
    """Reputación online (best-effort, gratis).
    - Trustpilot: lee el perfil público del dominio (rating + nº de reseñas).
    Si no existe o falla, devuelve exists=False (no rompe el análisis).
    """
    tp_url = f"https://www.trustpilot.com/review/{hostname}"
    trustpilot = {"exists": False, "url": tp_url}
    resp = fetch(tp_url, timeout=12)
    if not isinstance(resp, Exception) and getattr(resp, "status_code", 0) == 200:
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            agg = _extract_aggregate_rating(soup)
            if agg:
                trustpilot = {"exists": True, "url": tp_url,
                              "rating": agg["rating"], "reviews": agg["reviews"]}
        except Exception:
            pass
    return {"trustpilot": trustpilot}


def fetch_backlinks(hostname):
    """Backlinks reales vía DataForSEO (opcional).
    Se activa si hay DATAFORSEO_LOGIN y DATAFORSEO_PASSWORD en el entorno.
    Si no, devuelve disponible=False con una nota.
    """
    login = os.environ.get("DATAFORSEO_LOGIN")
    password = os.environ.get("DATAFORSEO_PASSWORD")
    if not (login and password):
        return {"disponible": False,
                "nota": ("Análisis de backlinks no configurado. Requiere una API de "
                         "terceros (DataForSEO, Ahrefs, SEMrush). Se activa con la clave.")}
    try:
        resp = requests.post(
            "https://api.dataforseo.com/v3/backlinks/summary/live",
            auth=(login, password),
            json=[{"target": hostname, "internal_list_limit": 1,
                   "backlinks_status_type": "live"}],
            timeout=45,
        )
        res = resp.json()["tasks"][0]["result"][0]
        return {
            "disponible": True,
            "backlinks": res.get("backlinks"),
            "referring_domains": res.get("referring_domains"),
            "rank": res.get("rank"),
            "broken_backlinks": res.get("broken_backlinks"),
            "referring_main_domains": res.get("referring_main_domains"),
        }
    except Exception as exc:
        return {"disponible": False, "nota": f"No se pudo consultar backlinks: {exc}"}


def audit_domain(domain, pagespeed_key=None, fetch_pagespeed=False):
    base_url, hostname = normalize_domain(domain)
    report = {"domain": hostname, "base_url": base_url, "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    # --- Página principal ---
    start = time.time()
    resp = fetch(base_url)
    elapsed = round(time.time() - start, 2)

    if isinstance(resp, Exception):
        report["error"] = f"No se pudo acceder al sitio: {resp}"
        return report

    report["status_code"] = resp.status_code
    report["final_url"] = resp.url
    report["https"] = resp.url.startswith("https://")
    report["redirected"] = resp.url != base_url
    report["response_time_seconds"] = elapsed
    report["page_size_kb"] = round(len(resp.content) / 1024, 1)

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- SEO técnico on-page ---
    title_tag = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_robots = soup.find("meta", attrs={"name": "robots"})
    canonical = soup.find("link", attrs={"rel": "canonical"})
    viewport = soup.find("meta", attrs={"name": "viewport"})
    html_tag = soup.find("html")

    headings = {f"h{i}": len(soup.find_all(f"h{i}")) for i in range(1, 7)}
    images = soup.find_all("img")
    images_missing_alt = [img for img in images if not img.get("alt", "").strip()]

    links = soup.find_all("a", href=True)
    internal_links, external_links = 0, 0
    for a in links:
        href = a["href"]
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        joined = urljoin(base_url, href)
        if urlparse(joined).netloc == hostname:
            internal_links += 1
        else:
            external_links += 1

    visible_text = soup.get_text(separator=" ", strip=True)
    word_count = len(visible_text.split())

    og_tags = {m.get("property"): m.get("content") for m in soup.find_all("meta") if m.get("property", "").startswith("og:")}

    report["onpage"] = {
        "title": title_tag.get_text(strip=True) if title_tag else None,
        "title_length": len(title_tag.get_text(strip=True)) if title_tag else 0,
        "meta_description": meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None,
        "meta_description_length": len(meta_desc["content"].strip()) if meta_desc and meta_desc.get("content") else 0,
        "meta_robots": meta_robots["content"] if meta_robots and meta_robots.get("content") else None,
        "canonical": canonical["href"] if canonical and canonical.get("href") else None,
        "lang": html_tag.get("lang") if html_tag else None,
        "viewport_present": bool(viewport),
        "headings": headings,
        "h1_count": headings["h1"],
        "images_total": len(images),
        "images_missing_alt": len(images_missing_alt),
        "internal_links": internal_links,
        "external_links": external_links,
        "word_count": word_count,
        "open_graph_tags": og_tags,
    }

    # --- robots.txt / sitemap / llms.txt ---
    robots_info = check_robots_txt(base_url)
    report["robots_txt"] = robots_info
    report["sitemap"] = check_sitemap(base_url, robots_info)
    report["llms_txt"] = check_llms_txt(base_url)

    # --- Datos estructurados (Schema.org) ---
    jsonld_types = extract_jsonld_types(soup)
    report["structured_data"] = {
        "jsonld_present": bool(jsonld_types),
        "types_found": sorted(set(jsonld_types)),
        "has_organization": any("organization" in t.lower() for t in jsonld_types),
        "has_faqpage": any("faqpage" in t.lower() for t in jsonld_types),
        "has_product": any("product" in t.lower() for t in jsonld_types),
        "has_article": any(t.lower() in ("article", "newsarticle", "blogposting") for t in jsonld_types),
        "has_localbusiness": any("localbusiness" in t.lower() for t in jsonld_types),
    }

    # --- Señales GEO ---
    blocked = robots_info.get("ai_bots_blocked", [])
    report["geo_signals"] = {
        "ai_bots_explicitly_blocked": blocked,
        "ai_bots_explicitly_allowed": robots_info.get("ai_bots_allowed", []),
        "ai_crawling_open_by_default": len(blocked) == 0,
        "llms_txt_present": report["llms_txt"]["exists"],
        "schema_org_present": bool(jsonld_types),
        "faq_schema_present": report["structured_data"]["has_faqpage"],
        "organization_schema_present": report["structured_data"]["has_organization"],
        "ssr_text_volume_chars": len(visible_text),
        "likely_js_heavy": len(visible_text) < 200,
    }

    # --- Contenido / keywords ---
    report["content"] = {
        "word_count": word_count,
        "top_keywords": word_freq(visible_text, 15),
        "first_paragraph_preview": (visible_text[:280] + "…") if len(visible_text) > 280 else visible_text,
    }

    # --- PageSpeed (opcional) ---
    if fetch_pagespeed:
        report["pagespeed"] = pagespeed_scores(report["final_url"], pagespeed_key)

    # --- Reputación online (Trustpilot + reseñas del propio sitio) ---
    reputacion = check_reputation(hostname)
    reputacion["sitio_propio"] = _extract_aggregate_rating(soup)  # reseñas con schema en su web
    report["reputacion"] = reputacion

    # --- Backlinks (DataForSEO opcional) ---
    report["backlinks"] = fetch_backlinks(hostname)

    # --- Nota de competencia ---
    report["competition_backlinks"] = {
        "note": (
            "El análisis de competidores se estima con IA. Los backlinks reales se "
            "obtienen de DataForSEO si está configurado."
        )
    }

    return report


# ----------------------------------------------------------------------
# Generación del informe en Markdown
# ----------------------------------------------------------------------

def score_section(report):
    """Calcula puntajes simples (0-100) por sección, basados en checklist."""
    scores = {}

    # SEO técnico
    onpage = report.get("onpage", {})
    seo_checks = [
        report.get("https", False),
        bool(onpage.get("title")) and 10 <= onpage.get("title_length", 0) <= 60,
        bool(onpage.get("meta_description")) and 50 <= onpage.get("meta_description_length", 0) <= 160,
        onpage.get("h1_count") == 1,
        onpage.get("viewport_present", False),
        bool(onpage.get("canonical")),
        report.get("sitemap", {}).get("exists", False),
        report.get("robots_txt", {}).get("exists", False),
        onpage.get("images_missing_alt", 1) == 0 if onpage.get("images_total") else True,
        report.get("response_time_seconds", 99) < 1.5,
    ]
    scores["seo_tecnico"] = round(100 * sum(seo_checks) / len(seo_checks))

    # GEO
    geo = report.get("geo_signals", {})
    geo_checks = [
        geo.get("ai_crawling_open_by_default", False),
        geo.get("schema_org_present", False),
        geo.get("organization_schema_present", False),
        geo.get("faq_schema_present", False),
        not geo.get("likely_js_heavy", True),
        geo.get("llms_txt_present", False),
        bool(onpage.get("meta_description")),
        onpage.get("h1_count", 0) >= 1,
    ]
    scores["geo"] = round(100 * sum(geo_checks) / len(geo_checks))

    # Contenido
    content = report.get("content", {})
    content_checks = [
        content.get("word_count", 0) >= 300,
        onpage.get("h1_count", 0) >= 1,
        sum(onpage.get("headings", {}).values()) >= 3,
        bool(onpage.get("meta_description")),
        len(content.get("top_keywords", [])) >= 5,
    ]
    scores["contenido"] = round(100 * sum(content_checks) / len(content_checks))

    scores["promedio_general"] = round((scores["seo_tecnico"] + scores["geo"] + scores["contenido"]) / 3)
    return scores


def build_recommendations(report, scores):
    recs = []
    onpage = report.get("onpage", {})
    geo = report.get("geo_signals", {})
    sd = report.get("structured_data", {})

    if not report.get("https"):
        recs.append("Migrar el sitio a HTTPS: es un requisito básico de seguridad y un factor de ranking.")
    if not onpage.get("title") or not (10 <= onpage.get("title_length", 0) <= 60):
        recs.append("Optimizar la etiqueta <title>: debe existir y tener entre 10 y 60 caracteres, incluyendo la palabra clave principal.")
    if not onpage.get("meta_description") or not (50 <= onpage.get("meta_description_length", 0) <= 160):
        recs.append("Agregar/ajustar la meta description (50-160 caracteres) con un mensaje claro y persuasivo.")
    if onpage.get("h1_count") != 1:
        recs.append("Usar exactamente un H1 por página, que resuma el tema principal.")
    if not onpage.get("viewport_present"):
        recs.append("Agregar la etiqueta meta viewport para garantizar que el sitio sea responsive/mobile-friendly.")
    if not onpage.get("canonical"):
        recs.append("Definir una URL canónica para evitar problemas de contenido duplicado.")
    if not report.get("sitemap", {}).get("exists"):
        recs.append("Crear y publicar un sitemap.xml, y referenciarlo en robots.txt.")
    if not report.get("robots_txt", {}).get("exists"):
        recs.append("Crear un archivo robots.txt en la raíz del dominio.")
    if onpage.get("images_missing_alt"):
        recs.append(f"Agregar texto alternativo (alt) a {onpage['images_missing_alt']} imagen(es) sin descripción.")
    if report.get("response_time_seconds", 0) > 1.5:
        recs.append("Mejorar el tiempo de respuesta del servidor/página (actualmente "
                     f"{report.get('response_time_seconds')}s); considerar caché, CDN y optimización de imágenes.")

    # GEO
    if geo.get("ai_bots_explicitly_blocked"):
        recs.append("Revisar el robots.txt: actualmente bloquea a estos bots de IA: "
                     f"{', '.join(geo['ai_bots_explicitly_blocked'])}. Si se quiere aparecer en respuestas de "
                     "ChatGPT/Perplexity/Gemini, hay que permitirles el acceso (decisión estratégica).")
    if not sd.get("jsonld_present"):
        recs.append("Implementar datos estructurados Schema.org (JSON-LD): al menos Organization y, si aplica, "
                     "FAQPage, Product o LocalBusiness. Mejora la comprensión del contenido por buscadores e IA.")
    elif not sd.get("has_organization"):
        recs.append("Agregar schema 'Organization' para reforzar la identidad de marca ante motores de IA.")
    if not sd.get("has_faqpage"):
        recs.append("Considerar agregar una sección de Preguntas Frecuentes con schema FAQPage: aumenta la "
                     "probabilidad de aparecer citado en respuestas generadas por IA (AI Overviews, ChatGPT, etc.).")
    if geo.get("likely_js_heavy"):
        recs.append("El contenido visible en el HTML inicial es muy escaso (posible sitio renderizado por JavaScript). "
                     "Implementar renderizado del lado del servidor (SSR) o pre-renderizado para que los crawlers de "
                     "buscadores e IA puedan leer el contenido.")
    if not geo.get("llms_txt_present"):
        recs.append("Opcional: crear un archivo llms.txt con un resumen estructurado del sitio (bajo costo, soporte "
                     "incipiente en algunos motores de IA como Perplexity).")

    # Contenido
    if report.get("content", {}).get("word_count", 0) < 300:
        recs.append("La página principal tiene poco contenido textual (<300 palabras). Ampliar el contenido relevante "
                     "ayuda tanto al SEO tradicional como a la GEO.")

    return recs


def to_markdown(report, scores, recommendations):
    d = report
    lines = []
    lines.append(f"# Diagnóstico SEO & GEO — {d['domain']}")
    lines.append(f"\n_Generado automáticamente el {d['fetched_at']}_\n")

    lines.append("## Resumen de puntajes\n")
    lines.append(f"- **Promedio general:** {scores['promedio_general']}/100")
    lines.append(f"- **SEO técnico:** {scores['seo_tecnico']}/100")
    lines.append(f"- **GEO (visibilidad en IA generativa):** {scores['geo']}/100")
    lines.append(f"- **Contenido:** {scores['contenido']}/100\n")

    lines.append("## Datos generales\n")
    lines.append(f"- URL analizada: {d.get('final_url')}")
    lines.append(f"- Código de estado HTTP: {d.get('status_code')}")
    lines.append(f"- HTTPS: {'Sí' if d.get('https') else 'No'}")
    lines.append(f"- Tiempo de respuesta: {d.get('response_time_seconds')} s")
    lines.append(f"- Tamaño de la página: {d.get('page_size_kb')} KB\n")

    onpage = d.get("onpage", {})
    lines.append("## SEO técnico on-page\n")
    lines.append(f"- Title: \"{onpage.get('title')}\" ({onpage.get('title_length')} caracteres)")
    lines.append(f"- Meta description: \"{onpage.get('meta_description')}\" ({onpage.get('meta_description_length')} caracteres)")
    lines.append(f"- Meta robots: {onpage.get('meta_robots')}")
    lines.append(f"- Canonical: {onpage.get('canonical')}")
    lines.append(f"- Idioma declarado (lang): {onpage.get('lang')}")
    lines.append(f"- Viewport (mobile-friendly): {'Sí' if onpage.get('viewport_present') else 'No'}")
    lines.append(f"- Encabezados: {onpage.get('headings')}")
    lines.append(f"- Imágenes totales: {onpage.get('images_total')} (sin alt: {onpage.get('images_missing_alt')})")
    lines.append(f"- Enlaces internos: {onpage.get('internal_links')} | externos: {onpage.get('external_links')}")
    lines.append(f"- Palabras en la página: {onpage.get('word_count')}")
    lines.append(f"- Sitemap: {'Sí — ' + d['sitemap']['url'] if d.get('sitemap', {}).get('exists') else 'No encontrado'}")
    lines.append(f"- robots.txt: {'Sí' if d.get('robots_txt', {}).get('exists') else 'No encontrado'}\n")

    lines.append("## Señales GEO (visibilidad en motores de IA generativa)\n")
    geo = d.get("geo_signals", {})
    sd = d.get("structured_data", {})
    lines.append(f"- Bots de IA explícitamente bloqueados en robots.txt: {geo.get('ai_bots_explicitly_blocked') or 'Ninguno'}")
    lines.append(f"- Bots de IA explícitamente permitidos: {geo.get('ai_bots_explicitly_allowed') or '(no especificado, acceso por defecto)'}")
    lines.append(f"- llms.txt presente: {'Sí' if geo.get('llms_txt_present') else 'No'}")
    lines.append(f"- Datos estructurados Schema.org presentes: {'Sí' if sd.get('jsonld_present') else 'No'}")
    if sd.get("types_found"):
        lines.append(f"  - Tipos encontrados: {', '.join(sd['types_found'])}")
    lines.append(f"- Schema FAQPage: {'Sí' if sd.get('has_faqpage') else 'No'}")
    lines.append(f"- Schema Organization: {'Sí' if sd.get('has_organization') else 'No'}")
    lines.append(f"- Posible sitio fuertemente dependiente de JavaScript (poco contenido en HTML inicial): "
                  f"{'Sí — riesgo para crawlers de IA' if geo.get('likely_js_heavy') else 'No'}\n")

    content = d.get("content", {})
    lines.append("## Contenido y palabras clave\n")
    lines.append(f"- Palabras totales en la página principal: {content.get('word_count')}")
    lines.append("- Palabras más frecuentes (excluyendo conectores):")
    for word, count in content.get("top_keywords", []):
        lines.append(f"  - {word}: {count}")
    lines.append(f"\n> Vista previa del contenido: \"{content.get('first_paragraph_preview')}\"\n")

    if "pagespeed" in d:
        lines.append("## Rendimiento (Google PageSpeed Insights)\n")
        for strategy, data in d["pagespeed"].items():
            lines.append(f"### {strategy.capitalize()}")
            if "error" in data:
                lines.append(f"- Error al consultar PageSpeed: {data['error']}")
            else:
                for k, v in data.items():
                    if k != "core_web_vitals":
                        lines.append(f"- {k}: {v}")
        lines.append("")

    lines.append("## Competencia y backlinks\n")
    lines.append(f"- {d.get('competition_backlinks', {}).get('note')}\n")

    lines.append("## Recomendaciones priorizadas\n")
    for i, rec in enumerate(recommendations, 1):
        lines.append(f"{i}. {rec}")

    lines.append("\n---")
    lines.append("_Informe generado automáticamente. Para una estrategia personalizada, contáctanos._")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico SEO & GEO de un dominio")
    parser.add_argument("domain", help="Dominio o URL a analizar (ej: midominio.com)")
    parser.add_argument("--pagespeed-key", help="API key de Google PageSpeed Insights (opcional)", default=None)
    parser.add_argument("--with-pagespeed", action="store_true", help="Consultar Google PageSpeed Insights")
    parser.add_argument("--out-prefix", help="Prefijo para los archivos de salida", default=None)
    parser.add_argument("--insecure", action="store_true", help="No verificar certificados SSL (solo para pruebas en redes con proxy/MITM)")
    args = parser.parse_args()

    if args.insecure:
        global VERIFY_SSL
        VERIFY_SSL = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    report = audit_domain(args.domain, pagespeed_key=args.pagespeed_key, fetch_pagespeed=args.with_pagespeed)

    if "error" in report:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)

    scores = score_section(report)
    recommendations = build_recommendations(report, scores)
    report["scores"] = scores
    report["recommendations"] = recommendations

    prefix = args.out_prefix or report["domain"].replace(".", "_")
    json_path = f"{prefix}_audit.json"
    md_path = f"{prefix}_informe.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report, scores, recommendations))

    print(f"OK. Generado: {json_path} y {md_path}")
    print(f"Puntaje general: {scores['promedio_general']}/100")


if __name__ == "__main__":
    main()
