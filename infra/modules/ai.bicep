// ---------------------------------------------------------------------------
// ai.bicep — Azure AI Services (AI Foundry / Document Intelligence)
// ---------------------------------------------------------------------------

@description('Name of the Azure AI Services account.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

// ---------------------------------------------------------------------------
// Azure AI Services
// ---------------------------------------------------------------------------
resource aiServices 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output aiServicesEndpoint string = aiServices.properties.endpoint
output aiServicesId string = aiServices.id
