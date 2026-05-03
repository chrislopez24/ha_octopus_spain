# Octopus Energy Spain para Home Assistant

Integración custom para Home Assistant compatible con HACS. Conecta con Octopus Energy España mediante la API GraphQL usada por Kraken y expone datos de cuenta, tarifa, facturas y consumo como entidades y servicios.

> Estado: versión `0.0.8`. La API de Octopus Spain no es pública ni versionada para terceros, así que algún campo puede cambiar.

## Qué incluye

- Tarifa, precios de energía/potencia y compensación de excedentes.
- Saldo eléctrico, créditos Sun Club y créditos referral.
- Ventana Sun Club 12:00-18:00 Europe/Madrid.
- Facturas recientes, con PDF solo bajo demanda y card Lovelace opcional para descargar las últimas 12.
- Consumo diario/horario, días completos disponibles y series para dashboards.
- Coste real si Octopus lo devuelve y coste estimado cuando no existe coste API.

La integración no crea dashboards ni modifica el panel de energía de Home Assistant. Los datos se exponen como sensores, atributos y servicios para usarlos en Lovelace, automatizaciones o scripts.

## Instalación

1. En HACS, abre **Integrations**.
2. Menú de tres puntos → **Custom repositories**.
3. Añade este repositorio: `https://github.com/chrislopez24/ha_octopus_spain`.
4. Categoría: **Integration**.
5. Instala **Octopus Energy Spain**.
6. Reinicia Home Assistant.
7. Añade la integración desde **Settings → Devices & services → Add integration**.

## Configuración

La configuración es solo por UI, sin YAML. Se solicitan email y contraseña de Octopus Energy Spain.

Home Assistant guarda esas credenciales en la entrada de configuración. El token temporal de Kraken se mantiene en memoria y se renueva cuando hace falta. No se guardan tokens, URLs firmadas, CUPS, números de cuenta ni IDs crudos en estados o atributos.

## Entidades principales

Sensores:

- `Tarifa`, `Código de tarifa`, `Tarifa válida hasta`.
- `Precio base energía`, `Precio actual energía`, `Precio potencia periodo 1/2`, `Compensación excedentes`.
- `Saldo crédito`, `Créditos Sun Club`, `Créditos referral`.
- `Última factura`, `Emisión última factura`, `Inicio/Fin periodo última factura`, si Octopus devuelve esos campos.
- `Facturas`, con atributo `recent_invoices` y referencias redacted.
- `Consumo últimos 7/31 días`, `Coste estimado últimos 7/31 días`, `Consumo último día completo`, `Coste API último día completo`, `Coste estimado último día completo`.
- Consumo plano por periodos `Punta`, `Llano`, `Valle` y `Total` para último día completo y mes actual, pensado para gráficas de barras.
- Coste estimado del mes actual y medias diarias de consumo/coste de 7 y 31 días.
- `Puntos de medición` y `Series de medición`.

Binary sensor:

- `Ventana Sun Club`.

## Servicios

Servicios con respuesta:

- `octopus_spain.get_invoices`: devuelve facturas recientes sin URLs firmadas.
- `octopus_spain.get_invoice_document`: devuelve una URL temporal firmada para el PDF de una factura, usando `invoice_id_hash` del sensor `Facturas`.
- `octopus_spain.get_latest_invoice_document`: devuelve bajo demanda el PDF de la factura más reciente.
- `octopus_spain.get_invoice_document_by_index`: devuelve bajo demanda el PDF de una factura usando el `index` de `recent_invoices`.
- `octopus_spain.get_measurements`: devuelve mediciones por rango en `DAY_INTERVAL` o `HOUR_INTERVAL`.

Ejemplo para obtener el PDF de una factura:

```yaml
service: octopus_spain.get_invoice_document
data:
  invoice_id_hash: "abc123def456"
```

La URL del PDF puede dar acceso a una factura y debe tratarse como sensible. No se persiste como atributo de entidad.

## Card de facturas

La integración sirve una card Lovelace propia en:

```text
/octopus_spain/octopus-invoice-card.js
```

Para forzar refresco del recurso tras actualizar, puedes añadir una query de versión en Lovelace: `/octopus_spain/octopus-invoice-card.js?v=0.0.8`.

Añade ese recurso como **JavaScript module** en Lovelace y usa:

```yaml
type: custom:octopus-invoice-card
entity: sensor.octopus_energy_spain_facturas
title: Facturas Octopus
limit: 12
```

La card muestra `recent_invoices` y descarga cada PDF a través de Home Assistant en `/api/octopus_spain/invoice/{invoice_id_hash}`. El endpoint obtiene la URL firmada bajo demanda, descarga el PDF y lo devuelve como adjunto; la URL firmada no queda expuesta en el estado ni en la card.

## Documentación técnica

- [docs/octopus-spain-graphql-api.md](docs/octopus-spain-graphql-api.md): operaciones GraphQL, mapeos y servicios.
- [docs/octopus-spain-graphql-integration.md](docs/octopus-spain-graphql-integration.md): notas históricas de diseño.
- [docs/octopus-spain-har-operation-catalog.md](docs/octopus-spain-har-operation-catalog.md): catálogo de operaciones observadas.

## Limitaciones

- La API de Octopus Spain es privada y puede cambiar.
- La selección de cuenta es automática y usa la primera cuenta eléctrica usable.
- Los sensores de última factura pueden quedar no disponibles si Octopus no devuelve `statementsWithDetails`.
- El coste estimado no incluye potencia, impuestos ni ajustes finales de factura.

## Desarrollo

Validaciones básicas:

```bash
rtk python3 -m compileall custom_components tools
rtk python3 -m pytest -q
```

La versión se declara en `custom_components/octopus_spain/manifest.json`. Para publicar una nueva versión: actualiza `manifest.json`, actualiza `CHANGELOG.md`, crea un tag `vX.Y.Z` y publícalo.
