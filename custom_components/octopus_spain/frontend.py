"""Frontend endpoints for Octopus Energy Spain."""

from __future__ import annotations

import re
from typing import Any

from aiohttp import ClientError, web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import OctopusSpainError
from .const import DOMAIN
from .services import first_runtime_data

INVOICE_DOWNLOAD_PATH = f"/api/{DOMAIN}/invoice/{{invoice_id_hash}}"
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class OctopusSpainInvoiceDownloadView(HomeAssistantView):
    """Download invoice PDFs through Home Assistant as attachments."""

    url = INVOICE_DOWNLOAD_PATH
    name = f"api:{DOMAIN}:invoice"
    requires_auth = True

    async def get(self, request: web.Request, invoice_id_hash: str) -> web.Response:
        """Return an invoice PDF as an attachment."""

        try:
            hass: HomeAssistant = request.app["hass"]
            runtime = first_runtime_data(hass)
            invoice = _invoice_by_hash(
                runtime.coordinator.data.invoices if runtime.coordinator.data else [],
                invoice_id_hash,
            )
            document = await runtime.client.async_get_invoice_document(invoice_id_hash)
            async with runtime.client.session.get(document.url) as response:
                response.raise_for_status()
                content = await response.read()
                content_type = response.headers.get("content-type", "application/pdf").split(";", 1)[0] or "application/pdf"
        except (ClientError, OctopusSpainError, TimeoutError) as err:
            raise web.HTTPBadGateway(reason="Invoice document is not available") from err
        except HomeAssistantError as err:
            raise web.HTTPNotFound(reason="Octopus Spain is not configured") from err

        return web.Response(
            body=content,
            content_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{_invoice_filename(invoice, invoice_id_hash)}"',
                "Cache-Control": "no-store",
            },
        )


def _invoice_by_hash(invoices: list[dict[str, Any]], invoice_id_hash: str) -> dict[str, Any]:
    """Find a redacted invoice by its stable hash."""

    return next(
        (invoice for invoice in invoices if invoice.get("invoice_id_hash") == invoice_id_hash),
        {},
    )


def _invoice_filename(invoice: dict[str, Any], invoice_id_hash: str) -> str:
    """Return a browser-safe invoice PDF filename."""

    label = invoice.get("period_label") or invoice.get("label") or invoice_id_hash
    filename = _SAFE_FILENAME.sub("_", f"octopus_spain_factura_{label}").strip("._-")
    return f"{filename or 'octopus_spain_factura'}.pdf"
