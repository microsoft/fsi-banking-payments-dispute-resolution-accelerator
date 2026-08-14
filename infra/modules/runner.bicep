// ---------------------------------------------------------------------------
// runner.bicep — Identity + RBAC for the ephemeral self-hosted CD runner
// (Azure Container Instance) that deploys the Function App package.
//
// Context (see .squad/decisions.md self-hosted runner decision, 2026-07-09):
// Flex Consumption (FC1) `functionAppConfig.deployment.storage` always points
// at a specific blob container (`deploymentpackage`), and there is no real
// Kudu/SCM zip-deploy bypass for FC1 — deployment fundamentally requires
// reaching that blob container's data plane. Now that the storage account
// has `publicNetworkAccess: Disabled` (Phase 1), the CD pipeline needs a
// worker that can reach the private endpoint from inside the VNet. This
// module provisions ONLY the durable pieces (identity + RBAC + the `runner`
// subnet is provisioned in network.bicep) — the actual container instance is
// created and destroyed per-deploy by the CD workflow itself
// (`az container create` / `az container delete` in .github/workflows/cd.yml),
// since an ephemeral per-run container is cheaper and simpler than an
// always-on runner for a pipeline that only triggers on pushes to main.
//
// The runner authenticates to Azure primarily via OIDC (the same federated
// CI service principal used elsewhere in cd.yml — `azure/login@v2` works
// fine from inside the VNet as long as the runner subnet has outbound
// internet access to Azure AD/ARM, which it does by default — see
// network.bicep). This user-assigned managed identity is attached to the
// container group as a second, narrower-scoped credential specifically for
// the deployment-package blob container, available for direct blob writes
// if a future deploy path needs it (e.g. if `az functionapp deploy`'s
// SCM/control-plane route stops being sufficient) — mirroring the
// `deployerBlobAssignment` pattern in functions.bicep, but scoped to the
// runner's own identity instead of the CI OIDC service principal.
// ---------------------------------------------------------------------------

@description('Name of the user-assigned managed identity for the self-hosted runner.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Resource ID of the Storage Account backing the Flex Consumption deployment package.')
param storageAccountId string

// Built-in role definition ID: Storage Blob Data Contributor
var storageBlobDataContributorId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

// ---------------------------------------------------------------------------
// User-assigned managed identity for the runner container group
// ---------------------------------------------------------------------------
resource runnerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------
// Existing Storage Account (for role assignment scope only)
// ---------------------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: last(split(storageAccountId, '/'))
}

// Blob Data Contributor at the account scope (container-level scoping for
// Storage RBAC role assignments requires a separate `roleAssignments`
// resource nested under the container, which needs the container as a
// parent; account-level keeps this consistent with the existing
// `deployerBlobAssignment` pattern in functions.bicep and is sufficient
// since the runner's only job is writing the deployment package blob).
resource runnerBlobAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, runnerIdentity.id, storageBlobDataContributorId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorId)
    principalId: runnerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output runnerIdentityId string = runnerIdentity.id
output runnerIdentityClientId string = runnerIdentity.properties.clientId
output runnerIdentityPrincipalId string = runnerIdentity.properties.principalId
