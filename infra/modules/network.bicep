// ---------------------------------------------------------------------------
// network.bicep — VNet + subnets for private networking (Phase 1)
//
// Per .squad/decisions.md "Decision Proposal: MANDATORY Private Networking":
// - func-integration: delegated subnet for Function App (Flex Consumption)
//   outbound VNet integration.
// - private-endpoints: subnet hosting NICs for storage blob/queue/table and
//   Cosmos SQL private endpoints.
//
// ⚠️ Delegation verified at implementation time (2026-07-09): Flex Consumption
// (FC1) VNet integration uses `virtualNetworkSubnetId` directly on
// Microsoft.Web/sites (same property as classic App Service VNet
// integration), but the delegated subnet's serviceName must be
// `Microsoft.App/environments` — NOT `Microsoft.Web/serverFarms`. Using the
// classic App Service delegation causes deployment failures for FC1. See
// Microsoft Learn: azure-functions/functions-networking-options ("flex" tab).
//
// `runner` subnet (added 2026-07-09, self-hosted CD runner): dedicated,
// non-overlapping subnet delegated to Microsoft.ContainerInstance/containerGroups
// so an ephemeral Azure Container Instance can join this VNet to write the
// Flex Consumption deployment package directly to the private
// `deploymentpackage` blob container (see .squad/decisions.md self-hosted
// runner decision, 2026-07-09). Deliberately NOT the `private-endpoints`
// subnet — Azure disallows most delegations from cleanly coexisting with a
// subnet already used for private-endpoint network policies.
//
// ⚠️ CORRECTION (2026-07-09, CD run 29033981840): the original assumption
// that this subnet gets usable "default outbound internet access" was
// WRONG for VNet-injected Container Instances. A container group with only
// a private IP (`ipAddress.type: Private`, no public IP) and no explicit
// egress path (NAT Gateway, Azure Firewall + UDR, or a Standard Load
// Balancer with outbound rules) generally cannot reach the internet at
// all — it just hangs in `Creating`/`Waiting to run` indefinitely with no
// clear error, since ACI's provisioning state doesn't surface egress
// failures. This is why the runner container never registered with GitHub
// and the image pull from Docker Hub never completed. Fix: a Standard NAT
// Gateway (+ its own Standard SKU public IP) is now associated with the
// `runner` subnet ONLY, giving the ephemeral ACI a deterministic outbound
// path for Docker Hub pulls and the GitHub API while keeping its
// inbound-private / no-public-IP posture intact. Deliberately NOT attached
// to `func-integration` or `private-endpoints` — those subnets don't need
// outbound internet and should stay as tightly scoped as before.
// ---------------------------------------------------------------------------

@description('Name of the Virtual Network.')
param name string

@description('Azure region for all resources.')
param location string

@description('Resource tags.')
param tags object

@description('VNet address space.')
param addressPrefix string = '10.100.0.0/16'

@description('Address prefix for the Function App VNet-integration subnet.')
param funcIntegrationSubnetPrefix string = '10.100.1.0/24'

@description('Address prefix for the private-endpoints subnet.')
param privateEndpointsSubnetPrefix string = '10.100.2.0/24'

@description('Address prefix for the self-hosted CD runner subnet (ACI).')
param runnerSubnetPrefix string = '10.100.3.0/24'

@description('Name of the NAT Gateway providing outbound internet egress for the runner subnet.')
param natGatewayName string

@description('Name of the Standard SKU public IP used by the NAT Gateway.')
param natGatewayPublicIpName string

// ---------------------------------------------------------------------------
// NAT Gateway (runner subnet outbound egress only)
//
// Standard SKU public IP is required by NAT Gateway. Both resources are
// always-on (NAT Gateway has no "stopped" state) — the ephemeral ACI is the
// only thing that comes and goes, not its egress path. See PR description /
// .squad/decisions.md for the ~$32-40/month cost estimate and the rationale
// for not attempting an ephemeral NAT Gateway.
// ---------------------------------------------------------------------------
resource natGatewayPublicIp 'Microsoft.Network/publicIPAddresses@2023-11-01' = {
  name: natGatewayPublicIpName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource natGateway 'Microsoft.Network/natGateways@2023-11-01' = {
  name: natGatewayName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIpAddresses: [
      {
        id: natGatewayPublicIp.id
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Virtual Network
// ---------------------------------------------------------------------------
resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        addressPrefix
      ]
    }
    subnets: [
      {
        name: 'func-integration'
        properties: {
          addressPrefix: funcIntegrationSubnetPrefix
          delegations: [
            {
              name: 'flexConsumptionDelegation'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
          privateEndpointNetworkPolicies: 'Enabled'
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: privateEndpointsSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'runner'
        properties: {
          addressPrefix: runnerSubnetPrefix
          delegations: [
            {
              name: 'aciDelegation'
              properties: {
                serviceName: 'Microsoft.ContainerInstance/containerGroups'
              }
            }
          ]
          privateEndpointNetworkPolicies: 'Enabled'
          natGateway: {
            id: natGateway.id
          }
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output vnetId string = vnet.id
output vnetName string = vnet.name
output funcIntegrationSubnetId string = '${vnet.id}/subnets/func-integration'
output privateEndpointsSubnetId string = '${vnet.id}/subnets/private-endpoints'
output runnerSubnetId string = '${vnet.id}/subnets/runner'
output natGatewayId string = natGateway.id
output natGatewayPublicIpAddress string = natGatewayPublicIp.properties.ipAddress
