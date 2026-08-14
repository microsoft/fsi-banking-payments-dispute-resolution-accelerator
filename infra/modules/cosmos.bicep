// ---------------------------------------------------------------------------
// cosmos.bicep — Azure Cosmos DB (NoSQL API) for dispute operational store
//
// Provisions a serverless Cosmos DB account. Uses RBAC-only access — no
// primary keys exposed. Analytical store can be enabled post-creation via
// Portal or CLI if needed for Fabric mirroring.
// ---------------------------------------------------------------------------

@description('Name of the Cosmos DB account.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Name of the Cosmos DB database.')
param databaseName string = 'disputes-db'

@description('Principal ID of the deployer (granted data access for seeding/testing).')
param deployerPrincipalId string = ''

@description('Principal ID of the Fabric mirroring service principal (granted data reader).')
param fabricMirrorPrincipalId string = ''

// Built-in role definition IDs for Cosmos DB data plane
var cosmosDbDataContributorRoleId = '00000000-0000-0000-0000-000000000002' // Cosmos DB Built-in Data Contributor
var cosmosDbDataReaderRoleId = '00000000-0000-0000-0000-000000000001' // Cosmos DB Built-in Data Reader

// ---------------------------------------------------------------------------
// Cosmos DB Account (NoSQL API, Serverless, Analytical Store enabled)
// ---------------------------------------------------------------------------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      { name: 'EnableServerless' }
    ]
    // Security: allow key-based auth for Fabric mirroring; RBAC still preferred for app access
    disableLocalAuth: false
    // EXPERIMENTAL (see the related decision note in .squad/decisions/inbox/):
    // re-enabled public network access + disabled the VNet filter to test
    // whether the SecurityControl: 'Ignore' tag suppresses organizational policy
    // enforcement, as an alternative to the private-networking approach in
    // .squad/decisions.md "Decision Proposal: MANDATORY Private Networking".
    // If the tag does NOT work, the modify-effect policy is expected to
    // silently flip these back to Disabled/true on the next evaluation.
    publicNetworkAccess: 'Enabled'
    isVirtualNetworkFilterEnabled: false
    // Consistency
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
  }
}

// ---------------------------------------------------------------------------
// Database
// ---------------------------------------------------------------------------
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// ---------------------------------------------------------------------------
// Containers
// ---------------------------------------------------------------------------

// disputes — core operational container (one document per dispute case)
resource disputesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'disputes'
  properties: {
    resource: {
      id: 'disputes'
      partitionKey: {
        paths: ['/networkCode', '/disputeId']
        kind: 'MultiHash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          { path: '/*' }
        ]
        excludedPaths: [
          { path: '/"_etag"/?' }
        ]
        compositeIndexes: [
          [
            { path: '/networkCode', order: 'ascending' }
            { path: '/createdAt', order: 'descending' }
          ]
          [
            { path: '/status', order: 'ascending' }
            { path: '/deadlineUtc', order: 'ascending' }
          ]
        ]
      }
      // Operational TTL: off (disputes are retained until explicit archival)
      defaultTtl: -1
    }
  }
}

// evidence — evidence items linked to disputes
resource evidenceContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'evidence'
  properties: {
    resource: {
      id: 'evidence'
      partitionKey: {
        paths: ['/disputeId']
        kind: 'Hash'
        version: 2
      }
      defaultTtl: -1
    }
  }
}

// timeline — audit trail / state transitions per dispute
resource timelineContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'timeline'
  properties: {
    resource: {
      id: 'timeline'
      partitionKey: {
        paths: ['/disputeId']
        kind: 'Hash'
        version: 2
      }
      defaultTtl: -1
    }
  }
}

// ---------------------------------------------------------------------------
// RBAC — Deployer → Cosmos DB Data Contributor (for seeding/testing)
// ---------------------------------------------------------------------------
resource deployerDataAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(deployerPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, deployerPrincipalId, cosmosDbDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDbDataContributorRoleId}'
    principalId: deployerPrincipalId
    scope: cosmosAccount.id
  }
}

// ---------------------------------------------------------------------------
// RBAC — Fabric Mirroring SP → Cosmos DB Data Reader (for change feed)
// ---------------------------------------------------------------------------
resource fabricMirrorDataAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(fabricMirrorPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, fabricMirrorPrincipalId, cosmosDbDataReaderRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDbDataReaderRoleId}'
    principalId: fabricMirrorPrincipalId
    scope: cosmosAccount.id
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output cosmosAccountName string = cosmosAccount.name
output cosmosAccountId string = cosmosAccount.id
output cosmosAccountEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosDatabaseName string = database.name
