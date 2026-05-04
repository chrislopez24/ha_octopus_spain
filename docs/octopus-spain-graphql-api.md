# Octopus Spain GraphQL API técnica

Fecha de última prueba: 2026-05-03.

Este documento describe las operaciones GraphQL que usa la integración `octopus_spain` para Home Assistant. Es documentación técnica del componente; no expone una API pública ni valores reales.

## Reglas de privacidad

No guardar ni publicar:

- email, password, cookies o tokens;
- número de cuenta;
- CUPS;
- dirección;
- IDs crudos de factura/ledger/property si pueden identificar una cuenta;
- PDFs o URLs firmadas S3.

En Home Assistant se usan hashes cortos estables para `unique_id`, `device_info` y referencias de facturas. Las URLs firmadas solo se devuelven bajo demanda mediante servicio con respuesta.

## Endpoint y autenticación

Endpoint directo Kraken probado:

```text
https://api.oees-kraken.energy/v1/graphql/
```

Autenticación:

```graphql
mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
    refreshToken
    refreshExpiresIn
  }
}
```

Header posterior:

```text
authorization: <token>
```

El token solo vive en memoria del cliente `OctopusSpainClient`.

La introspection de Kraken Spain muestra que `ObtainJSONWebTokenInput` acepta
`refreshToken`, además de las credenciales iniciales. En prueba live del
2026-05-04:

- el JWT recibido incluye claim `exp` y dura 3600 segundos;
- `obtainKrakenToken` con email/password devuelve `refreshToken`;
- `obtainKrakenToken(input: {refreshToken})` devuelve un JWT nuevo;
- `refreshExpiresIn` se comporta como timestamp Unix absoluto de expiración del
  refresh token.

La integración mantiene tanto el JWT como el refresh token solo en memoria. No
persiste tokens en la entrada de configuración ni en entidades.

## Selección interna de cuenta

La integración hace dos llamadas iniciales:

1. `ViewerAccount` para cuenta, ledgers y saldo.
2. `ViewerProperty` para propiedad y contrato activo.

Mapeo:

| Campo GraphQL | Uso interno | Exposición HA |
| --- | --- | --- |
| `viewer.accounts.number` | `AccountSelection.account_number` | nunca crudo; solo `account_hash` |
| `viewer.accounts.ledgers.number` | `ledger_number` para facturas/créditos | nunca crudo |
| `viewer.accounts.ledgers.ledgerType` | elegir `SPAIN_ELECTRICITY_LEDGER` | no sensible |
| `viewer.accounts.ledgers.balance` | `sensor.credit_balance` | EUR si existe |
| `properties.id` | `property_id` para mediciones | nunca crudo; solo `property_hash` |
| `activeAgreement.id` | query `Agreement` | nunca crudo |

Privacidad: no se consulta CUPS en la query usada por la integración.

## Operaciones GraphQL y mapeo Home Assistant

### `Viewer` safe

Uso:

- Resumen de cuenta/propiedad/suministros.
- Diagnóstico safe.

Se evita usar campos personales que aparecen en HARs, como email, móvil, NIF, dirección o CUPS.

### `LinkedSupplyPointAccounts` safe

Uso:

- Conteos de supply points.
- Base para futura selección de múltiples suministros.

No se exponen direcciones ni IDs crudos.

### `Agreement`

Uso:

- Tarifa.
- Código de producto.
- Validez.
- Precio base energía.
- Precio potencia periodo 1/2.
- Compensación de excedentes.

Sensores:

- `tariff_name`.
- `tariff_code`.
- `tariff_valid_to`.
- `base_energy_price`.
- `current_energy_price`.
- `power_price_period_1`.
- `power_price_period_2`.
- `surplus_rate`.

Sun Club regular se modela con el descuento conocido de 45% de 12:00 a 18:00 Europe/Madrid. Descuentos puntuales se exponen vía créditos si aparecen, pero no se inventan en el precio actual.

### `BillingInfo`

Uso:

- Saldo de ledger eléctrico.
- Sensores oportunistas de última factura si Kraken devuelve `statementsWithDetails`.

Sensores oportunistas:

- `last_invoice_amount`.
- `last_invoice_issued`.
- `last_invoice_period_start`.
- `last_invoice_period_end`.

En la cuenta probada, `statementsWithDetails(first: 1)` devuelve 0 edges. Por tanto estos sensores pueden quedar no disponibles hasta que Octopus devuelva statement. No se eliminan porque pueden empezar a tener valor cerca de la emisión/cierre de factura.

### `Bills`

Uso:

- Histórico compacto de facturas.
- Sensor `invoices`.
- Servicio `get_invoices`.
- Caché temporal en memoria de `invoice_id_hash -> invoice_id/pdfUrl`.

Campos usados:

- `id` / `number` para hash estable.
- `earliestChargeAt` como `period_start`.
- `latestChargeAt` como `period_end`.
- `pdfUrl` solo para caché en memoria, nunca atributo.

Atributo `recent_invoices`:

```json
[
  {
    "invoice_id_hash": "<hash>",
    "period_start": "YYYY-MM-DD",
    "period_end": "YYYY-MM-DD",
    "document_available": true
  }
]
```

### `Bill`

Uso:

- Resolver PDF bajo demanda mediante `invoice_id_hash`.

Servicio:

- `octopus_spain.get_invoice_document`.

Privacidad:

- La URL firmada solo se devuelve en la respuesta del servicio.
- No se guarda en estado ni atributos.

### `AccountCreditsQuery`

Uso:

- Créditos y bonificaciones.
- Agregación dinámica por `reasonCode`.
- Sensores específicos cuando tienen sentido (`SUN_CLUB`, `REFERRAL_REWARD`).

Mapeo importante:

- `amounts.gross` llega en minor units/céntimos.
- `summarize_credits()` divide entre 100 antes de exponer EUR.

Estructura expuesta en atributos:

```json
{
  "reason_code_counts": {"SUN_CLUB": 9},
  "reason_code_amounts": {"SUN_CLUB": 111.5},
  "recent_credits": [
    {"amount": 9.99, "created_at": "YYYY-MM-DD", "reason_code": "SUN_CLUB"}
  ]
}
```

No hay fixtures rígidas de reason codes; si Octopus añade códigos nuevos, quedan agregados en atributos.

### `getDevices`

Uso:

- Resumen safe de dispositivos asociados.

Exposición:

- Conteo, tipos y estados.
- Sin IDs de dispositivo.

### `AccountReferrals` safe

Uso:

- Resumen safe de referidos.

Exposición:

- Conteos y disponibilidad de URL.
- No se expone la URL de referido ni nombres.

### `getAccountMeasurements`

Uso:

- Consumo diario/horario.
- Coste API si `metaData.statistics` lo expone.
- Series y rollups para dashboards/automatizaciones.
- Coste estimado cuando el coste API no existe.

Variables base:

```json
{
  "propertyId": "<internal>",
  "first": 31,
  "startAt": "<ISO Europe/Madrid or UTC>",
  "endAt": "<ISO Europe/Madrid or UTC>",
  "timezone": "Europe/Madrid",
  "utilityFilters": [
    {
      "electricityFilters": {
        "readingDirection": "CONSUMPTION",
        "readingFrequencyType": "DAY_INTERVAL"
      }
    }
  ]
}
```

Para horario se usa `readingFrequencyType: HOUR_INTERVAL`.

#### Calidad del dato diario

Para sensores de consumo diario, el coordinator pide ventanas alineadas a medianoche Europe/Madrid:

- `startAt = YYYY-MM-DDT00:00:00+01/+02`.
- `endAt = YYYY-MM-DDT00:00:00+01/+02`.

Luego `measurements.normalize_measurement_points(..., complete_daily_only=True)` descarta puntos parciales. Esto evita mostrar como “día completo” una medición que empieza a media tarde por haber hecho la consulta con `now()`.

Sensores derivados:

- `last_complete_day_consumption` → `last_day_consumption_kwh` del último día completo disponible.
- `week_consumption` → últimos 7 días disponibles.
- `month_consumption` → últimos 31 días disponibles.
- `measurement_points` → puntos usados tras filtrar calidad.

Atributos relevantes:

```json
{
  "latest_period_start": "YYYY-MM-DDT00:00:00+02:00",
  "latest_period_end": "YYYY-MM-DDT00:00:00+02:00",
  "api_cost_available": false,
  "cost_preference": "estimated"
}
```

#### Coste real vs estimado

Si Kraken devuelve `metaData.statistics.costInclTax.estimatedAmount`, se rellena:

- `last_complete_day_api_cost`.

Si no lo devuelve, se mantiene no disponible y se usa coste estimado separado:

- `last_complete_day_estimated_cost`.
- `week_estimated_cost`.
- `month_estimated_cost`.

El coste estimado se calcula en `estimated_energy_costs_from_hourly()` usando:

- consumo horario real;
- precio base energía;
- descuento regular Sun Club entre 12:00 y 18:00.

No incluye potencia, impuestos ni ajustes de factura. Los atributos lo declaran explícitamente:

```json
{
  "estimated_cost_source": "estimated_from_hourly_consumption_and_tariff",
  "estimated_cost_includes_power": false,
  "estimated_cost_includes_taxes": false
}
```

#### Series para gráficas

`measurement_series` expone varios atributos:

```json
{
  "series": {
    "daily": [{"date": "YYYY-MM-DD", "kwh": 8.954, "cost_eur": null}],
    "weekly": [{"period": "YYYY-W18", "kwh": 69.748, "cost_eur": null}],
    "monthly": [{"period": "YYYY-MM", "kwh": 443.608, "cost_eur": null}],
    "yearly": [{"period": "YYYY", "kwh": 443.608, "cost_eur": null}]
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

`period_series`/`hourly_period_series` permiten ApexCharts de barras apiladas Punta/Llano/Valle. `estimated_cost_series_by_date` permite pintar coste diario estimado.

## Servicios Home Assistant

### `octopus_spain.get_invoice_document`

Entrada:

```yaml
invoice_id_hash: abc123def456
```

Respuesta:

```json
{
  "invoice_id_hash": "abc123def456",
  "url": "<signed-url>"
}
```

La URL es sensible y solo sale en la respuesta del servicio.

### `octopus_spain.get_invoices`

Entrada:

```yaml
limit: 12
```

Respuesta:

```json
{
  "count": 3,
  "invoices": [
    {
      "invoice_id_hash": "...",
      "period_start": "YYYY-MM-DD",
      "period_end": "YYYY-MM-DD",
      "document_available": true
    }
  ]
}
```

### `octopus_spain.get_measurements`

Entrada:

```yaml
start_date: "2026-04-01"
end_date: "2026-05-01"
frequency: DAY_INTERVAL
```

Con `DAY_INTERVAL`, el servicio devuelve datos enriquecidos para dashboards:

- puntos diarios;
- rollups;
- series daily/weekly/monthly/yearly;
- period_series;
- hourly_period_series;
- coste estimado.

Con `HOUR_INTERVAL`, devuelve la serie horaria raw con agregados y period_series horarios.

## Cobertura live probada

Scripts:

```bash
rtk python3 tools/probe_octopus_endpoints.py
rtk python3 tools/verify_ha_mapping.py
rtk python3 tools/smoke_test_api.py
```

Resultado redacted esperado:

```text
obtainKrakenToken: ok
ViewerAccount: ok
ViewerProperty: ok
ViewerSafe: ok
LinkedSupplyPointAccountsSafe: ok
Agreement: ok
BillingInfo: ok
getDevices: ok
AccountReferralsSafe: ok
Bills: ok
AccountCreditsQuery: ok
Bill: ok
getAccountMeasurementsDailyConsumption: ok
getAccountMeasurementsHourlyConsumption: ok
```

Mapeo verificado:

```text
auth.token: mapped
config.account_hash: mapped <hash>
config.property_hash: mapped <hash>
config.ledger: mapped
config.agreement: mapped
overview.viewer: mapped 1 1
overview.linked_supply: mapped 1
tariff.agreement: mapped True 3
billing.statements: mapped 0
devices: mapped 0
referrals.safe_summary: mapped True
invoices.list: mapped 11 11
invoices.document: mapped True
credits.reason_codes: mapped <count> [<codes>]
measurements.daily: mapped 31 ['kwh']
measurements.hourly: mapped 48 ['kwh']
```

## Mapeo web → Home Assistant

| Web/HAR | Método cliente | HA actual | Privacidad |
| --- | --- | --- | --- |
| `obtainKrakenToken` | `async_login` | config flow / reauth / refresh JWT | token y refresh token solo memoria |
| `ViewerAccount` | `async_viewer_account` | selección cuenta, saldo | cuenta/ledger internos |
| `ViewerProperty` | `async_viewer_property` | property/agreement | sin CUPS |
| `Viewer` safe | `async_account_overview` | resumen safe | sin email/NIF/móvil |
| `LinkedSupplyPointAccounts` safe | `async_account_overview` | resumen safe | sin dirección |
| `Agreement` | `async_agreement` | sensores tarifa/precio | no sensible |
| `BillingInfo` | `async_billing_info` | saldo, última factura oportunista | importes solo si API los da |
| `Bills` | `async_bills`, `async_get_invoices_response` | sensor facturas, servicio | ID hash, sin URL |
| `Bill` | `async_get_invoice_document` | servicio PDF | URL solo respuesta |
| `AccountCreditsQuery` | `async_credits` | créditos/reason codes en EUR | IDs ocultos |
| `getDevices` | `async_devices` | resumen dispositivos | sin IDs |
| `AccountReferrals` safe | `async_referrals` | resumen safe | sin URL/nombres |
| `getAccountMeasurements` | `async_measurements`, `async_measurement_dashboard_data`, `async_get_measurements_response` | sensores, series, servicio | property id interno |

## Próximos pasos técnicos

1. Cargar la integración en una instancia real de Home Assistant.
2. Validar entidades, atributos y servicios con respuesta.
3. Crear una tarjeta ApexCharts de ejemplo usando `hourly_period_series.daily` y `estimated_cost_series_by_date`.
4. Añadir options flow para rango histórico y polling configurable.
5. Añadir selección de cuenta/propiedad si hay múltiples.
