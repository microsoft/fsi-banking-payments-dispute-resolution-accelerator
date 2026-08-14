// ---------------------------------------------------------------------------
// private-endpoints.bicep — Private endpoints for storage (blob/queue/table)
// and Cosmos DB (Sql), each with a DNS zone group into the matching private
// DNS zone from private-dns.bicep.
// ---------------------------------------------------------------------------

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Subnet resource ID to deploy the private endpoint NICs into.')
param privateEndpointsSubnetId string

@description('Resource ID of the Storage Account.')
param storageAccountId string

@description('Name of the Storage Account (used to build unique PE names).')
param storageAccountName string

@description('Resource ID of the Cosmos DB account.')
param cosmosAccountId string

@description('Name of the Cosmos DB account (used to build unique PE names).')
param cosmosAccountName string

@description('Private DNS zone resource ID for privatelink.blob.core.windows.net.')
param blobZoneId string

@description('Private DNS zone resource ID for privatelink.queue.core.windows.net.')
param queueZoneId string

@description('Private DNS zone resource ID for privatelink.table.core.windows.net.')
param tableZoneId string

@description('Private DNS zone resource ID for privatelink.documents.azure.com.')
param documentsZoneId string

// ---------------------------------------------------------------------------
// Storage — blob private endpoint
// ---------------------------------------------------------------------------
resource peStorageBlob 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: 'pe-storage-blob-${storageAccountName}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointsSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-storage-blob-connection'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource peStorageBlobDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: peStorageBlob
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: blobZoneId
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Storage — queue private endpoint
// ---------------------------------------------------------------------------
resource peStorageQueue 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: 'pe-storage-queue-${storageAccountName}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointsSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-storage-queue-connection'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: [
            'queue'
          ]
        }
      }
    ]
  }
}

resource peStorageQueueDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: peStorageQueue
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'queue'
        properties: {
          privateDnsZoneId: queueZoneId
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Storage — table private endpoint
// ---------------------------------------------------------------------------
resource peStorageTable 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: 'pe-storage-table-${storageAccountName}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointsSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-storage-table-connection'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: [
            'table'
          ]
        }
      }
    ]
  }
}

resource peStorageTableDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: peStorageTable
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'table'
        properties: {
          privateDnsZoneId: tableZoneId
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Cosmos DB — Sql private endpoint
// ---------------------------------------------------------------------------
resource peCosmosSql 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: 'pe-cosmos-sql-${cosmosAccountName}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointsSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-cosmos-sql-connection'
        properties: {
          privateLinkServiceId: cosmosAccountId
          groupIds: [
            'Sql'
          ]
        }
      }
    ]
  }
}

resource peCosmosSqlDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: peCosmosSql
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'documents'
        properties: {
          privateDnsZoneId: documentsZoneId
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output storageBlobPrivateEndpointId string = peStorageBlob.id
output storageQueuePrivateEndpointId string = peStorageQueue.id
output storageTablePrivateEndpointId string = peStorageTable.id
output cosmosSqlPrivateEndpointId string = peCosmosSql.id
