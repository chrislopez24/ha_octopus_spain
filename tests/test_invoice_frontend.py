from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1]
PACKAGE = types.ModuleType("custom_components.octopus_spain")
PACKAGE.__path__ = [str(ROOT / "custom_components" / "octopus_spain")]
sys.modules.setdefault("custom_components.octopus_spain", PACKAGE)


class _FakeHomeAssistantView:
    pass


homeassistant = types.ModuleType("homeassistant")
components = types.ModuleType("homeassistant.components")
http_mod = types.ModuleType("homeassistant.components.http")
http_mod.HomeAssistantView = _FakeHomeAssistantView
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
exceptions = types.ModuleType("homeassistant.exceptions")
exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
services_mod = types.ModuleType("custom_components.octopus_spain.services")
services_mod.first_runtime_data = lambda _hass: None
services_mod.runtime_data_for_invoice_hash = lambda _hass, _invoice_id_hash: None

sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.components", components)
sys.modules.setdefault("homeassistant.components.http", http_mod)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.exceptions", exceptions)
sys.modules.setdefault("custom_components.octopus_spain.services", services_mod)


def load_module(name: str):
    spec = spec_from_file_location(
        f"custom_components.octopus_spain.{name}",
        ROOT / "custom_components" / "octopus_spain" / f"{name}.py",
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_invoice_download_endpoint_is_authenticated_home_assistant_api_route():
    load_module("const")
    load_module("model")
    load_module("api")
    frontend = load_module("frontend")

    assert frontend.OctopusSpainInvoiceDownloadView.url == "/api/octopus_spain/invoice/{invoice_id_hash}"
    assert frontend.OctopusSpainInvoiceDownloadView.name == "api:octopus_spain:invoice"
    assert frontend.OctopusSpainInvoiceDownloadView.requires_auth is True


def test_invoice_download_filename_is_pdf_and_safe():
    frontend = sys.modules.get("custom_components.octopus_spain.frontend") or load_module("frontend")

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
