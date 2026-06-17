# Agente de Diagnóstico SEO & GEO

Servicio backend que recibe el formulario de WordPress (vía webhook), genera
un informe PDF de diagnóstico SEO técnico + GEO (visibilidad en IA
generativa) + contenido, lo envía por correo al cliente y registra el lead
para seguimiento comercial.

## Contenido del proyecto

| Archivo | Función |
|---|---|
| `seo_geo_audit.py` | Lógica del análisis del dominio (scraping, robots.txt, schema.org, scoring) |
| `report_pdf.py` | Genera el PDF con la marca de la empresa |
| `ai_summary.py` | (Opcional) Resumen ejecutivo personalizado generado con Claude |
| `main.py` | API FastAPI (webhook, descarga del informe) |
| `test_pipeline.py` | Script de prueba sin necesidad de levantar el servidor |
| `requirements.txt` | Dependencias Python |
| `.env.example` | Plantilla de configuración |

---

## 1. Instalación local (para probar)

```bash
cd agente-seo-geo
python3 -m venv venv
source venv/bin/activate          # En Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # y completa los valores
```

### Probar solo el motor de análisis (sin servidor)

```bash
python3 seo_geo_audit.py https://www.tudominio.com --with-pagespeed --pagespeed-key TU_API_KEY
```

Genera `<dominio>_audit.json` y `<dominio>_informe.md`.

### Probar el flujo completo (análisis + PDF + registro de lead)

```bash
python3 test_pipeline.py https://www.tudominio.com
```

### Levantar la API localmente

```bash
uvicorn main:app --reload --port 8000
```

Probar con:

```bash
curl -X POST http://localhost:8000/api/diagnostico \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Juan Pérez","email":"juan@correo.com","dominio":"www.tudominio.com","telefono":"3000000000","empresa":"Mi Empresa"}'
```

La respuesta incluye los puntajes y un `pdf_url` para descargar el informe
(`GET /api/informe/{id}`). El correo al cliente y la notificación al equipo
de ventas se envían en segundo plano si configuraste SMTP en `.env`.

---

## 2. Despliegue en un VPS (Ubuntu)

1. **Crear el VPS** (1 vCPU / 1-2 GB RAM es suficiente para empezar).
2. **Instalar dependencias del sistema:**
   ```bash
   sudo apt update && sudo apt install -y python3-venv python3-pip nginx
   ```
3. **Subir el proyecto** (vía `git clone`, `scp` o similar) a, por ejemplo,
   `/opt/agente-seo-geo`.
4. **Crear entorno virtual e instalar dependencias** (igual que en el paso 1).
5. **Configurar `.env`** con los datos reales (SMTP, branding, API keys).
6. **Crear un servicio systemd** para que el agente corra siempre y se
   reinicie solo. Crea `/etc/systemd/system/agente-seo-geo.service`:

   ```ini
   [Unit]
   Description=Agente Diagnostico SEO GEO
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/opt/agente-seo-geo
   EnvironmentFile=/opt/agente-seo-geo/.env
   ExecStart=/opt/agente-seo-geo/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now agente-seo-geo
   ```

7. **Exponerlo a internet con Nginx** (proxy inverso + HTTPS con Let's
   Encrypt). Ejemplo de bloque de servidor:

   ```nginx
   server {
       server_name api.tudominio.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   ```bash
   sudo certbot --nginx -d api.tudominio.com
   ```

Al final tendrás la API disponible en `https://api.tudominio.com/api/diagnostico`.

---

## 3. Integración con el formulario de WordPress

La idea: el formulario de la landing page "Diagnóstico SEO + GEO gratis"
envía sus datos como webhook a `https://api.tudominio.com/api/diagnostico`.

### Opción A — WPForms (plan Pro, incluye Webhooks)

1. Crea un formulario con los campos: **Nombre**, **Email**, **Dominio**,
   **Teléfono** (opcional), **Empresa** (opcional).
2. En *Configuración del formulario → Marketing → Webhooks*, agrega un
   webhook:
   - **Request URL:** `https://api.tudominio.com/api/diagnostico`
   - **Request Method:** `POST`
   - **Request Format:** `JSON`
   - **Request Body:** mapea cada campo del formulario a las claves
     `nombre`, `email`, `dominio`, `telefono`, `empresa`.
3. Guarda y haz una prueba real desde la landing page.

### Opción B — Contact Form 7 + plugin "CF7 to Webhook" (gratis)

1. Crea el formulario CF7 con los campos equivalentes
   (`[text* nombre]`, `[email* email]`, `[text* dominio]`, etc.).
2. Instala el plugin **"Contact Form 7 - Webhook"** (o similar) desde el
   repositorio de WordPress.
3. Configura la URL del webhook igual que en la Opción A, en formato JSON.

### Opción C — Si no hay plugin de webhooks disponible

Se puede crear un pequeño *snippet* PHP (en un plugin propio o con "Code
Snippets") que, en el hook `wpcf7_mail_sent` (CF7) o equivalente, haga un
`wp_remote_post()` hacia la API. Si llegas a este punto, puedo ayudarte a
escribir ese fragmento.

### Página de "gracias" / resultado inmediato

La API responde de forma síncrona con los puntajes y un enlace de descarga
del PDF (`pdf_url`). Si quieres mostrar el puntaje inmediatamente en la
página de agradecimiento, se puede agregar un pequeño script JS que llame a
la API directamente (en vez de —o además de— el webhook del formulario) y
muestre el resultado. Puedo ayudarte a implementarlo si lo deseas.

---

## 4. Variables de entorno relevantes (`.env`)

Ver `.env.example` para la lista completa. Las más importantes para el MVP:

- `ALLOWED_ORIGINS`: dominio de tu sitio WordPress (para CORS).
- `SMTP_*`: credenciales para enviar el PDF por correo.
- `NOTIFY_EMAIL`: correo del equipo comercial que recibe cada nuevo lead.
- `COMPANY_NAME`, `BRAND_*`: personalización del PDF.
- `ENABLE_PAGESPEED` / `PAGESPEED_API_KEY`: activa el análisis de
  rendimiento (Core Web Vitals). Aumenta el tiempo de respuesta (~10-20s),
  por eso es opcional.
- `ENABLE_AI_SUMMARY` / `ANTHROPIC_API_KEY` / `AI_MODEL`: activa el resumen
  ejecutivo redactado por IA (ver sección 5).

---

## 5. Resumen ejecutivo con IA (opcional)

Por defecto, el informe se genera con reglas fijas (sección "¿Quién hace el
análisis?" más abajo). Si quieres que además incluya un resumen ejecutivo
redactado en lenguaje natural y personalizado para cada cliente —pensado
para el dueño del negocio, no para un técnico—, puedes activar la
integración con la API de Claude (Anthropic):

1. Crea una cuenta y una clave de API en
   [console.anthropic.com](https://console.anthropic.com/).
2. En tu `.env`, configura:
   ```
   ENABLE_AI_SUMMARY=true
   ANTHROPIC_API_KEY=sk-ant-...
   AI_MODEL=claude-haiku-4-5-20251001
   ```
3. Listo. Cada informe incluirá una sección "Resumen ejecutivo" antes de
   los datos técnicos, generada a partir de los resultados del análisis.

**Costo:** se usa el modelo "haiku" (el más económico) por defecto. El
costo por informe es de unos pocos centavos de dólar. Si el campo no está
activado, o falla la llamada a la API, el informe se genera igual sin esa
sección (no rompe el flujo).

---

## 6. ¿Quién hace el análisis técnico?

Es importante tenerlo claro: **el análisis SEO/GEO en sí (los puntajes y
las recomendaciones técnicas) NO lo hace una IA.** Lo hace `seo_geo_audit.py`,
un programa que revisa el sitio contra una lista fija de criterios (HTTPS,
meta tags, robots.txt, datos estructurados, bots de IA, etc.) y calcula los
puntajes con una fórmula. Esto es rápido, gratis y 100% predecible.

La IA (sección 5) es una capa adicional **opcional** que solo redacta un
resumen más natural a partir de esos resultados — no cambia los puntajes ni
inventa datos del sitio.

---

## 7. Próximas mejoras sugeridas

- Agregar el logo real de la empresa (`BRAND_LOGO_PATH`) al PDF.
- Conectar `guardar_lead()` a un CRM (HubSpot, Airtable, Google Sheets) en
  vez de (o además de) `leads.csv`.
- Agregar un módulo de competencia/backlinks con Ahrefs o SEMrush para una
  versión "premium" del informe.
- Si el volumen de solicitudes crece, mover el análisis a una cola
  (Celery + Redis) para no bloquear el servidor.
