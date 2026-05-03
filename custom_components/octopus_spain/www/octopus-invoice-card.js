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
      const href = `/api/octopus_spain/invoice/${encodeURIComponent(invoice.invoice_id_hash || "")}`;
      return `
        <a
          class="invoice-row ${available ? "" : "disabled"}"
          href="${available ? href : "#"}"
          download
          aria-disabled="${available ? "false" : "true"}"
        >
          <ha-icon icon="${available ? "mdi:file-document-outline" : "mdi:file-document-remove-outline"}"></ha-icon>
          <span class="invoice-text">
            <span class="primary">${label}</span>
            <span class="secondary">${period}</span>
          </span>
          <span class="download-icon" title="${available ? "Descargar PDF" : "PDF no disponible"}">
            <ha-icon icon="mdi:download"></ha-icon>
          </span>
        </a>
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
          min-height: 56px;
          border-radius: 8px;
          padding: 4px 0;
          color: var(--primary-text-color);
          text-decoration: none;
        }
        .invoice-row:hover {
          background: var(--secondary-background-color);
        }
        .invoice-row.disabled {
          pointer-events: none;
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
        button,
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
        button:hover:not(:disabled) {
          background: var(--divider-color);
        }
        button:disabled {
          color: var(--disabled-text-color);
          cursor: default;
        }
        .empty {
          padding: 8px 16px 18px;
        }
      </style>
    `;

    this.querySelector(".refresh-button")?.addEventListener("click", () => this.refreshInvoices());
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

customElements.define("octopus-invoice-card", OctopusInvoiceCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "octopus-invoice-card",
  name: "Octopus invoice card",
  description: "Download Octopus Energy Spain invoice PDFs from Lovelace.",
});
