// ---------------------------------------------------------------------------
// functions.bicep — Flex Consumption Function App (Python 3.11, identity-based)
//
// Uses Flex Consumption (FC1) with managed-identity storage access. This avoids
// storage account shared keys entirely, which is required in subscriptions that
// enforce `allowSharedKeyAccess = false` via Azure Policy.
// ---------------------------------------------------------------------------

@description('Name of the Function App.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Name of the App Service Plan (Flex Consumption).')
param appServicePlanName string

@description('Name of the Storage Account used for host state and deployment.')
param storageAccountName string

@description('Blob container used for uploaded dispute evidence documents.')
param documentsContainerName string = 'documents'

@description('Application Insights connection string.')
param appInsightsConnectionString string

@description('URI of the Key Vault.')
param keyVaultUri string

@description('Azure Cosmos DB endpoint URI.')
param cosmosEndpoint string = ''

@description('Azure Cosmos DB database name.')
param cosmosDatabaseName string = ''

@description('Case store backend: "cosmos" for Azure Cosmos DB, "synthetic" for mock data.')
param caseStore string = 'cosmos'

@description('Principal ID of the deploying user/service-principal (granted blob data access to upload the deployment package).')
param deployerPrincipalId string = ''

@description('Type of the deploying principal: User (local dev) or ServicePrincipal (CI/CD).')
@allowed([
  'User'
  'ServicePrincipal'
])
param deployerPrincipalType string = 'User'

@description('Blob container used for the Flex Consumption deployment package.')
param deploymentContainerName string = 'deploymentpackage'

@description('Origins allowed to call the Function App API via CORS (used by SWAs that reach the API via absolute URL instead of a linked backend).')
param corsAllowedOrigins array = []

@description('Azure AI Search endpoint for the Evidence Retrieval Agent (#12). Empty disables search (retrieval returns a graceful stub).')
param searchEndpoint string = ''

@description('Azure AI Search index name holding dispute rules/precedents.')
param searchIndexName string = 'dispute-knowledge'

@description('Semantic configuration name on the AI Search index (L2 reranking).')
param searchSemanticConfig string = 'dispute-semantic'

@description('Azure AI Foundry embeddings endpoint (Cohere embed-v-4-0) for hybrid vector search. Empty leaves retrieval on keyword+semantic only. The Function App also needs AZURE_EMBED_KEY set as a secure setting / Key Vault reference to enable vectors.')
param embedEndpoint string = ''

@description('Embeddings model deployment name for hybrid vector search.')
param embedDeployment string = 'embed-v-4-0'

@description('Azure AI Foundry project endpoint for optional grounded synthesis. Empty disables the LLM grounding layer (raw search results are returned).')
param foundryProjectEndpoint string = ''

@description('Resource ID of the VNet-integration subnet (delegated to Microsoft.App/environments) for outbound private connectivity to storage/Cosmos private endpoints.')
param vnetIntegrationSubnetId string = ''

@description('Route all outbound traffic through the VNet integration subnet (required so storage/Cosmos calls resolve via private endpoints instead of the public internet).')
param vnetRouteAllEnabled bool = true

// Built-in role definition IDs
var storageBlobDataOwnerId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageBlobDataContributorId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageQueueDataContributorId = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var storageTableDataContributorId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'

// ---------------------------------------------------------------------------
// Existing Storage Account + deployment container
// ---------------------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' existing = {
  parent: storageAccount
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: deploymentContainerName
  properties: {
    publicAccess: 'None'
  }
}

// ---------------------------------------------------------------------------
// Flex Consumption plan (FC1)
// ---------------------------------------------------------------------------
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  kind: 'functionapp'
  properties: {
    reserved: true // Linux
  }
}

// ---------------------------------------------------------------------------
// Flex Consumption Function App (Python 3.11)
// ---------------------------------------------------------------------------
resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    // Private networking (Phase 1 — see .squad/decisions.md "Decision Proposal:
    // MANDATORY Private Networking"): outbound VNet integration so the
    // Functions runtime reaches storage (blob/queue/table) and Cosmos DB via
    // their private endpoints instead of the public internet, now that both
    // have publicNetworkAccess: Disabled. virtualNetworkSubnetId is the same
    // property used for classic App Service VNet integration; for Flex
    // Consumption (FC1) the subnet must be delegated to
    // `Microsoft.App/environments` (verified at implementation time — FC1
    // does NOT use the classic `Microsoft.Web/serverFarms` delegation).
    virtualNetworkSubnetId: !empty(vnetIntegrationSubnetId) ? vnetIntegrationSubnetId : null
    vnetRouteAllEnabled: vnetRouteAllEnabled
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}${deploymentContainerName}'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 100
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: '3.11'
      }
    }
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccountName
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'KEY_VAULT_URI'
          value: keyVaultUri
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosEndpoint
        }
        {
          name: 'COSMOS_DATABASE_NAME'
          value: cosmosDatabaseName
        }
        {
          name: 'AZURE_STORAGE_MODE'
          value: 'azure'
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_NAME'
          value: storageAccountName
        }
        {
          name: 'AZURE_STORAGE_CONTAINER'
          value: documentsContainerName
        }
        {
          name: 'CASE_STORE'
          value: caseStore
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: searchEndpoint
        }
        {
          name: 'AZURE_SEARCH_INDEX'
          value: searchIndexName
        }
        {
          name: 'AZURE_SEARCH_SEMANTIC_CONFIG'
          value: searchSemanticConfig
        }
        {
          name: 'AZURE_EMBED_ENDPOINT'
          value: embedEndpoint
        }
        {
          name: 'AZURE_EMBED_DEPLOYMENT'
          value: embedDeployment
        }
        {
          name: 'FOUNDRY_PROJECT_ENDPOINT'
          value: foundryProjectEndpoint
        }
      ]
      cors: {
        allowedOrigins: corsAllowedOrigins
        supportCredentials: false
      }
    }
  }
}

// ---------------------------------------------------------------------------
// App Service Authentication (EasyAuth v2) — explicitly disabled.
//
// SECOND occurrence of an implicit Azure platform side effect breaking the
// portal (the first was linked-backend exclusivity — see staticwebapp.bicep).
// Linking a Function App as a Static Web App backend (`linkedBackends`, used
// by the `web` SWA above) causes Azure to auto-provision App Service Auth v2
// on the Function App itself, with `globalValidation.requireAuthentication =
// true` and ONLY that one SWA registered as an allowed `azureStaticWebApps`
// identity provider. This silently 401s every other caller — including the
// `portal` SWA, which reaches this API directly via CORS + an absolute URL
// (see main.bicep) and has no linked-backend identity token to present.
//
// This repo's auth model is function-level key/anonymous auth
// (`AuthLevel.ANONYMOUS` in src/api/function_app.py) plus the CORS allow-list
// above — NOT platform EasyAuth. Declaring this resource explicitly, rather
// than leaving it as an implicit by-product of `linkedBackends`, makes the
// setting visible, reviewable, and idempotent across `azd provision` runs.
// Acceptable for this MVP/demo; revisit (e.g. APIM, or per-caller EasyAuth
// with multiple registered identity providers) for production hardening.
// ---------------------------------------------------------------------------
resource authSettings 'Microsoft.Web/sites/config@2023-12-01' = {
  parent: functionApp
  name: 'authsettingsV2'
  properties: {
    platform: {
      enabled: false
    }
    globalValidation: {
      requireAuthentication: false
      unauthenticatedClientAction: 'AllowAnonymous'
    }
  }
}

// ---------------------------------------------------------------------------
// Role assignments — Function App managed identity → storage data access
// (Durable Functions needs blob + queue + table; deployment needs blob)
// ---------------------------------------------------------------------------
resource blobOwnerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, storageBlobDataOwnerId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource queueAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, storageQueueDataContributorId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataContributorId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource tableAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, storageTableDataContributorId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageTableDataContributorId)
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Deploying principal needs blob data access to upload the package (shared keys disabled)
resource deployerBlobAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(storageAccount.id, deployerPrincipalId, storageBlobDataContributorId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorId)
    principalId: deployerPrincipalId
    principalType: deployerPrincipalType
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output functionAppName string = functionApp.name
output functionAppUri string = 'https://${functionApp.properties.defaultHostName}'
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppId string = functionApp.id
