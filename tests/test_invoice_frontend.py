from pathlib import Path

from custom_components.octopus_spain import frontend


ROOT = Path(__file__).parents[1]


def test_invoice_download_endpoint_is_authenticated_home_assistant_api_route():
    assert frontend.OctopusSpainInvoiceDownloadView.url == "/api/octopus_spain/invoice/{invoice_id_hash}"
    assert frontend.OctopusSpainInvoiceDownloadView.name == "api:octopus_spain:invoice"
    assert frontend.OctopusSpainInvoiceDownloadView.requires_auth is True


def test_invoice_download_filename_is_pdf_and_safe():
    result = frontend._invoice_filename({"period_label": "2026-04-01 a 2026-05-01"}, "abc123")

    assert result == "octopus_spain_factura_2026-04-01_a_2026-05-01.pdf"


def test_invoice_card_defaults_to_twelve_downloadable_invoice_rows():
    card = (ROOT / "custom_components/octopus_spain/www/octopus-invoice-card.js").read_text(encoding="utf-8")

    assert "limit: 12" in card
    assert "/api/octopus_spain/invoice/" in card
    assert 'type: "auth/sign_path"' in card
    assert "fetchInvoice(" in card
    assert "fetchWithAuth" in card
    assert "authenticatedFetch(" in card
    assert "download" in card
    assert "window.open" not in card
