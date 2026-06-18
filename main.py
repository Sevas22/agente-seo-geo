# -*- coding: utf-8 -*-
"""
main.py
--------
Servicio FastAPI que recibe los datos del formulario de WordPress
(webhook), genera el diagnóstico SEO & GEO en PDF y lo envía por correo
al cliente, además de registrar el lead para seguimiento comercial.

Endpoints:
    POST /api/diagnostico   -> recibe el formulario y dispara todo el flujo
    GET  /api/informe/{id}  -> descarga el PDF generado
    GET  /health            -> chequeo de salud

Variables de entorno (ver .env.example):
    ALLOWED_ORIGINS, PAGESPEED_API_KEY, ENABLE_PAGESPEED,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_USE_TLS,
    NOTIFY_EMAIL, COMPANY_NAME, BRAND_PRIMARY_COLOR, BRAND_ACCENT_COLOR,
    BRAND_LOGO_PATH, BRAND_CTA_TEXT, BRAND_CTA_URL, BRAND_CONTACT_EMAIL,
    ENABLE_AI_SUMMARY, ANTHROPIC_API_KEY, AI_MODEL,
    STRIPE_SECRET_KEY, STRIPE_PRICE_ID, STRIPE_WEBHOOK_SECRET, APP_BASE_URL

Ejecutar localmente:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

import csv
import os
import re
import smtplib
import uuid
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

# Cargar .env ANTES de importar módulos locales: report_pdf lee el branding
# (BRAND_LOGO_PATH, COMPANY_NAME, etc.) en tiempo de importación.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr, field_validator

from seo_geo_audit import audit_domain, score_section, build_recommendations
from report_pdf import generate_pdf, DEFAULT_BRANDING
from ai_summary import generar_resumen_ia
from stripe_payments import (
    crear_sesion_checkout,
    verificar_pago_y_obtener_metadata,
    verificar_firma_webhook,
)


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
LEADS_CSV = BASE_DIR / "leads.csv"
REPORTS_DIR.mkdir(exist_ok=True)

ENABLE_PAGESPEED = os.environ.get("ENABLE_PAGESPEED", "false").lower() == "true"
PAGESPEED_API_KEY = os.environ.get("PAGESPEED_API_KEY")

ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]

app = FastAPI(title="Agente de Diagnóstico SEO & GEO")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# Registra el traceback completo en los logs del servidor (visibles en
# Dokploy -> Logs) para diagnóstico, pero NO lo expone al cliente.
import traceback as _tb_log


@app.exception_handler(Exception)
async def _log_exception_handler(request, exc):
    print("".join(_tb_log.format_exception(type(exc), exc, exc.__traceback__)))
    return JSONResponse({"detail": "Error interno del servidor."}, status_code=500)


# ----------------------------------------------------------------------
# Modelos
# ----------------------------------------------------------------------
class DiagnosticoRequest(BaseModel):
    nombre: str
    email: EmailStr
    dominio: str
    telefono: str | None = None
    empresa: str | None = None

    @field_validator("dominio")
    @classmethod
    def limpiar_dominio(cls, v):
        v = v.strip().lower()
        v = re.sub(r"^https?://", "", v)
        v = v.split("/")[0]
        if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", v):
            raise ValueError("Dominio no válido")
        return v


class DiagnosticoResponse(BaseModel):
    id: str
    dominio: str
    scores: dict
    pdf_url: str
    mensaje: str


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def guardar_lead(row: dict):
    nuevo = not LEADS_CSV.exists()
    with open(LEADS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if nuevo:
            writer.writeheader()
        writer.writerow(row)


def enviar_correo_con_adjunto(destinatario, asunto, cuerpo, adjunto_path, bcc=None):
    host = os.environ.get("SMTP_HOST")
    if not host:
        print("[main] SMTP no configurado: se omite el envío de correo.")
        return False

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    sender = os.environ.get("SMTP_FROM", user)
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = sender
    msg["To"] = destinatario
    if bcc:
        msg["Bcc"] = bcc
    msg.set_content(cuerpo)

    with open(adjunto_path, "rb") as f:
        msg.add_attachment(
            f.read(), maintype="application", subtype="pdf",
            filename=Path(adjunto_path).name,
        )

    with smtplib.SMTP(host, port) as server:
        if use_tls:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(msg)
    return True


def notificar_equipo_comercial(lead: dict, scores: dict, pdf_path: Path):
    notify_email = os.environ.get("NOTIFY_EMAIL")
    if not notify_email:
        return
    cuerpo = (
        f"Nuevo lead de diagnóstico SEO & GEO\n\n"
        f"Nombre: {lead['nombre']}\n"
        f"Empresa: {lead.get('empresa') or '-'}\n"
        f"Email: {lead['email']}\n"
        f"Teléfono: {lead.get('telefono') or '-'}\n"
        f"Dominio: {lead['dominio']}\n\n"
        f"Puntaje general: {scores['promedio_general']}/100 "
        f"(SEO: {scores['seo_tecnico']}, GEO: {scores['geo']}, Contenido: {scores['contenido']})\n\n"
        f"Puntajes bajos = mayor oportunidad de venta del servicio de SEO."
    )
    try:
        enviar_correo_con_adjunto(notify_email, f"Nuevo lead: {lead['dominio']}", cuerpo, pdf_path)
    except Exception as exc:
        print(f"[main] Error notificando al equipo comercial: {exc}")


def procesar_y_enviar(lead: dict, report: dict, pdf_path: Path):
    """Tarea en background: envía el informe al cliente y notifica al equipo comercial."""
    cuerpo = (
        f"Hola {lead['nombre']},\n\n"
        f"Adjunto encontrarás el diagnóstico SEO & GEO de {lead['dominio']}.\n\n"
        f"Puntaje general: {report['scores']['promedio_general']}/100\n\n"
        f"Si quieres que te ayudemos a mejorar estos resultados, responde este "
        f"correo o agenda una asesoría gratuita: "
        f"{os.environ.get('BRAND_CTA_URL', DEFAULT_BRANDING['cta_url'])}\n\n"
        f"Saludos,\n{os.environ.get('COMPANY_NAME', DEFAULT_BRANDING['company_name'])}"
    )
    try:
        enviar_correo_con_adjunto(
            lead["email"],
            f"Tu diagnóstico SEO & GEO de {lead['dominio']}",
            cuerpo,
            pdf_path,
        )
    except Exception as exc:
        print(f"[main] Error enviando correo al cliente: {exc}")

    notificar_equipo_comercial(lead, report["scores"], pdf_path)


def generar_pdf_seguro(report, lead, pdf_path):
    """Genera el PDF; si falla con el análisis de IA, reintenta SIN IA para que
    el informe (con los datos medidos) siempre se entregue. Registra el error
    real en los logs para diagnóstico."""
    try:
        generate_pdf(report, lead, str(pdf_path))
    except Exception as exc:
        import traceback
        print(f"[main] Error generando PDF con IA, reintento sin IA: {exc}")
        traceback.print_exc()
        report_sin_ia = dict(report)
        report_sin_ia["ai_summary"] = None
        generate_pdf(report_sin_ia, lead, str(pdf_path))


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/diagnostico", response_model=DiagnosticoResponse)
def crear_diagnostico(payload: DiagnosticoRequest, background_tasks: BackgroundTasks):
    try:
        report = audit_domain(
            payload.dominio,
            pagespeed_key=PAGESPEED_API_KEY,
            fetch_pagespeed=ENABLE_PAGESPEED,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo analizar el dominio: {exc}")

    if "error" in report:
        raise HTTPException(status_code=422, detail=report["error"])

    scores = score_section(report)
    recommendations = build_recommendations(report, scores)
    report["scores"] = scores
    report["recommendations"] = recommendations

    report_id = uuid.uuid4().hex[:12]
    pdf_path = REPORTS_DIR / f"{report_id}.pdf"

    lead = {
        "nombre": payload.nombre,
        "email": payload.email,
        "telefono": payload.telefono or "",
        "empresa": payload.empresa or "",
        "dominio": payload.dominio,
    }

    # Resumen ejecutivo con IA (opcional, ver ai_summary.py).
    # Si no está activado o falla, no afecta el resto del informe.
    report["ai_summary"] = generar_resumen_ia(report, scores, recommendations, lead)

    generar_pdf_seguro(report, lead, pdf_path)

    guardar_lead({
        "fecha": datetime.utcnow().isoformat(),
        "id": report_id,
        **lead,
        "score_general": scores["promedio_general"],
        "score_seo": scores["seo_tecnico"],
        "score_geo": scores["geo"],
        "score_contenido": scores["contenido"],
    })

    background_tasks.add_task(procesar_y_enviar, lead, report, pdf_path)

    return DiagnosticoResponse(
        id=report_id,
        dominio=payload.dominio,
        scores=scores,
        pdf_url=f"/api/informe/{report_id}",
        mensaje="Diagnóstico generado. Te enviaremos una copia por correo.",
    )


@app.get("/api/informe/{report_id}")
def descargar_informe(report_id: str):
    if not re.match(r"^[a-f0-9]{12}$", report_id):
        raise HTTPException(status_code=404, detail="Informe no encontrado")
    pdf_path = REPORTS_DIR / f"{report_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Informe no encontrado")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"diagnostico_seo_geo_{report_id}.pdf")


# ----------------------------------------------------------------------
# Endpoints de pago con Stripe
# ----------------------------------------------------------------------

class PagoRequest(BaseModel):
    nombre: str
    email: EmailStr
    dominio: str
    telefono: str | None = None
    empresa: str | None = None

    @field_validator("dominio")
    @classmethod
    def limpiar_dominio(cls, v):
        v = v.strip().lower()
        v = re.sub(r"^https?://", "", v)
        v = v.split("/")[0]
        if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", v):
            raise ValueError("Dominio no valido")
        return v


class PagoResponse(BaseModel):
    checkout_url: str
    session_id: str


class VerificarPagoRequest(BaseModel):
    session_id: str


@app.post("/api/crear-sesion-pago", response_model=PagoResponse)
def crear_sesion_pago(payload: PagoRequest):
    """
    Crea una sesion de Stripe Checkout y devuelve la URL de pago.
    El frontend redirige al usuario a esa URL.
    """
    try:
        resultado = crear_sesion_checkout(
            nombre=payload.nombre,
            email=payload.email,
            dominio=payload.dominio,
            telefono=payload.telefono or "",
            empresa=payload.empresa or "",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error al crear sesion de pago: {exc}")

    return PagoResponse(**resultado)


@app.post("/api/verificar-pago")
def verificar_pago(payload: VerificarPagoRequest, background_tasks: BackgroundTasks):
    """
    Verifica que el pago de Stripe este confirmado, ejecuta el analisis
    SEO/GEO, genera el PDF y lo envia por correo.
    Devuelve los puntajes y la URL de descarga del PDF.
    """
    try:
        meta = verificar_pago_y_obtener_metadata(payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not meta["pagado"]:
        raise HTTPException(status_code=402, detail="El pago aun no ha sido confirmado por Stripe.")

    # Evitar re-procesar si ya existe el informe para esta sesion
    session_short = re.sub(r"[^a-z0-9]", "", payload.session_id.lower())[:12]
    pdf_path = REPORTS_DIR / f"{session_short}.pdf"

    lead = {
        "nombre": meta["nombre"],
        "email": meta["email"],
        "telefono": meta["telefono"],
        "empresa": meta["empresa"],
        "dominio": meta["dominio"],
    }

    if not pdf_path.exists():
        try:
            report = audit_domain(
                meta["dominio"],
                pagespeed_key=PAGESPEED_API_KEY,
                fetch_pagespeed=ENABLE_PAGESPEED,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"No se pudo analizar el dominio: {exc}")

        if "error" in report:
            raise HTTPException(status_code=422, detail=report["error"])

        scores = score_section(report)
        recommendations = build_recommendations(report, scores)
        report["scores"] = scores
        report["recommendations"] = recommendations
        report["ai_summary"] = generar_resumen_ia(report, scores, recommendations, lead)

        generar_pdf_seguro(report, lead, pdf_path)

        guardar_lead({
            "fecha": datetime.utcnow().isoformat(),
            "id": session_short,
            "stripe_session": payload.session_id,
            **lead,
            "score_general": scores["promedio_general"],
            "score_seo": scores["seo_tecnico"],
            "score_geo": scores["geo"],
            "score_contenido": scores["contenido"],
        })

        background_tasks.add_task(procesar_y_enviar, lead, report, pdf_path)
    else:
        # PDF ya existe — reconstruir scores desde leads.csv si es posible
        scores = {"promedio_general": 0, "seo_tecnico": 0, "geo": 0, "contenido": 0}
        report = {"scores": scores, "domain": meta["dominio"]}

    return {
        "id": session_short,
        "dominio": meta["dominio"],
        "nombre": meta["nombre"],
        "scores": report["scores"],
        "pdf_url": f"/api/informe/{session_short}",
        "mensaje": "Diagnostico generado. Te enviamos el informe completo a tu correo.",
    }


@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    """
    Webhook de Stripe para confirmacion asincrona de pagos.
    Registra el evento en los logs — el procesamiento real ocurre
    en /api/verificar-pago llamado desde el frontend.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = verificar_firma_webhook(payload, sig_header)
    except RuntimeError as exc:
        # STRIPE_WEBHOOK_SECRET no configurado — solo loguear
        print(f"[webhook] {exc}")
        return JSONResponse({"received": True})
    except Exception as exc:
        print(f"[webhook] Firma invalida: {exc}")
        raise HTTPException(status_code=400, detail="Firma de webhook invalida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"[webhook] Pago completado: session={session['id']} email={session.get('customer_email')}")

    return JSONResponse({"received": True})
