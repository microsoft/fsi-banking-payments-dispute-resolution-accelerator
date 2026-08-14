// ---------------------------------------------------------------------------
// private-dns.bicep — Private DNS zones for storage + Cosmos private endpoints
//
// Four zones, each linked to the VNet so Function App (VNet-integrated)
// name resolution for *.blob/queue/table.core.windows.net and
// *.documents.azure.com resolves to the private endpoint IPs instead of the
// public endpoints. See .squad/decisions.md "Decision Proposal: MANDATORY
// Private Networking".
// ---------------------------------------------------------------------------

@description('Resource ID of the VNet to link all private DNS zones to.')
param vnetId string

@description('Resource tags.')
param tags object

var zoneNames = [
  'privatelink.blob.core.windows.net'
  'privatelink.queue.core.windows.net'
  'privatelink.table.core.windows.net'
  'privatelink.documents.azure.com'
]

resource dnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [
  for zoneName in zoneNames: {
    name: zoneName
    location: 'global'
    tags: tags
  }
]

resource dnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [
  for (zoneName, i) in zoneNames: {
    parent: dnsZones[i]
    name: '${last(split(vnetId, '/'))}-link'
    location: 'global'
    tags: tags
    properties: {
      virtualNetwork: {
        id: vnetId
      }
      registrationEnabled: false
    }
  }
]

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output blobZoneId string = dnsZones[0].id
output queueZoneId string = dnsZones[1].id
output tableZoneId string = dnsZones[2].id
output documentsZoneId string = dnsZones[3].id
