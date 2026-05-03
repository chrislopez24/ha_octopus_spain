# Octopus Energy Spain para Home Assistant

Integración custom para Home Assistant compatible con HACS. Conecta con Octopus Energy España mediante el endpoint GraphQL directo de Kraken observado para España y expone la información útil como entidades, atributos y servicios seguros.

> Estado: versión `0.0.2`. La API de Octopus Spain no es pública ni versionada para terceros; algunos campos pueden cambiar.

## Alcance

La integración está pensada para mostrar en Home Assistant los datos que ofrece la web/API de Octopus Spain de forma limpia y amigable:

- tarifa, código de producto, validez y precios;
- estimación de ventana Sun Club;
- saldo/crédito eléctrico;
- facturas recientes y documento PDF solo bajo demanda;
- créditos agrupados por `reasonCode` y convertidos a EUR;
- resumen seguro de dispositivos y referidos;
- consumo diario/horario, días completos disponibles y series preparadas para gráficas Lovelace/ApexCharts;
- coste API si Octopus lo devuelve y coste estimado de energía si no lo devuelve.

No instala ni modifica dashboards automáticamente. Tampoco guarda tokens, URLs firmadas ni identificadores crudos en estados o atributos.

## Versionado

La versión de la integración se declara en `custom_components/octopus_spain/manifest.json`. La primera versión pública es `0.0.1`; la versión actual es `0.0.2`.

Para publicar nuevas versiones en HACS se debe:

1. Actualizar `manifest.json`.
2. Actualizar `CHANGELOG.md`.
3. Crear un tag Git con el mismo número, por ejemplo `v0.0.2`.
4. Publicar/pushear el tag al repositorio.

## Instalación con HACS como custom repository

1. En HACS, abre **Integrations**.
2. Menú de tres puntos → **Custom repositories**.
3. Añade este repositorio público: `https://github.com/chrislopez24/ha_octopus_spain`.
4. Categoría: **Integration**.
5. Instala **Octopus Energy Spain**.
6. Reinicia Home Assistant.
7. Añade la integración desde **Settings → Devices & services → Add integration**.

## Configuración

La integración solo usa configuración por UI (`config_flow.py`). No hay configuración YAML.

Se solicitan:

- Email de Octopus Energy Spain.
- Contraseña de Octopus Energy Spain.

Home Assistant guarda estas credenciales en la entrada de configuración, que es el lugar estándar para integraciones con config flow. El token temporal de Kraken se mantiene solo en memoria y se renueva cuando hace falta. No se guardan tokens ni URLs firmadas de facturas en estados, atributos ni opciones.

## Entidades

La integración crea un dispositivo lógico de cuenta Octopus con identificadores hash, sin exponer número de cuenta ni CUPS.

Sensores principales:

- Tarifa.
- Código de tarifa.
- Fecha de validez de tarifa.
- Precio base de energía.
- Precio actual estimado de energía.
- Precio de potencia periodo 1.
- Precio de potencia periodo 2.
- Compensación de excedentes.
- Saldo/crédito eléctrico.
- Importe/fecha/periodo de última factura si `accountBillingInfo` lo expone; si no, quedan no disponibles hasta que Octopus los devuelva.
- Sensor `Facturas` con atributo `recent_invoices` redacted.
- Créditos Sun Club.
- Créditos referral.
- Consumo último día completo disponible.
- Coste API último día completo disponible, solo si Octopus lo expone.
- Coste estimado último día completo disponible.
- Consumo últimos 7 días completos.
- Coste estimado últimos 7 días.
- Consumo últimos 31 días completos.
- Coste estimado últimos 31 días.
- Puntos de medición disponibles.
- Sensor `Series de medición` con atributos `series`, `period_series`, `hourly_period_series` y `estimated_cost_series_by_date`.
- Binary sensor `Ventana Sun Club` para 12:00-18:00 Europe/Madrid.

El precio actual estimado aplica el descuento regular documentado de Sun Club de 45% entre 12:00 y 18:00 si existe precio base. Los descuentos puntuales de hasta 100% no se estiman salvo que Octopus los exponga por API.

## Calidad del dato de consumo y coste

La integración distingue entre datos reales y estimados:

- `Consumo ...`: kWh devueltos por Octopus.
- `Coste API ...`: coste devuelto por Octopus en `metaData.statistics.costInclTax`, cuando existe.
- `Coste estimado ...`: cálculo local de energía usando consumo horario, tarifa base y descuento regular Sun Club. No incluye potencia, impuestos ni ajustes finales de factura.

Los sensores diarios se basan en **días completos disponibles**. La integración pide ventanas alineadas a medianoche de Madrid y filtra puntos parciales para evitar mostrar como “día” un dato incompleto. Los atributos indican `latest_period_start`, `latest_period_end`, `api_cost_available`, `cost_preference` y fuente del coste estimado.

## Series para gráficas Lovelace / ApexCharts

El sensor `Series de medición` expone:

```json
{
  "series": {
    "daily": [
      {"date": "YYYY-MM-DD", "kwh": 8.954, "cost_eur": null}
    ],
    "weekly": [
      {"period": "YYYY-W18", "kwh": 69.748, "cost_eur": null}
    ],
    "monthly": [
      {"period": "YYYY-MM", "kwh": 452.224, "cost_eur": null}
    ],
    "yearly": [
      {"period": "YYYY", "kwh": 452.224, "cost_eur": null}
    ]
  },
  "period_series": {
    "daily": [
      {"date": "YYYY-MM-DD", "total_kwh": 8.954, "punta_kwh": 3.343, "llano_kwh": 2.755, "valle_kwh": 2.856}
    ],
    "monthly": [
      {"period": "YYYY-MM", "total_kwh": 443.608, "punta_kwh": 134.72, "llano_kwh": 123.442, "valle_kwh": 185.446}
    ]
  },
  "hourly_period_series": {
    "daily": [],
    "monthly": []
  },
  "estimated_cost_series_by_date": {
    "YYYY-MM-DD": 1.031635
  }
}
```

`period_series` y `hourly_period_series` están pensadas para barras apiladas tipo Punta/Llano/Valle en tarjetas custom como `apexcharts-card`. `estimated_cost_series_by_date` permite pintar una línea o barras de coste estimado diario.

## Servicios

Todos los servicios están pensados para respuesta bajo demanda. Usa herramientas de Home Assistant que soporten `return_response` cuando necesites leer la respuesta.

### `octopus_spain.get_invoice_document`

Devuelve bajo demanda una URL temporal firmada para una factura ya vista en el caché en memoria de la integración.

```yaml
service: octopus_spain.get_invoice_document
data:
  invoice_id_hash: "abc123def456"
```

La URL devuelta puede dar acceso al PDF de una factura y debe tratarse como sensible. No se persiste como atributo de entidad.

### `octopus_spain.get_invoices`

Devuelve una lista redacted de facturas recientes, sin URLs firmadas.

```yaml
service: octopus_spain.get_invoices
data:
  limit: 12
```

### `octopus_spain.get_measurements`

Devuelve puntos de consumo/coste por rango para gráficas o automatizaciones. Soporta intervalos diarios y horarios.

```yaml
service: octopus_spain.get_measurements
data:
  start_date: "2026-04-01"
  end_date: "2026-05-01"
  frequency: DAY_INTERVAL
```

Con `DAY_INTERVAL`, la respuesta incluye rollups de días completos, series, desglose Punta/Llano/Valle y coste estimado si hay tarifa base. Con `HOUR_INTERVAL`, devuelve la serie horaria raw y los agregados horarios.

## Privacidad y seguridad

Este repositorio está preparado para ser público. Por eso:

- No se incluyen HARs en Git (`*.har` está ignorado).
- No se deben commitear emails, tokens, cookies, CUPS, números de cuenta, direcciones, importes reales, PDFs ni URLs firmadas.
- Los IDs sensibles se convierten en hashes cortos estables para `unique_id`, device identifiers y facturas.
- Las respuestas GraphQL crudas no se registran en logs.
- Diagnostics redacta credenciales y selectores internos sensibles.
- Las URLs de factura solo se devuelven mediante `get_invoice_document` y no se guardan en estado.

## Limitaciones conocidas

- API privada/no documentada oficialmente por Octopus Energy Spain.
- La selección de cuenta/propiedad es automática y toma la primera cuenta eléctrica usable. La selección manual para múltiples cuentas queda para una fase posterior.
- `accountBillingInfo(...).statementsWithDetails(first: 1)` puede responder sin errores pero sin edges; los sensores oportunistas de última factura quedarán no disponibles hasta que Octopus devuelva esos datos.
- La disponibilidad de coste real depende de que Octopus devuelva `costInclTax` en `metaData.statistics`.
- El coste estimado es informativo para dashboards/automatizaciones; no pretende igualar la factura final.
- La validación completa de entidades requiere cargar la integración en una instancia real de Home Assistant.

## Dashboard

No es requisito crear dashboard desde la integración. Puedes usar tarjetas nativas como `entities`, `tile` o `history-graph`, y tarjetas custom si ya las tienes instaladas.

Ideas de uso:

- `entities` o `tile` para tarifa, precio actual, saldo, créditos y facturas.
- `history-graph` para sensores de precio, consumo y coste estimado.
- `apexcharts-card` con el atributo `hourly_period_series.daily` para barras apiladas Punta/Llano/Valle.
- `apexcharts-card` con `series.daily` para consumo diario y `estimated_cost_series_by_date` para coste estimado.
- Servicio `octopus_spain.get_measurements` para scripts, automatizaciones o paneles personalizados que pidan rangos concretos bajo demanda.

## Desarrollo local

Validaciones básicas:

```bash
rtk python3 -m compileall custom_components tools
rtk python3 -m pytest -q
```

Pruebas live con `.env` local ignorado por Git:

```bash
rtk python3 tools/catalog_har_operations.py
rtk python3 tools/probe_octopus_endpoints.py
rtk python3 tools/verify_ha_mapping.py
rtk python3 tools/smoke_test_api.py
```

## Estructura HACS

```text
custom_components/octopus_spain/
  __init__.py
  api.py
  binary_sensor.py
  config_flow.py
  const.py
  coordinator.py
  diagnostics.py
  entity.py
  graphql_queries.py
  manifest.json
  mappers.py
  measurements.py
  model.py
  redaction.py
  sensor.py
  service_helpers.py
  services.py
  services.yaml
  strings.json
  translations/es.json
hacs.json
README.md
```
