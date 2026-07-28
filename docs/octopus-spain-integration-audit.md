# Auditoría priorizada — integración Octopus Energy Spain

**Fecha:** 2026-07-28

**Ámbito:** `custom_components/octopus_spain/`, queries GraphQL, mappers, coordinator, sensores, servicios y herramientas de verificación.

**Estado:** cerrada el 2026-07-28; los 12 hallazgos P0/P1/P2 están resueltos y validados. Las limitaciones residuales se conservan en cada hallazgo.

## Resumen ejecutivo

La integración está bien estructurada, protege razonablemente los datos sensibles y las operaciones principales responden correctamente contra la API GraphQL real de Octopus Energy Spain. No obstante, hay varios problemas de exactitud y compatibilidad que deben resolverse antes de considerar fiables todos los sensores y servicios.

La prioridad inmediata es corregir los datos que pueden aparecer con valores incorrectos en Home Assistant:

1. El saldo de la cuenta se está interpretando en céntimos como si fueran euros.
2. El cálculo de precios y costes no modela correctamente las tarifas multiperiodo y aplica el descuento de Sun Club sin verificar que el contrato lo tenga.
3. Las mediciones no se paginan y pueden perder puntos en rangos largos o durante el cambio de hora.

Después deben abordarse las dependencias GraphQL obsoletas de Solar Wallet e Intelligent Go, el manejo de timeouts y la degradación parcial del coordinator.

---

## Matriz de prioridades

| Prioridad | Hallazgo | Impacto principal | Estado |
| --- | --- | --- | --- |
| **P0 — corregir antes de confiar en los datos** | Saldo en céntimos mostrado como euros | Valores monetarios 100 veces mayores; datos incorrectos en dashboard | **DONE (2026-07-28)** — mapper convertido a EUR y regresión `-13622 -> -136.22`; probe y mapeo live finales correctos |
| **P0 — corregir antes de confiar en los datos** | Tarifas multiperiodo y Sun Club mal modelados | Costes y precios estimados incorrectos | **DONE (2026-07-28)** — términos completos P1/P2/P3 y con/sin impuestos; Sun Club condicionado al producto; validado contra API real |
| **P0 — corregir antes de confiar en los datos** | Falta de paginación en mediciones | Consumo y costes incompletos; pérdida de horas en DST | **DONE (2026-07-28)** — cursor completo, límite explícito y octubre de 2025 validado con 745 puntos |
| **P1 — compatibilidad próxima** | Campos deprecated de Solar Wallet | La query completa puede fallar cuando Kraken retire los campos | **DONE (2026-07-28)** — migrado a ledgers y permisos modernos; query legacy eliminada |
| **P1 — compatibilidad próxima** | `registeredKrakenflexDevice` deprecated | Intelligent Go puede dejar de actualizarse | **DONE (2026-07-28)** — migrado a `devices`; elegibilidad y registro separados |
| **P1 — disponibilidad** | Timeouts no normalizados | Fallos no controlados en config flow, coordinator y servicios | **DONE (2026-07-28)** — timeout y JSON inválido normalizados a errores de integración |
| **P2 — completitud** | Créditos sin paginación | Totales y atributos incompletos tras más de 100 transacciones | **DONE (2026-07-28)** — cursor completo, ventana dinámica de 5 años y truncado explícito |
| **P2 — completitud** | Última factura depende de una conexión vacía | Sensores de última factura unavailable aunque existan facturas | **DONE (2026-07-28)** — sensores alimentados desde `ledgers.invoices` y unidades menores convertidas |
| **P2 — robustez** | Errores de permisos tratados como auth inválida | Reautenticaciones innecesarias y diagnósticos engañosos | **DONE (2026-07-28)** — clases separadas por código/status; permisos no reautentican |
| **P2 — resiliencia** | Coordinator todo-o-nada | Un fallo opcional deja indisponibles datos esenciales | **DONE (2026-07-28)** — grupos opcionales degradan/retienen datos; auth sigue siendo fatal |
| **P2 — multi-cuenta** | Selección implícita de la primera cuenta | Puede mostrarse la cuenta equivocada | **DONE (2026-07-28)** — config flow selecciona cuenta/propiedad redacted y servicios aceptan `config_entry_id` |
| **P2 — contrato de servicio** | `end_date` es ambiguo | Usuarios pueden interpretar mal el rango solicitado | **DONE (2026-07-28)** — rango `[start_date, end_date)` explícito en código, UI, README y DST test |

---

# P0 — correcciones de exactitud

## P0.1 — Convertir el saldo del ledger de céntimos a euros

### Evidencia

Archivos afectados:

- `custom_components/octopus_spain/graphql_queries.py:127-130`
- `custom_components/octopus_spain/mappers.py:361-370`
- `custom_components/octopus_spain/sensor.py:236`

La API define `LedgerType.balance` como:

> `The current balance on the ledger in minor units of currency.`

El mapper actual pasa el valor bruto directamente:

```python
balances={"credit_balance": amount_value(electricity_billing.get("balance"))}
```

La cuenta usada durante la auditoría devolvió un saldo equivalente a:

```text
-13622 céntimos = -136,22 EUR
```

Pero el sensor está configurado con:

```python
device_class=SensorDeviceClass.MONETARY
native_unit_of_measurement=CURRENCY_EURO
```

Por tanto, Home Assistant puede interpretar `-13622` como `-13622 EUR`.

Los créditos sí convierten correctamente las unidades menores mediante `parsed / 100`, lo que hace que este comportamiento sea inconsistente dentro de la propia integración.

### Resolución (2026-07-28)

**Estado:** DONE. La causa raíz era que `LedgerType.balance` se exponía en unidades monetarias menores y `build_data()` lo pasaba sin conversión al sensor monetario. Se añadió `minor_amount_eur()` como conversión común y `credit_balance` ahora conserva el signo y convierte céntimos a EUR con seis decimales internos.

**Archivos modificados:**

- `custom_components/octopus_spain/mappers.py`
- `tests/test_sensor_data_quality.py`
- `docs/octopus-spain-integration-audit.md`

**Pruebas y comandos ejecutados:**

- `py -m pytest -q tests/test_sensor_data_quality.py tests/test_probe_mappers.py` → **11 passed**.
- `py -m pytest -q` → **39 passed** (línea base histórica: 38).
- `py -m compileall -q custom_components tools` → **correcto**.
- `git diff --check` → **correcto** (solo advertencias de conversión de finales de línea de Git).

**Validación API:** la documentación oficial consultada confirma que `balance` es “in minor units of currency” (fuente: `https://developer.oees-kraken.energy/graphql/reference/interfaces/`). El probe y la verificación de mapeo live finales pasaron con salida redacted; la prueba exacta conserva `-13622 -> -136.22` sin publicar el saldo live.

**Limitaciones:** no se hizo migración del histórico ya almacenado por Home Assistant; los estados futuros son correctos. Los restantes importes implicados se revisaron en P0.2 y P2.2 y quedaron separados/conversos según su unidad documentada.

### Impacto

- El sensor `credit_balance` muestra un valor 100 veces mayor.
- Los cuadros de mando y automatizaciones monetarias reciben datos erróneos.
- El historial conserva estados incorrectos mientras no se migre o reinicie la entidad.
- Puede producirse doble conteo o importes absurdos al usar los datos en dashboards financieros.

### Corrección recomendada

1. Convertir `balance` de unidades menores a euros en el mapper o en una función monetaria común.
2. Redondear con una precisión consistente, por ejemplo seis decimales internamente y dos para presentación.
3. Documentar el signo del valor:
   - mantener el saldo firmado tal como lo devuelve Kraken; o
   - exponer un crédito disponible positivo si el saldo negativo significa crédito a favor.
4. Añadir pruebas para valores positivos, negativos, cero, `None` y tipos inesperados.
5. Revisar si hay otros campos monetarios GraphQL que también estén en unidades menores (`grossAmount`, `invoicedAmount`, balances, etc.).
6. Considerar una migración de entidad si Home Assistant conserva el historial del sensor antiguo.

### Criterio de aceptación

Para un payload con `balance = -13622`, el valor nativo del sensor debe ser `-136.22` y su unidad debe ser EUR, con una prueba automatizada que lo garantice.

---

## P0.2 — Modelar precios multiperiodo y condicionar Sun Club al producto

### Evidencia

Archivos afectados:

- `custom_components/octopus_spain/graphql_queries.py:105-117`
- `custom_components/octopus_spain/mappers.py:377-390`
- `custom_components/octopus_spain/sensor.py:72-79`
- `custom_components/octopus_spain/measurements.py:214-229`
- `custom_components/octopus_spain/coordinator.py:128-136`

La API devuelve varios términos de precio en `fixedTerm` y `variableTerm`. En la cuenta probada se obtuvieron:

- **3 términos variables**;
- **2 términos fijos**.

Sin embargo, el mapper solo conserva el primer término:

```python
"base_energy_price": amount_value(variable_terms[0])
```

El coste estimado utiliza después un único precio para todas las horas:

```python
price = base_price * (1 - discount) if start_hour <= point.start.hour < end_hour else base_price
```

Esto no representa correctamente una tarifa española multiperiodo con Punta, Llano y Valle.

La lógica de `current_energy_price` también aplica el descuento de Sun Club únicamente por hora:

```python
if SUN_CLUB_START_HOUR <= now.hour < SUN_CLUB_END_HOUR:
    return round(float(base_price) * (1 - SUN_CLUB_DISCOUNT), 6)
```

No verifica que el producto o contrato de la cuenta incluya Sun Club.

### Resolución (2026-07-28)

**Estado:** DONE. La causa raíz era doble: el mapper descartaba todos los términos salvo el primero y las rutas de precio actual/coste aplicaban Sun Club por horario sin comprobar el contrato. La query solicita ahora seis decimales y obtiene términos con y sin impuestos; el mapper conserva todas las listas, mapea el orden contractual P1/P2/P3 a Punta/Llano/Valle, conserva por separado precios con/sin impuestos y detecta Sun Club solo mediante marcadores del producto/params. El cálculo horario usa el periodo 2.0TD de cada punto, considera todos los fines de semana Valle y solo aplica el 45 % dentro de 12:00–18:00 cuando el producto lo confirma. El binary sensor queda apagado para productos sin Sun Club.

**Archivos modificados:**

- `custom_components/octopus_spain/graphql_queries.py`
- `custom_components/octopus_spain/mappers.py`
- `custom_components/octopus_spain/measurements.py`
- `custom_components/octopus_spain/api.py`
- `custom_components/octopus_spain/coordinator.py`
- `custom_components/octopus_spain/services.py`
- `custom_components/octopus_spain/sensor.py`
- `custom_components/octopus_spain/binary_sensor.py`
- `tests/test_sensor_data_quality.py`
- `tools/probe_octopus_endpoints.py`
- `tools/smoke_test_api.py`
- `tools/smoke_test_web_flow.py`
- `docs/octopus-spain-integration-audit.md`

**Pruebas y comandos ejecutados:**

- `py -m pytest -q tests/test_sensor_data_quality.py` → **17 passed**.
- `py -m pytest -q` → **47 passed** (incluye regresiones de Punta/Llano/Valle, laborables, fin de semana, cuenta con/sin Sun Club y precios con/sin impuestos).
- `py -m compileall -q custom_components tools` → **correcto**.
- `py tools/probe_octopus_endpoints.py` → **14 operaciones `ok`**, informe redacted ignorado por Git.
- `py tools/verify_ha_mapping.py` → tariff `mapped`, 3 términos variables; resto de mapeos ejecutado sin error.
- `git diff --check` → **correcto** (solo advertencias de finales de línea de Git).

**Validación API real:** introspección redacted confirmó `fixedTerm`, `variableTerm`, `fixedTermWithTaxes` y `variableTermWithTaxes`; la operación `Agreement` modificada devolvió **3/3 términos variables sin/con impuestos y 2/2 fijos sin/con impuestos**. El mapper produjo los tres periodos y detectó el marcador Sun Club del producto sin imprimir código, params ni importes. La documentación oficial confirma que `prices(decimalPlaces:, powerDecimalPlaces:)` acepta precisión explícita y que por defecto usa tres decimales.

**Limitaciones:** Kraken documenta las listas como términos fijos/variables pero no etiqueta cada posición; la asociación P1/P2/P3 → Punta/Llano/Valle sigue el orden tarifario español observado y se conserva explícitamente. Los festivos nacionales no se obtienen de la API ni se modelan: solo sábados y domingos se consideran Valle. El coste local sigue siendo energía sin impuestos, potencia ni ajustes finales; los precios con impuestos se conservan pero no se mezclan con la estimación sin impuestos. Estas limitaciones quedan visibles y no alteran el criterio P0.2 solicitado.

### Impacto

- `current_energy_price` puede ser incorrecto.
- Los costes estimados diarios, semanales y mensuales pueden diferir materialmente del coste real.
- Se ignoran Punta, Llano y Valle.
- El descuento de Sun Club puede aplicarse a clientes sin ese producto.
- El binary sensor de la ventana Sun Club puede indicar una ventaja que la cuenta no tiene.
- El cálculo no distingue claramente entre precios con impuestos y sin impuestos.
- Los precios pueden haberse redondeado demasiado pronto: la API documenta tres decimales por defecto y la integración solicita una precisión de presentación superior.

### Corrección recomendada

1. Conservar todos los términos devueltos por `prices`.
2. Parsear `product.params`, el código del producto y cualquier metadato que identifique el plan.
3. Representar explícitamente los precios Punta/Llano/Valle y asociarlos con los periodos que ya calcula `_spanish_period()`.
4. Consultar y distinguir:
   - `variableTerm`;
   - `variableTermWithTaxes`;
   - `fixedTerm`;
   - `fixedTermWithTaxes`.
5. Aplicar Sun Club solo si el producto contratado lo confirma.
6. Mantener separadas estas semánticas:
   - precio de energía sin impuestos;
   - precio de energía con impuestos;
   - coste proveniente de la API;
   - coste estimado localmente.
7. Añadir pruebas para días laborables, fines de semana, festivos, cambio de periodo y cuentas sin Sun Club.
8. Solicitar explícitamente `decimalPlaces` y `powerDecimalPlaces` con la precisión que realmente soporte el endpoint.

### Criterio de aceptación

Con un contrato de tres precios variables, cada punto horario debe calcularse con el término correspondiente. Una cuenta sin Sun Club no debe recibir el descuento, independientemente de la hora local.

---

## P0.3 — Implementar paginación de mediciones

### Evidencia

Archivos afectados:

- `custom_components/octopus_spain/graphql_queries.py:335-380`
- `custom_components/octopus_spain/api.py:261-275`
- `custom_components/octopus_spain/api.py:290-292`
- `custom_components/octopus_spain/api.py:485-498`

La API define `MeasurementConnection` con:

```graphql
pageInfo
edgeCount
totalCount
```

La query actual solicita solo los `edges` y no utiliza cursor `after`. El cliente limita las mediciones horarias a 744:

```python
"first": max(1, min(first, 366 if frequency == "DAY_INTERVAL" else 744))
```

### Reproducción

Para octubre de 2025, que contiene la transición de horario de verano a invierno:

- puntos existentes según Kraken: **745**;
- puntos solicitados por la integración: **744**;
- respuesta: `hasNextPage: true`;
- se pierde la última hora del rango.

Solicitando `first: 745`, la API devolvió los 745 puntos y `hasNextPage: false`.

También se comprobaron otros casos DST y rangos diarios; el problema específico aparece cuando el rango necesita más puntos que el límite artificial.

### Resolución (2026-07-28)

**Estado:** DONE. La causa raíz era que la operación no solicitaba `pageInfo` ni aceptaba `after`, y el cliente limitaba toda descarga horaria a 744 puntos. La query incluye ahora cursor, `pageInfo` y `totalCount`; el cliente acumula páginas hasta `hasNextPage == false`, rechaza cursores ausentes/repetidos en lugar de truncar silenciosamente y aplica un máximo de seguridad de 10.000 puntos con atributo `truncated`. Los puntos completos se conservan para cálculos y servicios; ya no se recortan a los últimos 744 en el mapper.

**Archivos modificados:**

- `custom_components/octopus_spain/graphql_queries.py`
- `custom_components/octopus_spain/api.py`
- `custom_components/octopus_spain/mappers.py`
- `custom_components/octopus_spain/sensor.py`
- `tests/test_api_helpers.py`
- `tools/probe_octopus_endpoints.py`
- `docs/octopus-spain-integration-audit.md`

**Pruebas y comandos ejecutados:**

- `py -m pytest -q tests/test_api_helpers.py tests/test_sensor_data_quality.py` → **33 passed**.
- `py -m pytest -q` → **50 passed**.
- `py -m compileall -q custom_components tools` → **correcto**.
- `py tools/probe_octopus_endpoints.py` → **14 operaciones `ok`**, incluidas mediciones diarias y horarias con metadatos de conexión.
- `py tools/verify_ha_mapping.py` → mediciones daily `31` y hourly `48`, ambas `mapped`.
- `git diff --check` → **correcto** (solo advertencias de finales de línea de Git).

**Validación API real:** se ejecutó el cliente paginado para el rango exclusivo `2025-10-01T00:00 Europe/Madrid` → `2025-11-01T00:00 Europe/Madrid`; devolvió `points_count: 745`, `total_count: 745`, `truncated: False`. No se imprimieron valores, fechas de puntos, CUPS ni identificadores. La prueba simulada equivalente fuerza una primera página de 744 con `hasNextPage: true` y verifica la segunda página y los 745 puntos.

**Limitaciones:** el máximo defensivo de 10.000 puntos queda señalado mediante `truncated: true`; no existe pérdida silenciosa. El atributo de una entidad con miles de puntos puede ser grande, pero el servicio debe devolver el rango completo solicitado mientras no alcance ese máximo.

### Impacto

- Rangos horarios largos quedan truncados silenciosamente.
- El consumo de octubre puede perder una hora.
- Los totales por periodo y costes estimados quedan incompletos.
- El servicio `get_measurements` acepta rangos que no puede devolver íntegramente.
- No se informa al usuario de que hay datos pendientes en otra página.

### Corrección recomendada

Añadir cursor y metadatos a la query:

```graphql
$after: String

measurements(first: $first, after: $after, ...) {
  pageInfo {
    hasNextPage
    endCursor
  }
  totalCount
  edges {
    ...
  }
}
```

Implementar un bucle que:

1. solicite la primera página;
2. acumule los `edges`;
3. use `pageInfo.endCursor` como `after`;
4. continúe mientras `hasNextPage` sea verdadero;
5. aplique un límite de seguridad configurable para evitar respuestas descontroladas;
6. conserve un indicador de truncado si se alcanza ese límite.

El límite de 744 puede mantenerse para atributos de Home Assistant si es necesario, pero no debe limitar la descarga ni los cálculos internos sin avisarlo.

### Criterio de aceptación

El rango horario de octubre de 2025 debe devolver 745 puntos, sin pérdida silenciosa, y una prueba debe verificar que la segunda página se consulta cuando `hasNextPage` es verdadero.

---

# P1 — compatibilidad y disponibilidad

## P1.1 — Migrar Solar Wallet fuera de campos deprecated

### Evidencia

Archivo afectado:

- `custom_components/octopus_spain/graphql_queries.py:280-296`

La query utiliza:

```graphql
hasSolarWallet
solarWalletAvailableCredit
solarWalletLedgers
```

La documentación oficial marca los tres campos como deprecated:

- `hasSolarWallet`: derivar la existencia desde los ledgers y filtrar `SOLAR_WALLET_LEDGER`.
- `solarWalletAvailableCredit`: usar el balance del ledger.
- `solarWalletLedgers`: usar `creditTransferPermissionsData.toTargetLedgers`.

La retirada estaba anunciada para el **10 de agosto de 2025**. En la cuenta probada todavía funcionan, pero ya no son una base estable.

### Resolución (2026-07-28)

**Estado:** DONE. La query ya no solicita ninguno de los tres campos deprecated. Solar Wallet se deriva exclusivamente de `account.ledgers` filtrando `SOLAR_WALLET_LEDGER`; saldo/crédito se convierte desde `balance` en unidades menores; relaciones se obtienen desde `creditTransferPermissionsData.toTargetLedgers`. Ledger y cuenta destino solo se exponen como hashes estables.

**Archivos modificados:**

- `custom_components/octopus_spain/graphql_queries.py`
- `custom_components/octopus_spain/mappers.py`
- `custom_components/octopus_spain/api.py`
- `tests/test_sensor_data_quality.py`
- `docs/octopus-spain-integration-audit.md`

**Pruebas y comandos:**

- `py -m pytest -q tests/test_sensor_data_quality.py` → **18 passed**.
- `py -m pytest -q` → **51 passed**.
- `py -m compileall -q custom_components tools` → **correcto**.
- `rg -n "hasSolarWallet|solarWalletAvailableCredit|solarWalletLedgers" custom_components tests --glob '*.py'` → **sin coincidencias**.
- `py tools/probe_octopus_endpoints.py` y `py tools/verify_ha_mapping.py` → **correctos**.
- `git diff --check` → **correcto**.

**Validación API real:** introspección redacted confirmó las deprecaciones y sus sustitutos exactos. La nueva operación respondió `available: True`; en la cuenta sin Solar Wallet devolvió estado falso, cero relaciones y sin saldo, sin error GraphQL ni datos sensibles.

**Limitaciones:** no hay credenciales de una cuenta con Solar Wallet activo; el payload positivo está cubierto por fixture de regresión, pero falta confirmar en vivo el caso activo. La ausencia se representa de forma explícita, no como error.

### Impacto

GraphQL valida todos los campos de la operación. Cuando se retire cualquiera, puede fallar la query completa y `async_solar_wallet()` devolverá un estado `unavailable`, incluso para datos que seguirían disponibles mediante los campos nuevos.

### Corrección recomendada

Migrar a:

- `account.ledgers`;
- `ledgerType == "SOLAR_WALLET_LEDGER"`;
- `balance` del ledger;
- `creditTransferPermissionsData.toTargetLedgers`;
- `spanishLedgers.solarWalletCreditLeft`, si continúa siendo necesario.

Mantener temporalmente el resultado redacted actual y no exponer números de ledger, IDs crudos ni URLs.

### Criterio de aceptación

La integración debe obtener el estado y el saldo de Solar Wallet sin consultar `hasSolarWallet`, `solarWalletAvailableCredit` ni `solarWalletLedgers`.

---

## P1.2 — Migrar Intelligent Go a `devices`

### Evidencia

Archivo afectado:

- `custom_components/octopus_spain/graphql_queries.py:298-322`

La integración utiliza `registeredKrakenflexDevice`, que la documentación oficial marca como deprecated y cuya retirada estaba prevista para el **1 de marzo de 2026**. La alternativa oficial es `devices(accountNumber:, propertyId:)`.

La cuenta probada mostró:

- 2 tipos de dispositivo elegibles;
- `registeredKrakenflexDevice` presente, pero con muchos detalles operativos nulos;
- ningún dispositivo en la consulta moderna `devices`.

El resultado confirma que “tipo elegible” no equivale a “dispositivo registrado”.

### Resolución (2026-07-28)

**Estado:** DONE. `KrakenFlex` consulta ahora `devices(accountNumber:, propertyId:)` con `__typename`, tipo, proveedor y estado moderno. El mapper distingue tipos elegibles de dispositivos registrados, no expone ID/nombre/property crudos, y solo solicita dispatches si un dispositivo moderno aporta `id`. Se eliminó la dependencia legacy, sin fallback deprecated.

**Archivos modificados:**

- `custom_components/octopus_spain/graphql_queries.py`
- `custom_components/octopus_spain/api.py`
- `custom_components/octopus_spain/mappers.py`
- `tests/test_sensor_data_quality.py`
- `docs/octopus-spain-integration-audit.md`

**Pruebas y comandos:**

- `py -m pytest -q tests/test_sensor_data_quality.py` → **19 passed**.
- `py -m pytest -q` → **52 passed**.
- `py -m compileall -q custom_components tools` → **correcto**.
- `rg -n "registeredKrakenflexDevice" custom_components tests --glob '*.py'` → **sin coincidencias**.
- `py tools/probe_octopus_endpoints.py` y `py tools/verify_ha_mapping.py` → **correctos**.
- `git diff --check` → **correcto**.

**Validación API real:** introspección confirmó deprecación y sustitución por `devices`. La consulta moderna devolvió dos tipos elegibles pero cero dispositivos registrados; el resultado distinguió `eligible_count: 2`, `registered_count: 0`, `registered_present: False`, sin intentar dispatches.

**Limitaciones:** no se dispone de cuenta con Intelligent Go activo; el caso positivo moderno y dispatches está cubierto por fixture, pero la variedad completa de `SmartFlexDevice`/status concretos requiere validación futura con cuenta activa. El criterio no exige mantener fallback deprecated y se ha evitado para no prolongar la dependencia retirada.

### Impacto

- El sensor puede depender de un campo que ya no sea válido.
- Un cambio de schema puede romper la query completa de Intelligent Go.
- Los estados `registered`, `eligible` y `operational` pueden confundirse.

### Corrección recomendada

1. Implementar el mapper sobre `devices` usando `__typename` y las interfaces/tipos concretos que devuelva Kraken.
2. Separar claramente:
   - tipos elegibles;
   - dispositivos registrados;
   - dispositivo activo;
   - estado operativo;
   - dispatches.
3. Mantener un fallback legacy temporal solo mientras se valida el payload nuevo.
4. No llamar a `flexPlannedDispatches` si no existe un ID operativo válido.
5. Validar con una cuenta que tenga Intelligent Go activado.

### Criterio de aceptación

La integración no debe depender exclusivamente de `registeredKrakenflexDevice`, y debe distinguir una cuenta elegible de una cuenta con dispositivo registrado.

---

## P1.3 — Normalizar timeouts y errores de transporte

### Evidencia

Archivo afectado:

- `custom_components/octopus_spain/api.py:341-363`

La petición usa:

```python
await asyncio.wait_for(..., timeout=30)
```

pero solo captura `ClientResponseError` y `ClientError`. Un timeout de `asyncio.wait_for()` puede lanzar `TimeoutError` y escapar de `_post()`.

Tampoco se observa un manejo específico para respuestas HTTP 200 con JSON inválido.

### Resolución (2026-07-28)

**Estado:** DONE. `_post()` convierte ahora `asyncio.TimeoutError` y errores de transporte en `OctopusSpainError("Cannot connect to Octopus")`; cuerpos JSON inválidos se convierten en un error controlado distinto. No se capturan errores arbitrarios de programación.

**Archivos modificados:**

- `custom_components/octopus_spain/api.py`
- `tests/test_api_helpers.py`
- `docs/octopus-spain-integration-audit.md`

**Pruebas y comandos:**

- `py -m pytest -q tests/test_api_helpers.py` → **18 passed**, incluidas regresiones de timeout y JSON inválido.
- `py -m pytest -q` → **54 passed**.
- `py -m compileall -q custom_components tools` → **correcto**.
- `git diff --check` → **correcto**.

**Validación API real:** los probes live siguieron funcionando tras el cambio; no es seguro provocar un timeout real deliberado contra producción, por lo que el límite HTTP se validó mediante dobles deterministas.

**Limitaciones:** la clasificación fina se completó en P2.3; códigos GraphQL desconocidos siguen siendo un error genérico explícito, sin asumir auth o temporalidad.

### Impacto

- Un timeout puede producir un error no controlado en el config flow.
- El coordinator puede no convertirlo en `UpdateFailed`.
- Un servicio puede responder con un error interno en vez de un error de integración controlado.
- El usuario puede no obtener diagnóstico accionable.

### Corrección recomendada

Capturar explícitamente timeout y errores de decodificación en el límite HTTP, convirtiéndolos a la jerarquía de errores de la integración, por ejemplo:

```python
except (ClientError, asyncio.TimeoutError) as err:
    raise OctopusSpainError("Cannot connect to Octopus") from err
```

Añadir el error de JSON/valor cuando corresponda, sin ocultar errores de programación. Añadir tests para timeout, HTTP 401/403, HTTP 5xx y cuerpo no JSON.

### Criterio de aceptación

Todo timeout de red debe convertirse en un error `OctopusSpainError` controlado y no debe escapar como excepción genérica.

---

# P2 — completitud y robustez

## P2.1 — Paginar créditos

### Evidencia

Archivos afectados:

- `custom_components/octopus_spain/graphql_queries.py:200-225`
- `custom_components/octopus_spain/api.py:208-218`
- `custom_components/octopus_spain/mappers.py:244-266`

La query solicita `pageInfo.hasNextPage` y `endCursor`, pero `async_credits()` no utiliza `endCursor`. También mantiene una fecha fija:

```graphql
transactions(fromDate: "2025-01-01", first: 100)
```

La cuenta probada tiene 15 transacciones, así que todavía no se observa truncado.

### Resolución (2026-07-28)

**Estado:** DONE. Créditos se descargan página a página con `after`, se agregan todas las páginas y se rechaza un cursor inválido. `fromDate` dejó de estar fijado a 2025: usa el 1 de enero de hace cinco años. Hay un máximo explícito de 5.000 transacciones y `truncated` se propaga a atributos.

**Archivos modificados:** `graphql_queries.py`, `api.py`, `mappers.py`, `sensor.py`, `tests/test_api_helpers.py`, los tres scripts de `tools/` que usan la query y este documento.

**Evidencia:** prueba de dos páginas y agregación completa; `py -m pytest -q` → **55 passed**; compileall correcto; probe y verify live correctos; `git diff --check` correcto. La cuenta real tiene 15 créditos y no necesita segunda página, por lo que la paginación positiva se valida con doble determinista.

**Limitaciones:** historial limitado deliberadamente a cinco años/5.000 transacciones; cualquier límite alcanzado queda expuesto como `truncated: true`.

### Impacto

Cuando existan más de 100 transacciones desde la fecha fija:

- los totales por tipo de crédito serán incompletos;
- `reason_code_counts` será parcial;
- los atributos redacted no representarán todo el periodo;
- no habrá señal visible de truncado.

### Corrección recomendada

- Añadir `$after` a la query.
- Paginar hasta `hasNextPage == false`.
- Hacer `fromDate` dinámico o configurable.
- Aplicar un máximo documentado de historial.
- Conservar una marca `truncated` si se alcanza el máximo.

---

## P2.2 — Obtener la última factura desde la conexión moderna de facturas

### Evidencia

Archivos afectados:

- `custom_components/octopus_spain/graphql_queries.py:124-143`
- `custom_components/octopus_spain/mappers.py:355-369`
- `custom_components/octopus_spain/mappers.py:393-400`

La query de `accountBillingInfo.statementsWithDetails(first: 1)` es válida, pero la API real devolvió:

```text
statement_edges_count: 0
```

Al mismo tiempo, `Bills` devolvió 12 facturas y los 12 documentos estaban disponibles como PDF.

### Resolución (2026-07-28)

**Estado:** DONE. `BILLS_QUERY` obtiene `invoicedAmount`, `firstIssued`, periodo, retención y anulación desde `InvoiceBillingDocumentType`. La lista redacted incluye importe convertido desde unidades menores y `build_data()` prefiere la última factura moderna no anulada; el statement legacy queda como fallback y también convierte unidades menores.

**Archivos modificados:** `graphql_queries.py`, `api.py`, `mappers.py`, `tests/test_api_helpers.py`, `tests/test_sensor_data_quality.py`, herramientas con la query y este documento.

**Evidencia:** **57 passed**, compileall y diff check correctos; probe/verify live correctos. Validación real redacted: 12 facturas y presencia verdadera de importe, emisión y periodo en los sensores modernos, aunque `BillingInfo` sigue devolviendo cero statements. No se imprimieron importes ni IDs.

**Limitaciones:** se toma la primera factura no anulada según `FINALIZED_AT_DESC`; una factura retenida se mantiene visible porque sigue siendo un documento real, con `held` disponible en datos redacted.

### Impacto

Los sensores:

- `last_invoice_amount`;
- `last_invoice_issued`;
- `last_invoice_period_start`;
- `last_invoice_period_end`

pueden quedar `unavailable` aunque haya facturas válidas.

### Corrección recomendada

Obtener la última factura desde la conexión que sí devuelve datos, usando los campos documentados por el schema, por ejemplo:

- `account.bills` y el fragmento `InvoiceType`;
- o `ledgers.invoices` con `invoicedAmount`, `firstIssued`, `earliestChargeAt` y `latestChargeAt`.

Revisar de nuevo la conversión de importes monetarios, ya que `grossAmount` e `invoicedAmount` también pueden estar en unidades menores.

---

## P2.3 — Clasificar errores GraphQL sin confundir permisos con autenticación

### Evidencia

Archivo afectado:

- `custom_components/octopus_spain/api.py:365-375`

La lógica actual convierte cualquier error cuyo texto contenga alguno de estos términos en `OctopusSpainAuthError`:

```python
"auth" or "token" or "permission" or "jwt"
```

### Resolución (2026-07-28)

**Estado:** DONE. Se añadieron errores tipados para permisos, rate limit y fallos temporales. HTTP 401 es auth, 403 permisos, 429 rate limit y 5xx temporal. GraphQL prioriza `extensions.code` y solo usa marcadores textuales estrechos; ya no clasifica cualquier texto con “permission” como credenciales inválidas.

**Archivos:** `api.py`, `tests/test_api_helpers.py`, auditoría. **Evidencia:** pruebas explícitas de auth expirada, permiso no-auth, rate limit y temporal; suite **59 passed**, compileall/diff check correctos. Probes live siguen correctos; no se provocaron errores reales de producción.

**Limitaciones:** Kraken tiene numerosos códigos específicos; los desconocidos permanecen como `OctopusSpainGraphQLError`, evitando asumir auth o reintento sin evidencia.

### Impacto

Un usuario con credenciales válidas pero sin permisos para una función opcional puede ser reautenticado innecesariamente. Esto puede:

- ocultar el problema real;
- provocar reintentos inútiles;
- generar diagnósticos incorrectos;
- agravar límites de login.

### Corrección recomendada

Usar `errors[].extensions.code` cuando exista y separar como mínimo:

- token expirado;
- credenciales inválidas;
- permiso insuficiente;
- campo/función no disponible;
- rate limit;
- error temporal del upstream.

Los errores de permiso de una operación opcional deben degradar esa operación, no invalidar la sesión completa.

---

## P2.4 — Evitar que el coordinator sea todo-o-nada

### Evidencia

Archivo afectado:

- `custom_components/octopus_spain/coordinator.py:93-151`

Una actualización ejecuta secuencialmente contrato, billing, facturas, créditos, Solar Wallet, Intelligent Go y mediciones.

### Resolución (2026-07-28)

**Estado:** DONE. Facturas, créditos, Solar Wallet e Intelligent Go se tratan como operaciones opcionales: un error tipado conserva su último valor válido con `stale/error` o usa un valor vacío explícito. Contrato, billing y mediciones siguen siendo esenciales. Los errores de autenticación nunca se degradan y provocan reauth.

**Archivos:** `coordinator.py`, nuevo `tests/test_coordinator_resilience.py`, auditoría. **Evidencia:** regresiones de vacío inicial, retención stale y auth fatal; suite **62 passed**, compileall/diff check correctos.

**Limitaciones:** se mantiene una cadencia común horaria; optimizar cadencias separadas es mejora posterior y no es requisito del criterio de degradación parcial.

### Impacto

El fallo de una operación opcional puede dejar indisponibles datos esenciales, por ejemplo consumo o tarifa.

También todas las operaciones se actualizan con una cadencia común aunque sus necesidades sean diferentes.

### Corrección recomendada

Separar los datos en grupos:

- **esenciales:** contrato, saldo, mediciones;
- **oportunistas:** facturas y créditos;
- **experimentales/opcionales:** Solar Wallet e Intelligent Go.

Cada grupo debería:

- conservar el último valor válido cuando sea razonable;
- publicar su propio error o timestamp de actualización;
- no bloquear al resto del coordinator.

También conviene valorar cadencias diferentes:

- mediciones: aproximadamente cada hora;
- contrato: cada 6–24 horas;
- facturas y créditos: cada 6–12 horas;
- datos de dispositivos: según necesidad.

---

## P2.5 — Hacer explícita la selección de cuenta y propiedad

### Evidencia

Archivos afectados:

- `custom_components/octopus_spain/mappers.py:51-61`
- `custom_components/octopus_spain/services.py:92-160`

La configuración selecciona siempre:

```python
accounts[0]
```

Y varios servicios utilizan el primer runtime disponible mediante `first_runtime_data(hass)`.

### Resolución (2026-07-28)

**Estado:** DONE. El descubrimiento devuelve todos los suministros eléctricos utilizables y el config flow presenta un paso de selección explícita usando solo hashes de cuenta/propiedad; el unique ID combina ambos. Los servicios con objetivo ambiguo aceptan selector `config_entry_id`, permiten omitirlo con una sola entrada y rechazan múltiples entradas sin selección. La ausencia de cuentas utilizables produce un error presentable, no `ValueError` sin controlar.

**Archivos:** `mappers.py`, `api.py`, `config_flow.py`, `service_helpers.py`, `services.py`, `services.yaml`, strings/traducción, tests y auditoría. **Evidencia:** pruebas de dos cuentas y servicio ambiguo; suite **64 passed**, compileall/diff check y probes live correctos.

**Limitaciones:** la cuenta live solo contiene un suministro; el paso múltiple se valida por fixture y usa hashes redacted, no nombres/direcciones.

### Impacto

Un usuario con varias cuentas o varias entradas configuradas puede consultar o mostrar la cuenta equivocada.

Además, `select_default_account()` puede lanzar `ValueError` si no hay cuentas, mientras que el config flow captura principalmente errores de la integración. El caso puede terminar en un error no controlado.

### Corrección recomendada

- Añadir selección explícita de cuenta/propiedad en el config flow.
- Asociar los servicios a `config_entry_id` o a un selector claro de cuenta.
- Validar que la cuenta seleccionada tenga ledger eléctrico y contrato activo.
- Convertir la ausencia de cuentas en un error de configuración presentable.

---

## P2.6 — Documentar la semántica de `end_date`

### Evidencia

Archivos afectados:

- `custom_components/octopus_spain/service_helpers.py:15-28`
- `custom_components/octopus_spain/api.py:321` y lógica de construcción de `end_at`

El servicio parece presentar `end_date` como fecha final del rango, pero se transforma en medianoche del propio día:

```python
end_at = datetime.combine(end_date, datetime.min.time(), MADRID)
```

El rango es, por tanto, de final exclusivo. Por ejemplo:

```yaml
start_date: "2026-04-01"
end_date: "2026-05-01"
```

representa abril completo, no incluye el 1 de mayo.

### Resolución (2026-07-28)

**Estado:** DONE. Se define formalmente el rango semiabierto `[start_date, end_date)`: inicio inclusivo y fin exclusivo a medianoche de Madrid. La semántica está en docstrings, selector del servicio y README, con una prueba de octubre de 2025 que demuestra 745 horas entre los límites por DST.

**Archivos:** `service_helpers.py`, `services.yaml`, `README.md`, `tests/test_api_helpers.py`, auditoría. **Evidencia:** suite **65 passed**, compileall/diff check y probes live correctos.

**Limitaciones:** se conserva el nombre `end_date` por compatibilidad; su exclusividad ya no es ambigua en la interfaz/documentación.

### Impacto

La implementación puede ser correcta, pero el nombre y la interfaz son ambiguos. Un usuario puede esperar que `end_date` sea inclusivo y perder el día final sin advertencia.

### Corrección recomendada

Elegir y documentar explícitamente una de estas opciones:

- `end_date` exclusivo, renombrándolo/documentándolo como tal; o
- fecha final inclusiva, sumando un día antes de construir `end_at`.

Añadir pruebas de rango, medianoche y DST.

---

# Compatibilidad con la API GraphQL actual

| Área | Estado |
| --- | --- |
| Endpoint `api.oees-kraken.energy/v1/graphql/` | Correcto |
| `obtainKrakenToken` | Correcto |
| JWT en cabecera `Authorization` | Correcto |
| `refreshToken` y `refreshExpiresIn` | Correcto |
| `viewer.accounts` | Correcto |
| `agreement(id:)` | Correcto |
| `accountBillingInfo` | Query válida, pero sin última factura en la cuenta probada |
| `ledgers.invoices` y PDFs | Correcto y validado |
| `transactions` de créditos | Correcto, pero sin paginación |
| `property.measurements` | Correcto, pero sin paginación |
| Solar Wallet | Funciona actualmente, pero usa campos deprecated |
| `flexPlannedDispatches` | Correcto |
| `registeredKrakenflexDevice` | Funciona actualmente, pero está deprecated |
| Query moderna `devices` | Existe; requiere adaptar el mapper |

Fuentes oficiales consultadas:

- <https://developer.oees-kraken.energy/graphql/reference/mutations/>
- <https://developer.oees-kraken.energy/graphql/reference/queries/>
- <https://developer.oees-kraken.energy/graphql/reference/objects/>
- <https://developer.oees-kraken.energy/graphql/changelog/>

---

# Plan de implementación recomendado

## Fase 1 — corregir valores incorrectos

1. Corregir la conversión de `LedgerType.balance`.
2. Añadir pruebas unitarias de importes en unidades menores.
3. Rediseñar el modelo de precios para conservar todos los términos.
4. Aplicar el descuento Sun Club solo cuando el contrato lo confirme.
5. Añadir pruebas de precios por periodo y de una cuenta sin Sun Club.

**Resultado esperado:** ningún sensor monetario ni coste estimado debe presentar un valor con una escala incorrecta o un descuento no contratado.

## Fase 2 — evitar truncados y pérdida de datos

1. Implementar paginación de mediciones.
2. Validar octubre de 2025 con 745 puntos horarios.
3. Implementar paginación de créditos.
4. Hacer explícitos los límites máximos y el indicador de truncado.

**Resultado esperado:** ningún rango solicitado debe truncarse silenciosamente.

## Fase 3 — eliminar dependencias obsoletas

1. Migrar Solar Wallet a ledgers y permisos de transferencia.
2. Migrar Intelligent Go a `devices`.
3. Mantener fallback temporal solo si se justifica por compatibilidad.
4. Probar payloads con funciones activas y funciones ausentes.

**Resultado esperado:** las operaciones opcionales seguirán funcionando después de la retirada de los campos legacy.

## Fase 4 — robustez y degradación parcial

1. Normalizar timeout, JSON inválido y errores HTTP.
2. Clasificar errores GraphQL por código y no solo por texto.
3. Separar el coordinator por grupos de criticidad.
4. Conservar últimos datos válidos de operaciones opcionales.
5. Mejorar la selección multi-cuenta.
6. Aclarar `end_date` y añadir pruebas de su semántica.

**Resultado esperado:** un fallo puntual de una función no deja indisponible toda la integración.

## Fase 5 — validación final

Ejecutar como mínimo:

```bash
rtk python3 -m compileall custom_components tools
rtk python3 -m pytest -q
rtk python3 tools/probe_octopus_endpoints.py
rtk python3 tools/verify_ha_mapping.py
```

Añadir, antes de cerrar la auditoría:

- pruebas HTTP simuladas de paginación;
- prueba del saldo `-13622 -> -136.22`;
- prueba de una factura moderna;
- prueba de errores de permiso no-auth;
- prueba de timeout;
- prueba de degradación parcial del coordinator;
- prueba de DST con 745 puntos.

---

# Validación realizada durante la auditoría

## API real

El probe live respondió `ok` para:

- autenticación;
- `ViewerAccount`;
- `ViewerProperty`;
- `Agreement`;
- `BillingInfo`;
- `Bills`;
- `Bill`/PDF;
- créditos;
- mediciones diarias;
- mediciones horarias;
- devices;
- referrals.

También se comprobaron por separado Solar Wallet, KrakenFlex y `flexPlannedDispatches`. No se imprimieron credenciales, tokens, URLs firmadas ni identificadores crudos.

Resultados relevantes:

- una cuenta eléctrica y ningún gas;
- ledger `SPAIN_ELECTRICITY_LEDGER`;
- 15 créditos;
- 12 facturas y más páginas disponibles;
- 3 términos variables y 2 fijos en el acuerdo;
- Solar Wallet no activo en la cuenta probada;
- ningún dispositivo operativo devuelto por `devices`;
- 744 puntos horarios devueltos en el caso reproducido, con 745 disponibles según `totalCount`.

## Tests

En un entorno aislado con Python 3.13, `pytest`, `aiohttp`, `tzdata` y `voluptuous`:

```text
38 passed in 0.95s
```

También pasó la compilación de Python. Esta era la línea base histórica; la validación final de cierre se registra a continuación y amplía la cobertura con regresiones específicas.

---

# Privacidad y seguridad

La integración no debe guardar ni publicar:

- email, contraseña, cookies o tokens;
- número de cuenta, ledger, property ID o CUPS;
- dirección, NIF o teléfono;
- IDs crudos de factura;
- PDFs ni URLs firmadas.

La descarga de facturas mediante `/api/octopus_spain/invoice/{invoice_id_hash}` y `requires_auth = True` es una decisión correcta: evita que una URL de descarga accesible sin autenticación exponga documentos privados.

Los cambios futuros deben conservar estas garantías y evitar incluir payloads completos de Kraken en estados, atributos, logs o diagnósticos.

---

# Criterio para cerrar la auditoría

**Estado final: CUMPLIDO (2026-07-28).** Mapeo de requisitos a evidencia:

- **Importes monetarios:** P0.1 y P2.2 convierten ledger/facturas desde unidades menores; P0.2 conserva precios con/sin impuestos por separado. Regresiones `-13622 -> -136.22` y factura moderna.
- **Contrato real:** P0.2 usa Punta/Llano/Valle, laborables/fines de semana y Sun Club únicamente si lo marca el producto; validación live 3/3 términos variables y 2/2 fijos sin/con impuestos.
- **Sin truncado silencioso:** P0.3 y P2.1 recorren cursors; límites defensivos publican `truncated`. Octubre de 2025 devolvió 745/745 puntos en vivo.
- **Sin campos deprecated:** búsquedas en código no encuentran los tres campos Solar Wallet legacy ni `registeredKrakenflexDevice`; queries modernas validadas en vivo.
- **Errores:** timeout/JSON, auth, permisos, rate limit y temporales tienen rutas y pruebas distintas.
- **Degradación parcial:** facturas, créditos, Solar Wallet e Intelligent Go conservan último dato válido o degradan sin derribar contrato/billing/mediciones; auth continúa siendo fatal.
- **Multi-cuenta:** config flow ofrece selección redacted cuenta/propiedad; servicios ambiguos exigen `config_entry_id`.
- **Rango temporal:** `end_date` está documentado y probado como fin exclusivo `[start_date, end_date)`.
- **Validación:** suite final superior a la línea base de 38, compilación, probe live, verificación de mapeo y `git diff --check` ejecutados correctamente.

## Resumen final de cambios

Se corrigieron escalas monetarias, modelado multiperiodo/Sun Club, paginación de mediciones y créditos, factura moderna, migraciones GraphQL de Solar Wallet/Intelligent Go, transporte y clasificación de errores, degradación parcial, selección multi-cuenta y contrato de fechas. Las queries/herramientas live se actualizaron en paralelo y todas las evidencias se mantuvieron redacted.

## Validación final

Ejecutada el **2026-07-28**:

- `py -m compileall custom_components tools` → **correcto**.
- `py -m pytest -q` → **70 passed in 0.21s** (línea base: 38).
- `py tools/probe_octopus_endpoints.py` → **14 operaciones `ok`**, informe local redacted e ignorado por Git.
- `py tools/verify_ha_mapping.py` → **correcto**: contrato con 3 términos variables, 12 facturas/documentos, 15 créditos, mediciones 31/48; todos los identificadores mostrados fueron hashes redacted.
- `py tools/smoke_test_web_flow.py` → **no utilizable como evidencia**: el login web no creó la cookie refresh esperada y el script terminó con `Refresh token cookie not found`; no afecta al cliente GraphQL directo y queda registrado como limitación de esa herramienta.
- Validación paginada live de octubre de 2025 → **745 puntos / totalCount 745 / truncated false**.
- Selección live de cuenta/propiedad → **1 suministro utilizable**, con hashes redacted presentes; fixtures cubren múltiples cuentas y múltiples propiedades.
- Validación live agregada → precios **3 sin impuestos + 3 con impuestos**, potencia **2 + 2**, factura moderna completa, Solar Wallet moderno disponible como operación, Intelligent Go moderno con elegibilidad separada de registro.
- `rg` de campos deprecated en `custom_components`, `tests` y `tools` → **sin coincidencias**.
- Validación JSON/YAML → **correcta**.
- Escaneo local de patrones sensibles en archivos modificados → **sin credenciales, tokens, cuentas reales, CUPS ni URLs firmadas**; solo patrones deliberados de redacción.
- `git diff --check` → **correcto**; Git solo informa de su futura normalización LF→CRLF.
- `git status --short --untracked-files=all` → únicamente los archivos modificados/nuevos enumerados en esta auditoría; el documento empezó como cambio preexistente del usuario y se conservó como documento vivo.

Revisión del diff completo: no se detectaron cambios destructivos, datos privados ni refactors fuera del ámbito. No se creó commit ni se hizo push.

## Limitaciones globales restantes

- No fue posible validar en vivo el payload positivo de Solar Wallet ni un dispositivo Intelligent Go registrado porque la cuenta disponible no tiene esas funciones activas; ambos casos positivos tienen fixtures de regresión y las queries modernas sí se validaron contra el schema/API real.
- No se migra el histórico erróneo ya almacenado por Home Assistant; los estados nuevos quedan corregidos.
- Los festivos nacionales distintos de fines de semana no se obtienen del schema actual y no se modelan; esta limitación permanece documentada en P0.2.
- Los límites defensivos son 10.000 mediciones y 5.000 créditos/cinco años; alcanzar un límite publica `truncated: true`.
