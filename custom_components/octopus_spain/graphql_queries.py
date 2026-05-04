"""GraphQL operation documents for Octopus Energy Spain.

These are private Kraken GraphQL operations observed in the Octopus Spain web
application and validated against the direct Kraken endpoint when possible.
Keep operation documents here so the API client remains focused on domain
methods and response mapping.
"""

from __future__ import annotations

AUTH_MUTATION = """
mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
    refreshToken
    refreshExpiresIn
  }
}
"""

VIEWER_ACCOUNT_QUERY = """
query ViewerAccount {
  viewer {
    accounts {
      ... on Account {
        number
        createdAt
        accountType
        ledgers {
          ledgerType
          balance
          number
        }
      }
    }
  }
}
"""

VIEWER_SAFE_QUERY = """
query Viewer {
  viewer {
    preferences {
      isOptedInToOfferMessages
    }
    accounts {
      ... on Account {
        createdAt
        accountType
        properties {
          id
          electricitySupplyPoints {
            status
            selfConsumptionCode
          }
          gasSupplyPoints {
            status
          }
        }
      }
    }
  }
}
"""

VIEWER_PROPERTY_QUERY = """
query ViewerProperty {
  viewer {
    accounts {
      ... on Account {
        number
        properties {
          id
          electricitySupplyPoints {
            status
            activeAgreement {
              id
              product {
                code
                atr
              }
            }
          }
          gasSupplyPoints {
            status
            activeAgreement {
              id
              product {
                code
              }
            }
          }
        }
      }
    }
  }
}
"""

AGREEMENT_QUERY = """
query Agreement($id: ID!) {
  agreement(id: $id) {
    id
    validFrom
    validTo
    product {
      displayName
      code
      prices {
        fixedTerm
        variableTerm
        fixedTermUnits
        variableTermUnits
        dailyFee
        dailyFeeWithTaxes
        surplusRate
      }
      params
    }
  }
}
"""

BILLING_INFO_QUERY = """
query BillingInfo($accountNumber: String!) {
  accountBillingInfo(accountNumber: $accountNumber) {
    ledgers {
      ledgerType
      balance
      statementsWithDetails(first: 1) {
        edges {
          node {
            amount
            consumptionStartDate
            consumptionEndDate
            issuedDate
          }
        }
      }
    }
  }
}
"""

BILLS_QUERY = """
query Bills($accountNumber: String!, $ledgerNumber: String!, $first: Int!, $after: String) {
  account(accountNumber: $accountNumber) {
    ledgers(ledgerNumber: $ledgerNumber) {
      number
      ledgerType
      supportsInvoices
      invoices(first: $first, after: $after, orderBy: FINALIZED_AT_DESC) {
        edges {
          node {
            id
            number
            pdfUrl
            consumptionStartDate: earliestChargeAt
            consumptionEndDate: latestChargeAt
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

BILL_QUERY = """
query Bill($accountNumber: String!, $ledgerNumber: String!, $statementId: Int!, $after: String) {
  account(accountNumber: $accountNumber) {
    ledgers(ledgerNumber: $ledgerNumber) {
      number
      ledgerType
      supportsInvoices
      statements(first: 1, after: $after, statementId: $statementId) {
        edges {
          node {
            id
            pdfUrl
          }
        }
      }
      invoices(first: 1, after: $after, invoiceId: $statementId) {
        edges {
          node {
            id
            pdfUrl
          }
        }
      }
    }
  }
}
"""

CREDITS_QUERY = """
query AccountCreditsQuery($accountNumber: String!, $ledgerNumber: String, $after: String) {
  account(accountNumber: $accountNumber) {
    ledgers(ledgerNumber: $ledgerNumber) {
      transactions(fromDate: "2025-01-01", first: 100, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            __typename
            ... on Credit {
              id
              amounts {
                gross
              }
              createdAt
              reasonCode
            }
          }
        }
      }
    }
  }
}
"""

LINKED_SUPPLY_SAFE_QUERY = """
query LinkedSupplyPointAccounts {
  viewer {
    accounts {
      ... on Account {
        properties {
          electricitySupplyPoints {
            id
          }
          gasSupplyPoints {
            id
          }
        }
      }
    }
  }
}
"""

REFERRALS_SAFE_QUERY = """
query AccountReferrals($accountNumber: String!, $before: String, $after: String, $first: Int, $status: ReferralStatus) {
  account(accountNumber: $accountNumber) {
    referrals(before: $before, after: $after, first: $first, status: $status) {
      edgeCount
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
      totalCount
    }
    activeReferralSchemes {
      domestic {
        referralUrl
      }
    }
  }
}
"""

DEVICES_QUERY = """
query getDevices($accountNumber: String!) {
  devices(accountNumber: $accountNumber) {
    deviceType
    status {
      current
    }
  }
}
"""

MEASUREMENTS_QUERY = """
query getAccountMeasurements(
  $propertyId: ID!
  $first: Int!
  $utilityFilters: [UtilityFiltersInput!]
  $startOn: Date
  $endOn: Date
  $startAt: DateTime
  $endAt: DateTime
  $timezone: String
) {
  property(id: $propertyId) {
    measurements(
      first: $first
      utilityFilters: $utilityFilters
      startOn: $startOn
      endOn: $endOn
      startAt: $startAt
      endAt: $endAt
      timezone: $timezone
    ) {
      edges {
        node {
          value
          unit
          ... on IntervalMeasurementType {
            startAt
            endAt
            durationInSeconds
          }
          metaData {
            statistics {
              costExclTax {
                pricePerUnit {
                  amount
                }
                costCurrency
                estimatedAmount
              }
              costInclTax {
                costCurrency
                estimatedAmount
              }
              value
              description
              label
              type
            }
          }
        }
      }
    }
  }
}
"""
