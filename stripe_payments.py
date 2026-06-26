# -*- coding: utf-8 -*-
"""
stripe_payments.py
------------------
Logica de pagos con Stripe Checkout.

Variables de entorno requeridas:
    STRIPE_SECRET_KEY      sk_live_... o sk_test_...
    STRIPE_PRICE_ID        price_...  (ID del precio en Stripe Dashboard)
    STRIPE_WEBHOOK_SECRET  whsec_...  (secreto del webhook en Stripe Dashboard)
    APP_BASE_URL           https://tu-widget.vercel.app  (sin / al final)
"""

import os
import json

try:
    import stripe
except ImportError:
    stripe = None


def _get_stripe():
    """Devuelve el modulo stripe configurado, o lanza un error claro."""
    if stripe is None:
        raise RuntimeError(
            "El paquete 'stripe' no esta instalado. "
            "Agrega 'stripe==10.*' a requirements.txt y redespliega."
        )
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta la variable de entorno STRIPE_SECRET_KEY. "
            "Configurala en Render -> Environment."
        )
    stripe.api_key = api_key
    return stripe


def crear_sesion_checkout(nombre: str, email: str, dominio: str,
                           telefono: str = "", empresa: str = "") -> dict:
    """
    Crea una sesion de Stripe Checkout y devuelve la URL de pago.

    Retorna:
        {"checkout_url": "https://checkout.stripe.com/...", "session_id": "cs_..."}
    """
    s = _get_stripe()
    price_id = os.environ.get("STRIPE_PRICE_ID")
    if not price_id:
        raise RuntimeError(
            "Falta STRIPE_PRICE_ID. Crea un producto en Stripe Dashboard "
            "y pega el ID del precio (price_...) en las variables de entorno de Render."
        )

    base_url = os.environ.get("APP_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError(
            "Falta APP_BASE_URL (ej. https://tu-widget.vercel.app). "
            "Configurala en Render -> Environment."
        )

    # Página de resultado (donde se muestra el informe tras pagar). Configurable
    # con STRIPE_SUCCESS_URL; por defecto una página del sitio WordPress.
    # Nota: se usa el parámetro 'ref' (no 'session_id') porque muchos firewalls
    # de WordPress/LiteSpeed bloquean el parámetro 'session_id' (devuelven 403).
    success_base = os.environ.get("STRIPE_SUCCESS_URL") or f"{base_url}/informe-seo-geo"
    sep = "&" if "?" in success_base else "?"
    success_url = f"{success_base}{sep}ref={{CHECKOUT_SESSION_ID}}"
    cancel_url = os.environ.get("STRIPE_CANCEL_URL") or base_url

    session = s.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=email,
        success_url=success_url,
        cancel_url=cancel_url,
        # Muestra el cajón "Agregar código promocional" en la página de pago.
        # Tu equipo usa un código (ej. cupón 100%) para generar el informe gratis.
        allow_promotion_codes=True,
        metadata={
            "nombre": nombre,
            "dominio": dominio,
            "telefono": telefono or "",
            "empresa": empresa or "",
        },
    )

    return {"checkout_url": session.url, "session_id": session.id}


def verificar_pago_y_obtener_metadata(session_id: str) -> dict:
    """
    Verifica que el pago este completado y devuelve los metadatos del lead.

    Retorna:
        {
            "pagado": True/False,
            "nombre": ..., "email": ..., "dominio": ...,
            "telefono": ..., "empresa": ...
        }
    Lanza ValueError si el session_id no es valido.
    """
    s = _get_stripe()

    try:
        session = s.checkout.Session.retrieve(session_id)
    except s.error.InvalidRequestError as exc:
        raise ValueError(f"Session de Stripe no valida: {exc}") from exc

    # "paid" = pago normal; "no_payment_required" = total $0 (código del 100%).
    pagado = session.payment_status in ("paid", "no_payment_required")

    metadata = session.metadata or {}
    return {
        "pagado": pagado,
        "nombre": metadata.get("nombre", ""),
        "email": session.customer_email or "",
        "dominio": metadata.get("dominio", ""),
        "telefono": metadata.get("telefono", ""),
        "empresa": metadata.get("empresa", ""),
    }


def verificar_firma_webhook(payload: bytes, sig_header: str) -> dict:
    """
    Verifica la firma del webhook de Stripe y devuelve el evento.
    Lanza stripe.error.SignatureVerificationError si la firma no es valida.
    """
    s = _get_stripe()
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise RuntimeError(
            "Falta STRIPE_WEBHOOK_SECRET. Obtenlo en Stripe Dashboard "
            "-> Developers -> Webhooks -> tu endpoint -> Signing secret."
        )
    event = s.Webhook.construct_event(payload, sig_header, webhook_secret)
    return event
