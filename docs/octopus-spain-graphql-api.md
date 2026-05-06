# Octopus Spain GraphQL API

Ultima revision: 2026-05-04.

Este documento resume solo lo necesario para mantener la integracion `octopus_spain`. Octopus Energy Spain usa una API GraphQL privada de Kraken; no hay contrato publico ni versionado para terceros.

## Privacidad

No guardar ni publicar:

- email, password, cookies o tokens;
- numero de cuenta, ledger, property ID o CUPS;
- direccion, NIF, telefono o datos personales;
- IDs crudos de factura;
- PDFs o URLs firmadas.

La integracion usa hashes cortos estables para referencias visibles. Las URLs firmadas de facturas solo se obtienen bajo demanda mediante servicio o endpoint autenticado de Home Assistant.

## Endpoint y autenticacion

Endpoint probado:

```text
https://api.oees-kraken.energy/v1/graphql/
```

Operacion de login:

```graphql
mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
    refreshToken
    refreshExpiresIn
  }
}
```

El cliente mantiene JWT y refresh token solo en memoria. Antes de cada query refresca el JWT si esta cerca de caducar; si Kraken devuelve error de auth/JWT, reautentica y reintenta una vez.

## Flujo de cuenta

La seleccion inicial usa:

- `ViewerAccount`: obtiene cuentas, ledgers y saldo.
- `ViewerProperty`: obtiene propiedad y contrato activo sin consultar CUPS.

Mapeo interno:

| GraphQL | Uso interno | Exposicion |
| --- | --- | --- |
| `viewer.accounts.number` | `account_number` | nunca crudo |
| `ledgers.number` | facturas y creditos | nunca crudo |
| `ledgers.ledgerType` | elegir electricidad | no sensible |
| `ledgers.balance` | `credit_balance` | EUR |
| `properties.id` | mediciones | nunca crudo |
| `activeAgreement.id` | query `Agreement` | nunca crudo |

## Operaciones usadas por la integracion

| Operacion | Metodo | Uso |
| --- | --- | --- |
| `Agreement` | `async_agreement` | tarifa, precios, validez y excedentes |
| `BillingInfo` | `async_billing_info` | saldo y ultima factura si Kraken la devuelve |
| `Bills` | `async_bills` | lista redacted de facturas recientes |
| `Bill` | `async_get_invoice_document` | resolver PDF bajo demanda |
| `AccountCreditsQuery` | `async_credits` | creditos agregados por `reasonCode` |
| `getAccountMeasurements` | `async_measurements` | consumo diario/horario y coste si existe |
| `SolarWallet` | `async_solar_wallet` | estado Solar Wallet, credito disponible y relaciones redacted |
| `KrakenFlex` | `async_intelligent_go` | tipos elegibles y dispositivo KrakenFlex registrado |
| `KrakenFlexDispatches` | `async_intelligent_go` | cargas planificadas cuando existe `krakenflexDeviceId` |

Las queries exploratorias para `Viewer`, `LinkedSupplyPointAccounts`, `getDevices` y `AccountReferrals` se conservan solo para probes manuales en `tools/`; no forman parte del polling normal porque no alimentan entidades ni servicios actuales.

## Mapeo Home Assistant

Tarifa:

- `tariff_name`, `tariff_code`, `tariff_valid_to`;
- `base_energy_price`, `current_energy_price`;
- `power_price_period_1`, `power_price_period_2`, `surplus_rate`.

Facturas:

- `last_invoice_*` si `BillingInfo` devuelve `statementsWithDetails`;
- sensor `invoices` con atributo `recent_invoices`;
- descarga PDF mediante `/api/octopus_spain/invoice/{invoice_id_hash}`.

Creditos:

- `credit_balance`;
- `sun_club_credits`;
- `referral_credits`.

Solar Wallet:

- `has_solar_wallet`;
- `solar_wallet_available_credit`, `solar_wallet_credit_left`;
- relaciones con `target_ledger_hash`, fechas de validez y presencia de nombre, sin exponer ledger crudo.

Intelligent Go / KrakenFlex:

- tipos de dispositivo elegibles;
- dispositivo registrado sin exponer `krakenflexDeviceId`;
- estado, proveedor, vehiculo/cargador, limite de SOC y cargas planificadas si Kraken las devuelve.

Estos campos estan mapeados a partir de introspection y pruebas con una cuenta sin Solar Wallet ni Intelligent Go activo. El soporte debe considerarse experimental hasta validar payloads reales de clientes que tengan esas funciones contratadas.

Mediciones:

- consumo ultimo dia completo, ultimos 7 dias y ultimos 31 dias;
- coste API cuando `metaData.statistics.costInclTax.estimatedAmount` existe;
- coste estimado desde consumo horario y tarifa base cuando no hay coste API;
- series `daily`, `weekly`, `monthly`, `yearly`;
- series por periodos `punta`, `llano`, `valle` para dashboards.

## Sun Club

No se ha confirmado un campo GraphQL que indique precio efectivo instantaneo. La integracion calcula `current_energy_price` localmente:

- fuera de 12:00-18:00 Europe/Madrid: precio base;
- dentro de 12:00-18:00 Europe/Madrid: precio base con descuento Sun Club.

El coordinator refresca en limites horarios de Madrid para reflejar entradas y salidas de esa ventana.

## Desarrollo

Comandos habituales:

```bash
rtk python3 -m compileall custom_components tools
rtk python3 -m pytest -q
rtk python3 tools/probe_octopus_endpoints.py
rtk python3 tools/verify_ha_mapping.py
```

Los probes requieren `.env` local y no deben commitear salidas generadas.
