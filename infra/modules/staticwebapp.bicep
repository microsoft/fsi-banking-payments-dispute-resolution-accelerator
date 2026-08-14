// ---------------------------------------------------------------------------
// staticwebapp.bicep — Azure Static Web App (Standard SKU — required for linked backends)
//
// Generic module reused for both React SPAs in this repo (src/web/ and
// src/customer-portal/). AZD matches each instance to its azure.yaml service
// via the azd-service-name tag (set via the azdServiceName param) and deploys
// the Vite dist/ output. Standard SKU is required to link a Function App
// backend (Free SKU does not support linkedBackends / BYO API).
//
// The linked-backend feature is exclusive per Function App: a single Function
// App can only be linked as the backend of ONE Static Web App at a time. Set
// linkBackend = false for any additional SWA instance that must reach the same
// Function App — that SWA should instead call the API via CORS + an absolute
// URL (see infra/main.bicep's portalStaticWebApp module for the pattern).
//
// IMPLICIT SIDE EFFECT: creating `linkedBackends` here also causes Azure to
// auto-enable App Service Authentication (EasyAuth v2) on the linked Function
// App, registering ONLY this SWA as an allowed `azureStaticWebApps` identity
// provider and requiring authentication for all callers. Any other caller
// (including a second SWA reaching the API via CORS) gets an unconditional
// 401. See the explicit `authsettingsV2` resource in functions.bicep, which
// overrides this back to anonymous/CORS-based access for this repo's auth
// model — do not remove that resource while `linkedBackends` remains here.
// ---------------------------------------------------------------------------

@description('Name of the Static Web App.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Resource id of the Function App to link as the API backend.')
param functionAppResourceId string

@description('Value for the azd-service-name tag, used by AZD to match this resource to a service in azure.yaml.')
param azdServiceName string = 'web'

@description('Whether to link the Function App as this SWA\'s backend. Set to false when the Function App is already linked to another SWA (linked backends are exclusive per Function App); the SWA will instead reach the API via CORS + an absolute URL.')
param linkBackend bool = true

// ---------------------------------------------------------------------------
// Static Web App
// ---------------------------------------------------------------------------
resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': azdServiceName })
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {}
}

// ---------------------------------------------------------------------------
// Linked backend — wires the Function App as the /api proxy for the SWA
// ---------------------------------------------------------------------------
resource linkedBackend 'Microsoft.Web/staticSites/linkedBackends@2023-12-01' = if (linkBackend) {
  parent: staticWebApp
  name: 'api'
  properties: {
    backendResourceId: functionAppResourceId
    region: location
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output staticWebAppName string = staticWebApp.name
output staticWebAppUri string = 'https://${staticWebApp.properties.defaultHostname}'
output staticWebAppId string = staticWebApp.id
