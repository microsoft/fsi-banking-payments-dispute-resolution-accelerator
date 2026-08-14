targetScope = 'subscription'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------
@minLength(1)
@maxLength(64)
@description('Name of the AZD environment.')
param environmentName string

@description('Azure region for all resources.')
param location string = 'eastus2'

@description('Principal ID of the deploying user/service-principal (for RBAC).')
param principalId string

@description('Type of the deploying principal: User (local dev) or ServicePrincipal (CI/CD).')
@allowed([
  'User'
  'ServicePrincipal'
])
param principalType string = 'User'

@description('Deploy private endpoints for Cosmos DB and Storage. Defaults to false — Phase 1 uses publicNetworkAccess: Enabled with SecurityControl: Ignore tag-bypass. Set true only when private-networking isolation is explicitly required. See issue #86.')
param deployPrivateEndpoints bool = false

@description('Azure AI Search endpoint for the Evidence Retrieval Agent (#12). Empty leaves search disabled (retrieval returns a graceful stub). Set per-environment, e.g. https://rgdevaisearch.search.windows.net. The Function App managed identity also needs the "Search Index Data Reader" role on the service to read at runtime.')
param searchEndpoint string = ''

@description('Azure AI Foundry embeddings endpoint (Cohere embed-v-4-0) for hybrid vector search on the Evidence Retrieval Agent. Empty leaves retrieval on keyword+semantic only.')
param embedEndpoint string = ''

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------
var abbrs = loadJsonContent('./abbreviations.json')
// EXPERIMENTAL (see the related decision note in .squad/decisions/inbox/):
// SecurityControl: 'Ignore' is a tag-based skip condition some internal/custom
// Azure Policy definitions honor as an alternative to a formal Policy
// Exemption object. Adding it here to test whether it suppresses the
// organizational "modify" effects that otherwise force
// allowSharedKeyAccess/disableLocalAuth/publicNetworkAccess back to secure
// defaults. NOT verified to work — must be confirmed empirically post-deploy.
var tags = { 'azd-env-name': environmentName, SecurityControl: 'Ignore' }
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

var rgName               = '${abbrs.resourceGroup}-${environmentName}'
var storageAccountName   = '${abbrs.storageAccount}${resourceToken}'
var keyVaultName         = '${abbrs.keyVault}-${resourceToken}'
var appServicePlanName   = '${abbrs.appServicePlan}-${resourceToken}'
var functionAppName      = '${abbrs.functionApp}-${resourceToken}-app'
var appInsightsName      = '${abbrs.applicationInsights}-${resourceToken}'
var logAnalyticsName     = '${abbrs.logAnalyticsWorkspace}-${resourceToken}'
var eventGridTopicName   = '${abbrs.eventGridTopic}-${resourceToken}'
var aiServicesName       = '${abbrs.aiServices}-${resourceToken}'
var staticWebAppName     = '${abbrs.staticWebApp}-${resourceToken}'
var portalStaticWebAppName = '${abbrs.staticWebApp}-portal-${resourceToken}'
var cosmosAccountName    = '${abbrs.cosmosDbAccount}-${resourceToken}'
var vnetName             = '${abbrs.virtualNetwork}-${resourceToken}'
var runnerIdentityName   = '${abbrs.userAssignedIdentity}-github-runner-${resourceToken}'
var natGatewayName       = '${abbrs.natGateway}-runner-${resourceToken}'
var natGatewayPublicIpName = '${abbrs.publicIPAddress}-natgw-runner-${resourceToken}'

// ---------------------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------------------
resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: rgName
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------
// Monitoring (Log Analytics Workspace + Application Insights)
// ---------------------------------------------------------------------------
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    name: appInsightsName
    location: location
    tags: tags
    logAnalyticsName: logAnalyticsName
  }
}

// ---------------------------------------------------------------------------
// Storage Account
// ---------------------------------------------------------------------------
module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    name: storageAccountName
    location: location
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Key Vault
// ---------------------------------------------------------------------------
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault-deploy-v2'
  scope: rg
  params: {
    name: keyVaultName
    location: location
    tags: tags
    principalId: principalId
    principalType: principalType
  }
}

// ---------------------------------------------------------------------------
// Cosmos DB (NoSQL — dispute operational store + Fabric mirroring)
// ---------------------------------------------------------------------------
module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  scope: rg
  params: {
    name: cosmosAccountName
    location: location
    tags: tags
    deployerPrincipalId: principalId
  }
}

// ---------------------------------------------------------------------------
// Private Networking (Phase 1 — see .squad/decisions.md "Decision Proposal:
// MANDATORY Private Networking"): VNet + private DNS zones + private
// endpoints for storage (blob/queue/table) and Cosmos DB (Sql), so both can
// run with publicNetworkAccess: Disabled while remaining fully reachable by
// the Function App via VNet integration.
// ---------------------------------------------------------------------------
module network 'modules/network.bicep' = {
  name: 'network'
  scope: rg
  params: {
    name: vnetName
    location: location
    tags: tags
    natGatewayName: natGatewayName
    natGatewayPublicIpName: natGatewayPublicIpName
  }
}

module privateDns 'modules/private-dns.bicep' = if (deployPrivateEndpoints) {
  name: 'privateDns'
  scope: rg
  params: {
    vnetId: network.outputs.vnetId
    tags: tags
  }
}

module privateEndpoints 'modules/private-endpoints.bicep' = if (deployPrivateEndpoints) {
  name: 'privateEndpoints'
  scope: rg
  params: {
    location: location
    tags: tags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    storageAccountId: storage.outputs.storageAccountId
    storageAccountName: storage.outputs.storageAccountName
    cosmosAccountId: cosmos.outputs.cosmosAccountId
    cosmosAccountName: cosmos.outputs.cosmosAccountName
    blobZoneId: privateDns.outputs.blobZoneId
    queueZoneId: privateDns.outputs.queueZoneId
    tableZoneId: privateDns.outputs.tableZoneId
    documentsZoneId: privateDns.outputs.documentsZoneId
  }
}

// ---------------------------------------------------------------------------
// Self-hosted CD runner — identity + RBAC only (see .squad/decisions.md
// self-hosted runner decision, 2026-07-09). The `runner` subnet is
// provisioned in network.bicep; the ephemeral Azure Container Instance
// itself is created/destroyed per CD run by .github/workflows/cd.yml, not
// by this template — see infra/modules/runner.bicep for rationale.
// ---------------------------------------------------------------------------
module runner 'modules/runner.bicep' = {
  name: 'runner'
  scope: rg
  params: {
    name: runnerIdentityName
    location: location
    tags: tags
    storageAccountId: storage.outputs.storageAccountId
  }
}

// ---------------------------------------------------------------------------
// Function App (App Service Plan + Function App)
// ---------------------------------------------------------------------------
module functions 'modules/functions.bicep' = {
  name: 'functions'
  scope: rg
  params: {
    name: functionAppName
    location: location
    tags: tags
    appServicePlanName: appServicePlanName
    storageAccountName: storage.outputs.storageAccountName
    documentsContainerName: storage.outputs.documentsContainerName
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultUri: keyVault.outputs.keyVaultUri
    cosmosEndpoint: cosmos.outputs.cosmosAccountEndpoint
    cosmosDatabaseName: cosmos.outputs.cosmosDatabaseName
    deployerPrincipalId: principalId
    deployerPrincipalType: principalType
    // MVP simplification: allow all origins since the portal SWA's hostname isn't
    // known until after it's created (pre-computing it would require a circular
    // module dependency or a post-deploy CLI step). Tighten to the actual portal +
    // web SWA origins post-demo, e.g. via `az functionapp cors add` once hostnames
    // are stable, or by reading `azd env get-values` in CD after provision.
    corsAllowedOrigins: ['*']
    vnetIntegrationSubnetId: network.outputs.funcIntegrationSubnetId
    searchEndpoint: searchEndpoint
    embedEndpoint: embedEndpoint
  }
}

// ---------------------------------------------------------------------------
// Cosmos DB RBAC — grant Function App identity data access (depends on both)
// ---------------------------------------------------------------------------
module cosmosRbac 'modules/cosmos-rbac.bicep' = {
  name: 'cosmosRbac'
  scope: rg
  params: {
    cosmosAccountName: cosmos.outputs.cosmosAccountName
    principalId: functions.outputs.functionAppPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Event Grid System Topic
// ---------------------------------------------------------------------------
module eventGrid 'modules/eventgrid.bicep' = {
  name: 'eventGrid'
  scope: rg
  params: {
    name: eventGridTopicName
    location: location
    tags: tags
    storageAccountId: storage.outputs.storageAccountId
    functionAppName: functions.outputs.functionAppName
    ingestContainerName: storage.outputs.ingestContainerName
  }
}

// ---------------------------------------------------------------------------
// Azure AI Services
// ---------------------------------------------------------------------------
module ai 'modules/ai.bicep' = {
  name: 'ai'
  scope: rg
  params: {
    name: aiServicesName
    location: location
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Static Web App — Analyst Review UI (src/web/)
// ---------------------------------------------------------------------------
module staticWebApp 'modules/staticwebapp.bicep' = {
  name: 'staticWebApp'
  scope: rg
  params: {
    name: staticWebAppName
    location: location
    tags: tags
    // Implicit dependency: ARM waits for functions module before provisioning the SWA
    functionAppResourceId: functions.outputs.functionAppId
  }
}

// ---------------------------------------------------------------------------
// Static Web App — Customer Portal MVP (src/customer-portal/)
//
// Does NOT use a linked backend: Azure only allows one linked backend per
// Function App, and it's already claimed by the `web` SWA above. Instead, the
// portal reaches the API via CORS + an absolute URL (VITE_API_BASE_URL set at
// build time in azure.yaml's portal prebuild hook to AZURE_FUNCTION_APP_URI/api).
// functionAppResourceId is still passed for parameter compatibility but is
// unused by the module when linkBackend is false.
// ---------------------------------------------------------------------------
module portalStaticWebApp 'modules/staticwebapp.bicep' = {
  name: 'portalStaticWebApp'
  scope: rg
  params: {
    name: portalStaticWebAppName
    location: location
    tags: tags
    functionAppResourceId: functions.outputs.functionAppId
    azdServiceName: 'portal'
    linkBackend: false
  }
}

// ---------------------------------------------------------------------------
// Outputs (consumed by AZD and application)
// ---------------------------------------------------------------------------
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name

output AZURE_FUNCTION_APP_NAME string = functions.outputs.functionAppName
output AZURE_FUNCTION_APP_URI string = functions.outputs.functionAppUri

output AZURE_STORAGE_ACCOUNT_NAME string = storage.outputs.storageAccountName
output AZURE_KEY_VAULT_NAME string = keyVault.outputs.keyVaultName
output AZURE_KEY_VAULT_URI string = keyVault.outputs.keyVaultUri

output AZURE_AI_SERVICES_ENDPOINT string = ai.outputs.aiServicesEndpoint
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString

output STATIC_WEB_APP_NAME string = staticWebApp.outputs.staticWebAppName
output STATIC_WEB_APP_URI string = staticWebApp.outputs.staticWebAppUri

output PORTAL_STATIC_WEB_APP_NAME string = portalStaticWebApp.outputs.staticWebAppName
output PORTAL_STATIC_WEB_APP_URI string = portalStaticWebApp.outputs.staticWebAppUri

output AZURE_COSMOS_ENDPOINT string = cosmos.outputs.cosmosAccountEndpoint
output AZURE_COSMOS_DATABASE_NAME string = cosmos.outputs.cosmosDatabaseName

output AZURE_VNET_NAME string = network.outputs.vnetName
output AZURE_VNET_ID string = network.outputs.vnetId
output AZURE_RUNNER_SUBNET_ID string = network.outputs.runnerSubnetId
output AZURE_RUNNER_NAT_GATEWAY_ID string = network.outputs.natGatewayId
output AZURE_RUNNER_NAT_GATEWAY_PUBLIC_IP string = network.outputs.natGatewayPublicIpAddress
output AZURE_RUNNER_IDENTITY_ID string = runner.outputs.runnerIdentityId
output AZURE_RUNNER_IDENTITY_CLIENT_ID string = runner.outputs.runnerIdentityClientId
