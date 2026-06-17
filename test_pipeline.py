# -*- coding: utf-8 -*-
"""
test_pipeline.py
------------------
Prueba el flujo completo (sin levantar FastAPI, ya que no está instalado en
este entorno de pruebas): simula lo que hace el endpoint /api/diagnostico
con un lead de ejemplo y un dominio real.

Ejecutar:
    python3 test_pipeline.py https://www.ejemplo.com --insecure
"""
import sys
import csv
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import seo_geo_audit as sga
from report_pdf import generate_pdf
from ai_summary import generar_resumen_ia

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
LEADS_CSV = BASE_DIR / "leads.csv"
REPORTS_DIR.mkdir(exist_ok=True)


def guardar_lead(row):
    nuevo = not LEADS_CSV.exists()
    with open(LEADS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if nuevo:
            writer.writeheader()
        writer.writerow(row)


def main():
    domain = sys.argv[1] if len(sys.argv) > 1 else "https://www.anthropic.com"
    insecure = "--insecure" in sys.argv

    if insecure:
        sga.VERIFY_SSL = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    lead = {
        "nombre": "Jhoan Gómez",
        "email": "jsebastiangomez@unimonserrate.edu.co",
        "telefono": "3000000000",
        "empresa": "Empresa de Prueba",
        "dominio": domain.replace("https://", "").replace("http://", "").split("/")[0],
    }

    print(f"1) Analizando {domain} ...")
    report = sga.audit_domain(domain, fetch_pagespeed=False)
    if "error" in report:
        print("ERROR en el análisis:", report["error"])
        sys.exit(1)

    scores = sga.score_section(report)
    recommendations = sga.build_recommendations(report, scores)
    report["scores"] = scores
    report["recommendations"] = recommendations
    print("   Puntajes:", scores)

    print("1.5) Generando resumen ejecutivo con IA (si está activado) ...")
    report["ai_summary"] = generar_resumen_ia(report, scores, recommendations, lead)
    print("   ai_summary:", "generado" if report["ai_summary"] else "omitido")

    report_id = "test123456ab"
    pdf_path = REPORTS_DIR / f"{report_id}.pdf"
    print(f"2) Generando PDF en {pdf_path} ...")
    generate_pdf(report, lead, str(pdf_path))
    print("   PDF generado:", pdf_path.exists(), pdf_path.stat().st_size, "bytes")

    print("3) Guardando lead en leads.csv ...")
    guardar_lead({
        "fecha": datetime.utcnow().isoformat(),
        "id": report_id,
        **lead,
        "score_general": scores["promedio_general"],
        "score_seo": scores["seo_tecnico"],
        "score_geo": scores["geo"],
        "score_contenido": scores["contenido"],
    })
    print("   leads.csv:", LEADS_CSV.exists())

    print("\nOK - flujo completo simulado correctamente (sin envio de correo: SMTP no configurado).")


if __name__ == "__main__":
    main()
