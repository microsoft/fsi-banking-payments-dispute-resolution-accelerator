// ---------------------------------------------------------------------------
// storage.bicep — Storage Account (Durable Functions state store)
// ---------------------------------------------------------------------------

@description('Name of the Storage Account.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Blob container used for inbound dispute network files.')
param ingestContainerName string = 'ingest'

@description('Blob container used for uploaded dispute evidence documents.')
param documentsContainerName string = 'documents'

// ---------------------------------------------------------------------------
// Storage Account
// ---------------------------------------------------------------------------
module storageAccount 'br/public:avm/res/storage/storage-account:0.9.1' = {
  name: 'storageAccount'
  params: {
    name: name
    location: location
    tags: tags
    skuName: 'Standard_LRS'
    kind: 'StorageV2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    // EXPERIMENTAL (see the related decision note in .squad/decisions/inbox/):
    // re-enabled public network access + Allow default action to test whether
    // the SecurityControl: 'Ignore' tag suppresses organizational policy enforcement,
    // as an alternative to the private-networking approach in
    // .squad/decisions.md "Decision Proposal: MANDATORY Private Networking".
    // If the tag does NOT work, the modify-effect policy is expected to
    // silently flip these back to Disabled/Deny on the next evaluation.
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

resource storageAccountResource 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: name
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' existing = {
  name: 'default'
  parent: storageAccountResource
}

resource ingestContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: ingestContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: documentsContainerName
  properties: {
    publicAccess: 'None'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output storageAccountName string = storageAccount.outputs.name
output storageAccountId string = storageAccount.outputs.resourceId
output primaryBlobEndpoint string = storageAccount.outputs.primaryBlobEndpoint
output ingestContainerName string = ingestContainer.name
output documentsContainerName string = documentsContainer.name
