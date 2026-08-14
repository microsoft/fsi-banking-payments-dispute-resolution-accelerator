// ---------------------------------------------------------------------------
// monitoring.bicep — Log Analytics Workspace + Application Insights
// ---------------------------------------------------------------------------

@description('Name of the Application Insights component.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Name of the Log Analytics Workspace.')
param logAnalyticsName string

// ---------------------------------------------------------------------------
// Log Analytics Workspace
// ---------------------------------------------------------------------------
module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.3.4' = {
  name: 'logAnalytics'
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
    skuName: 'PerGB2018'
    dataRetention: 30
  }
}

// ---------------------------------------------------------------------------
// Application Insights
// ---------------------------------------------------------------------------
module appInsights 'br/public:avm/res/insights/component:0.3.1' = {
  name: 'appInsights'
  params: {
    name: name
    location: location
    tags: tags
    workspaceResourceId: logAnalytics.outputs.resourceId
    kind: 'web'
    applicationType: 'web'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output logAnalyticsResourceId string = logAnalytics.outputs.resourceId
output appInsightsInstrumentationKey string = appInsights.outputs.instrumentationKey
output appInsightsConnectionString string = appInsights.outputs.connectionString
