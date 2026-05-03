class OctopusInvoiceCard extends HTMLElement {
  static getStubConfig() {
    return {
      entity: "sensor.octopus_energy_spain_facturas",
      title: "Facturas Octopus",
      limit: 12,
    };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("entity is required");
    }

    this.config = {
      title: "Facturas Octopus",
      limit: 12,
      ...config,
    };
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return Math.max(3, Math.min(Number(this.config?.limit || 12) + 1, 13));
  }

  getGridOptions() {
    const rows = Math.max(3, Math.min(Number(this.config?.limit || 12) + 1, 13));
    return {
      columns: 12,
      min_columns: 6,
      rows,
      min_rows: 3,
    };
  }

  notify(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message },
      bubbles: true,
      composed: true,
    }));
  }

  invoices() {
    const state = this._hass?.states?.[this.config.entity];
    return Array.isArray(state?.attributes?.recent_invoices)
      ? state.attributes.recent_invoices
      : [];
  }

  async refreshInvoices() {
    if (!this._hass || !this.config?.entity) {
      return;
    }

    try {
      await this._hass.callService("homeassistant", "update_entity", {
        entity_id: this.config.entity,
      });
    } catch (error) {
      this.notify(error?.message || "No se pudieron refrescar las facturas.");
    }
  }

  async downloadInvoice(invoice) {
    if (!invoice?.invoice_id_hash) {
      this.notify("La factura no tiene identificador de descarga.");
      return;
    }

    try {
      const response = await this.authenticatedFetch(
        `/api/octopus_spain/invoice/${encodeURIComponent(invoice.invoice_id_hash)}`,
      );
      if (!response.ok) {
        throw new Error(`No se pudo generar el PDF de la factura (${response.status}).`);
      }
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.toLowerCase().startsWith("application/pdf")) {
        throw new Error("Octopus no devolvio un PDF.");
      }

      const blob = await response.blob();
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = filenameFromResponse(response) || filenameFromInvoice(invoice);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      this.notify(error?.message || "No se pudo descargar la factura.");
    }
  }

  authenticatedFetch(url) {
    if (this._hass?.fetchWithAuth) {
      return this._hass.fetchWithAuth(url);
    }

    const token = this._hass?.auth?.data?.access_token;
    return fetch(url, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined);
  }

  render() {
    if (!this.config || !this._hass) {
      return;
    }

    const entityState = this._hass.states?.[this.config.entity];
    const invoices = this.invoices().slice(0, Number(this.config.limit || 12));
    const rows = invoices.map((invoice) => {
      const available = Boolean(invoice.document_available && invoice.invoice_id_hash);
      const label = escapeHtml(invoice.label || `Factura #${Number(invoice.index || 0) + 1}`);
      const period = escapeHtml(invoice.period_label || "Periodo no disponible");
      const index = Number(invoice.index || 0);
      return `
        <button
          class="invoice-row ${available ? "" : "disabled"}"
          type="button"
          data-invoice-index="${index}"
          aria-disabled="${available ? "false" : "true"}"
          ${available ? "" : "disabled"}
        >
          <ha-icon icon="${available ? "mdi:file-document-outline" : "mdi:file-document-remove-outline"}"></ha-icon>
          <span class="invoice-text">
            <span class="primary">${label}</span>
            <span class="secondary">${period}</span>
          </span>
          <span class="download-icon" title="${available ? "Descargar PDF" : "PDF no disponible"}">
            <ha-icon icon="mdi:download"></ha-icon>
          </span>
        </button>
      `;
    }).join("");

    this.innerHTML = `
      <ha-card>
        <div class="header">
          <div>
            <div class="title">${escapeHtml(this.config.title)}</div>
            <div class="subtitle">${entityState ? `${invoices.length} facturas recientes` : "Entidad no encontrada"}</div>
          </div>
          <button class="refresh-button" type="button" title="Refrescar">
            <ha-icon icon="mdi:refresh"></ha-icon>
          </button>
        </div>
        ${rows ? `<ul>${rows}</ul>` : "<div class=\"empty\">No hay facturas disponibles.</div>"}
      </ha-card>
      <style>
        ha-card {
          overflow: hidden;
        }
        .header,
        .invoice-row {
          display: grid;
          align-items: center;
        }
        .header {
          grid-template-columns: 1fr 40px;
          gap: 12px;
          padding: 16px 16px 8px;
        }
        .title {
          font-size: 16px;
          font-weight: 600;
          line-height: 22px;
        }
        .subtitle,
        .secondary,
        .empty {
          color: var(--secondary-text-color);
          font-size: 12px;
          line-height: 18px;
        }
        ul {
          list-style: none;
          margin: 0;
          padding: 0 8px 8px;
        }
        .invoice-row {
          grid-template-columns: 40px 1fr 40px;
          gap: 8px;
          width: 100%;
          min-height: 56px;
          border-radius: 8px;
          padding: 4px 0;
          border: 0;
          background: transparent;
          color: var(--primary-text-color);
          font: inherit;
          text-align: left;
          text-decoration: none;
          cursor: pointer;
        }
        .invoice-row:hover {
          background: var(--secondary-background-color);
        }
        .invoice-row.disabled {
          cursor: default;
          opacity: 0.55;
        }
        .invoice-row > ha-icon {
          color: var(--info-color, #2196f3);
          justify-self: center;
        }
        .invoice-text {
          min-width: 0;
          display: grid;
          gap: 1px;
        }
        .primary,
        .secondary {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .refresh-button,
        .download-icon {
          width: 40px;
          height: 40px;
          display: grid;
          place-items: center;
          border: 0;
          border-radius: 8px;
          background: transparent;
          color: var(--primary-text-color);
          cursor: pointer;
        }
        .refresh-button:hover:not(:disabled) {
          background: var(--divider-color);
        }
        .refresh-button:disabled {
          color: var(--disabled-text-color);
          cursor: default;
        }
        .empty {
          padding: 8px 16px 18px;
        }
      </style>
    `;

    this.querySelector(".refresh-button")?.addEventListener("click", () => this.refreshInvoices());
    for (const row of this.querySelectorAll(".invoice-row")) {
      row.addEventListener("click", () => {
        const index = Number(row.dataset.invoiceIndex || 0);
        const invoice = this.invoices().find((item) => Number(item.index || 0) === index);
        this.downloadInvoice(invoice);
      });
    }
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[character]));
}

function filenameFromResponse(response) {
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/i);
  return match?.[1] || "";
}

function filenameFromInvoice(invoice) {
  const label = invoice?.period_label || invoice?.label || invoice?.invoice_id_hash || "factura";
  const safeLabel = String(label).replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^[._-]+|[._-]+$/g, "");
  return `octopus_spain_factura_${safeLabel || "factura"}.pdf`;
}

customElements.define("octopus-invoice-card", OctopusInvoiceCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "octopus-invoice-card",
  name: "Octopus invoice card",
  description: "Download Octopus Energy Spain invoice PDFs from Lovelace.",
});
