// ---------------------------------------------------------------------------
// cosmos-rbac.bicep — Grant a principal Cosmos DB Data Contributor access
//
// Separated from cosmos.bicep to break circular dependency: the Function App
// must exist first (to read its managed identity principalId), but Cosmos
// must also exist first (to supply its endpoint to Functions app settings).
// ---------------------------------------------------------------------------

@description('Name of the existing Cosmos DB account.')
param cosmosAccountName string

@description('Principal ID to grant Cosmos DB data plane access.')
param principalId string

// Cosmos DB Built-in Data Contributor
var cosmosDbDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource dataContributorAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, principalId, cosmosDbDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDbDataContributorRoleId}'
    principalId: principalId
    scope: cosmosAccount.id
  }
}
