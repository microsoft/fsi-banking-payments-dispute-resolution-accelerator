// ---------------------------------------------------------------------------
// keyvault.bicep — Key Vault with RBAC role assignment
// ---------------------------------------------------------------------------

@description('Name of the Key Vault.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('Principal ID to grant Key Vault Secrets User role.')
param principalId string

@description('Type of the principal: User or ServicePrincipal.')
@allowed([
  'User'
  'ServicePrincipal'
])
param principalType string = 'User'

// ---------------------------------------------------------------------------
// Key Vault
// ---------------------------------------------------------------------------
module keyVault 'br/public:avm/res/key-vault/vault:0.6.1' = {
  name: 'keyVault'
  params: {
    name: name
    location: location
    tags: tags
    sku: 'standard'
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    roleAssignments: [
      {
        principalId: principalId
        roleDefinitionIdOrName: 'Key Vault Secrets User'
        principalType: principalType
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output keyVaultName string = keyVault.outputs.name
output keyVaultUri string = keyVault.outputs.uri
output keyVaultResourceId string = keyVault.outputs.resourceId
