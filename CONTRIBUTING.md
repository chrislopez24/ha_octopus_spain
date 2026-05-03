# Contributing / desarrollo local

## Privacidad

Este repositorio está pensado para ser público. No incluyas nunca:

- `.env` con credenciales;
- HARs;
- tokens/cookies;
- número de cuenta, CUPS, dirección, email, teléfono, NIF;
- importes reales;
- PDFs o URLs firmadas.

Los scripts de `tools/` imprimen solo estados, hashes, contadores y presencia de campos.

## Setup de pruebas live

Copia `.env.example` a `.env` y rellena:

```env
OCTOPUS_EMAIL=
OCTOPUS_PASSWORD=
```

No commitees `.env`.

## Validaciones

```bash
rtk python3 -m compileall custom_components tools
rtk python3 -m pytest -q
rtk python3 tools/catalog_har_operations.py
rtk python3 tools/probe_octopus_endpoints.py
rtk python3 tools/verify_ha_mapping.py
```

`tools/probe_octopus_endpoints.py` genera `docs/octopus-spain-api-probe-results.json`, que está ignorado por Git porque depende de la cuenta local aunque esté redacted.

## Arquitectura

- `custom_components/octopus_spain/graphql_queries.py`: documentos GraphQL nombrados.
- `custom_components/octopus_spain/api.py`: cliente GraphQL, autenticación, caché temporal de facturas y métodos de dominio.
- `custom_components/octopus_spain/mappers.py`: mapeo de payloads GraphQL a datos redacted para Home Assistant.
- `custom_components/octopus_spain/measurements.py`: helpers puros para rollups y series de consumo/coste aptas para gráficas.
- `custom_components/octopus_spain/coordinator.py`: polling HA.
- `custom_components/octopus_spain/services.py`: servicios con respuesta bajo demanda.
- `tools/`: probes live y catálogo HAR sin datos sensibles.
