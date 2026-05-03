# Octopus Spain HAR GraphQL operation catalog

Catálogo generado desde HARs locales ignorados por Git. No incluye valores de variables ni respuestas.

## `AccountCreditsQuery`

- HARs: octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: accountNumber, ledgerNumber
- Campos observados:
  - `AccountCreditsQuery`
  - `accountNumber`
  - `ledgerNumber`
  - `account`
  - `ledgers`
  - `transactions`
  - `fromDate`
  - `pageInfo`
  - `hasNextPage`
  - `endCursor`
  - `edges`
  - `node`
  - `__typename`
  - `Credit`
  - `amounts`
  - `gross`
  - `getCreditsSummary_Credit`
  - `isSunClubCredit_Credit`
  - `isIOGOCredit_Credit`
  - `isSolarWalletCredit_Credit`
  - `isValidCreditReason_Credit`
  - `id`
  - `createdAt`
  - `reasonCode`
  - `getTotalCredits_Credit`
  - `getCurrentMonthTotalCredits_Credit`
  - `getLastMonthTotalCredits_Credit`
  - `sortCreditsByDate_Credit`

## `AccountReferrals`

- HARs: octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: accountNumber, after, first
- Campos observados:
  - `AccountReferrals`
  - `accountNumber`
  - `ReferralStatus`
  - `account`
  - `referrals`
  - `edgeCount`
  - `edges`
  - `cursor`
  - `node`
  - `id`
  - `paymentDate`
  - `schemeType`
  - `referredUserName (sensible/no exponer)`
  - `paymentStatus`
  - `referredUserJoinDate`
  - `code`
  - `referredUserPaymentAmount`
  - `referringUserPaymentAmount`
  - `combinedPaymentAmount`
  - `pageInfo`
  - `hasNextPage`
  - `hasPreviousPage`
  - `startCursor`
  - `endCursor`
  - `totalCount`
  - `activeReferralSchemes`
  - `domestic`
  - `referralUrl (sensible/no exponer)`

## `Agreement`

- HARs: octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: id
- Campos observados:
  - `Agreement`
  - `id`
  - `agreement`
  - `validFrom`
  - `validTo`
  - `product`
  - `displayName`
  - `code`
  - `prices`
  - `fixedTerm`
  - `variableTerm`
  - `fixedTermUnits`
  - `variableTermUnits`
  - `dailyFee`
  - `dailyFeeWithTaxes`
  - `surplusRate`
  - `params`

## `Bill`

- HARs: octopusenergy-facturas-click-detalle.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: accountNumber, ledgerNumber, statementId
- Campos observados:
  - `Bill`
  - `accountNumber`
  - `ledgerNumber`
  - `statementId`
  - `account`
  - `ledgers`
  - `number`
  - `ledgerType`
  - `supportsInvoices`
  - `statements`
  - `edges`
  - `node`
  - `id`
  - `pdfUrl (sensible/no exponer)`
  - `invoices`
  - `invoiceId`

## `Bills`

- HARs: octopusenergy-facturas-click-detalle.es.har, octopusenergy-facturas.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: accountNumber, first, ledgerNumber
- Campos observados:
  - `Bills`
  - `accountNumber`
  - `ledgerNumber`
  - `account`
  - `ledgers`
  - `number`
  - `ledgerType`
  - `supportsInvoices`
  - `statements`
  - `edges`
  - `node`
  - `id`
  - `consumptionStartDate`
  - `earliestChargeAt`
  - `consumptionEndDate`
  - `latestChargeAt`
  - `pageInfo`
  - `hasNextPage`
  - `endCursor`
  - `invoices`
  - `FINALIZED_AT_DESC`
  - `pdfUrl (sensible/no exponer)`

## `LinkedSupplyPointAccounts`

- HARs: octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: ninguna
- Campos observados:
  - `LinkedSupplyPointAccounts`
  - `viewer`
  - `accounts`
  - `Account`
  - `DashboardAccountMainInfo_Account`
  - `number`
  - `billingAddress (sensible/no exponer)`
  - `properties`
  - `postcode`
  - `richAddress (sensible/no exponer)`
  - `streetAddress (sensible/no exponer)`
  - `locality`
  - `postalCode`
  - `country`
  - `structuredStreetAddress`
  - `splitAddress (sensible/no exponer)`
  - `electricitySupplyPoints`
  - `id`
  - `gasSupplyPoints`

## `Viewer`

- HARs: octopusenergy-facturas-click-detalle.es.har, octopusenergy-facturas.es.har, octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: ninguna
- Campos observados:
  - `Viewer`
  - `viewer`
  - `givenName`
  - `email (sensible/no exponer)`
  - `mobile (sensible/no exponer)`
  - `preferredName`
  - `accountUserMeta`
  - `firstFamilyName`
  - `secondFamilyName`
  - `nif (sensible/no exponer)`
  - `preferences`
  - `isOptedInToOfferMessages`
  - `accounts`
  - `Account`
  - `number`
  - `createdAt`
  - `accountType`
  - `loggedRepresentative`
  - `properties`
  - `id`
  - `postcode`
  - `splitAddress (sensible/no exponer)`
  - `address (sensible/no exponer)`
  - `electricitySupplyPoints`
  - `cups (sensible/no exponer)`
  - `selfConsumptionCode`
  - `gasSupplyPoints`

## `ViewerAccount`

- HARs: octopusenergy-facturas-click-detalle.es.har, octopusenergy-facturas.es.har, octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: ninguna
- Campos observados:
  - `ViewerAccount`
  - `viewer`
  - `accounts`
  - `Account`
  - `number`
  - `createdAt`
  - `accountType`
  - `billingAddress (sensible/no exponer)`
  - `billingAddressPostcode (sensible/no exponer)`
  - `billingAddressLine1 (sensible/no exponer)`
  - `billingAddressLine2 (sensible/no exponer)`
  - `billingAddressLine3 (sensible/no exponer)`
  - `billingAddressLine4 (sensible/no exponer)`
  - `ledgers`
  - `ledgerType`
  - `balance`
  - `creditTransferPermissionsData`
  - `toTargetLedgers`
  - `ledgerNumber`
  - `validFrom`
  - `validTo`
  - `accountNumber`

## `ViewerProperty`

- HARs: octopusenergy-facturas-click-detalle.es.har, octopusenergy-facturas.es.har, octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: ninguna
- Campos observados:
  - `ViewerProperty`
  - `viewer`
  - `accounts`
  - `Account`
  - `number`
  - `properties`
  - `id`
  - `postcode`
  - `splitAddress (sensible/no exponer)`
  - `address (sensible/no exponer)`
  - `electricitySupplyPoints`
  - `cups (sensible/no exponer)`
  - `selfConsumptionCode`
  - `supplierChangeInProgress`
  - `activeAgreement`
  - `product`
  - `code`
  - `atr`
  - `gasSupplyPoints`

## `getAccountMeasurements`

- HARs: octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: endAt, first, propertyId, startAt, timezone, utilityFilters
- Campos observados:
  - `getAccountMeasurements`
  - `propertyId`
  - `utilityFilters`
  - `UtilityFiltersInput`
  - `startOn`
  - `endOn`
  - `startAt`
  - `endAt`
  - `timezone`
  - `property`
  - `id`
  - `measurements`
  - `edges`
  - `node`
  - `value`
  - `unit`
  - `IntervalMeasurementType`
  - `durationInSeconds`
  - `metaData`
  - `statistics`
  - `costExclTax`
  - `pricePerUnit`
  - `amount`
  - `costCurrency`
  - `estimatedAmount`
  - `costInclTax`
  - `description`
  - `label`
  - `type`

## `getDevices`

- HARs: octopusenergy.es.har
- Endpoints: https://octopusenergy.es/api/graphql/kraken
- Variables: accountNumber
- Campos observados:
  - `getDevices`
  - `accountNumber`
  - `devices`
  - `deviceType`
  - `current`
