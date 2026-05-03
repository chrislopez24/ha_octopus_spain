# Octopus Spain GraphQL integration — investigación histórica

Fecha de revisión: 2026-05-03.

Este documento queda como nota histórica de investigación inicial sobre la web GraphQL de Octopus Spain. La fuente original fueron HARs locales tratados como material sensible. Este archivo no debe contener email, password, cookies, tokens, número de cuenta, CUPS, dirección, datos personales, importes reales, PDFs ni URLs firmadas.

## Decisión actual

La integración `octopus_spain` se implementa como integración custom de Home Assistant compatible con HACS y centrada en exponer de forma segura lo que ofrece la web/API de Octopus Spain:

- autenticación Kraken con email/password desde config flow;
- selección interna de cuenta, ledger, propiedad y contrato activo;
- sensores de tarifa, precios, saldo/crédito, facturas, consumos, costes cuando estén disponibles y series agregadas;
- servicios con respuesta para facturas, documentos de factura y mediciones;
- resúmenes seguros de dispositivos, referidos y créditos;
- redacción estricta de identificadores y URLs sensibles.

## Fuera de alcance

Queda fuera de alcance cualquier integración con almacenamiento histórico especial de Home Assistant o paneles energéticos específicos. Los datos de consumo y coste se exponen como sensores, atributos y servicios para que el usuario los pinte en Lovelace con tarjetas nativas o custom.

## Operaciones GraphQL útiles confirmadas

- `obtainKrakenToken` para autenticación.
- `ViewerAccount` para cuenta y ledger eléctrico internos.
- `ViewerProperty` para propiedad y contrato activo sin consultar CUPS.
- `Viewer` safe para resumen de cuenta/suministros sin datos personales.
- `LinkedSupplyPointAccounts` safe para conteos de suministros.
- `Agreement` para tarifa, producto, precios y validez.
- `BillingInfo` para saldo y posible statement reciente, aunque en la cuenta probada no devolvió edges.
- `Bills` para histórico redacted de facturas.
- `Bill` para resolver `pdfUrl` bajo demanda al clicar facturas antiguas.
- `AccountCreditsQuery` para créditos agregados por `reasonCode`.
- `getDevices` para resumen seguro de dispositivos.
- `AccountReferrals` safe para resumen sin URL de referido ni nombres.
- `getAccountMeasurements` para consumos diarios/horarios y coste si Octopus lo devuelve en `metaData.statistics`.

## Modelo Home Assistant resultante

### Entidades

- Tarifa y código.
- Fecha de validez.
- Precio base de energía.
- Precio actual estimado con ventana Sun Club regular.
- Potencia por periodo.
- Compensación de excedentes.
- Saldo/crédito.
- Última factura si `BillingInfo` lo expone.
- Facturas recientes con `invoice_id_hash` y sin URLs.
- Consumo/coste último día, últimos 7 días, últimos 31 días y últimos 365 días.
- Puntos de medición.
- Series agregadas `daily`, `weekly`, `monthly`, `yearly` en atributo `series`.
- Binary sensor de ventana Sun Club.

### Servicios

- `octopus_spain.get_invoice_document`: devuelve URL firmada solo bajo demanda.
- `octopus_spain.get_invoices`: devuelve facturas redacted.
- `octopus_spain.get_measurements`: devuelve puntos, rollups y series por rango y frecuencia.

## Notas de privacidad

- No consultar CUPS si no es imprescindible.
- No exponer números de cuenta, ledger, property IDs, invoice IDs crudos ni URLs firmadas en estados/atributos.
- Usar hashes cortos estables para referencias que deba ver el usuario.
- Mantener token Kraken solo en memoria.
- Diagnostics debe redactar credenciales y selectores internos.
- Los HARs y `.env` son sensibles y están ignorados por Git.

## Documentación viva

La documentación técnica mantenida está en:

- `README.md` para instalación, entidades, servicios y uso en dashboards.
- `docs/octopus-spain-graphql-api.md` para mapeo GraphQL probado y detalles técnicos.
- `CONTRIBUTING.md` para desarrollo local, privacidad y validaciones.
