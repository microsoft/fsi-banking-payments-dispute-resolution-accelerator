# Fabric Mirroring Setup — Cosmos DB → OneLake

## Overview

Mirrors the 3 Cosmos DB containers (disputes, evidence, timeline) into Fabric OneLake
as Delta tables for analytics. Uses **Service Principal authentication** because an
Azure Policy (`CosmosDB_LocalAuth_Modify`) enforces `disableLocalAuth: true` on this
subscription, blocking key-based connections.

## Service Principal Details

| Property | Value |
|----------|-------|
| App Name | `fabric-mirror-cosmos-disputes` |
| App (Client) ID | `` |
| Tenant ID | `` |
| SP Object ID | `` |
| Secret Expiry | ~July 2027 (1 year) |

### Roles Assigned

| Role | Scope | Purpose |
|------|-------|---------|
| Cosmos DB Built-in Data Reader | Account (data plane) | Read change feed |
| Cosmos DB Account Reader Role | Account (control plane) | Discover account metadata |

## Cosmos DB Connection

| Property | Value |
|----------|-------|
| Endpoint | `` |
| Database | `disputes-db` |
| Containers | `disputes`, `evidence`, `timeline` |

## Fabric Portal Steps

### 1. Create Mirrored Database

1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com)
2. Open your target workspace (or create one)
3. Click **+ New item** → **Mirrored Azure Cosmos DB**
4. Connection settings:
   - **Authentication kind**: Service Principal
   - **Cosmos DB Endpoint**: ``
   - **Tenant ID**: ``
   - **Service Principal Client ID**: `<YOUR-SERVICE-PRINCIPAL-CLIENT-ID>`
   - **Service Principal Secret**: *(stored in Key Vault — retrieve with command below)*
5. Click **Connect**

### 2. Select Containers to Mirror

Select all 3 containers:
- [x] `disputes`
- [x] `evidence`
- [x] `timeline`

Click **Mirror database** to start initial sync.

### 3. Verify Mirroring

- Initial sync will take a few minutes for ~3,950 documents
- Check the mirroring status page for "Running" state
- Each container becomes a Delta table in the Lakehouse SQL analytics endpoint

## Retrieve Client Secret

```powershell
# From Key Vault (if stored):
az keyvault secret show --vault-name "kv-weuanic6nxgss" --name "fabric-mirror-secret" --query value -o tsv

# Or re-generate (invalidates previous):
az ad app credential reset --id "<YOUR-SERVICE-PRINCIPAL-CLIENT-ID>" --display-name "fabric-mirror-secret" --years 1
```

## Store Secret in Key Vault (Recommended)

```powershell
az keyvault secret set --vault-name "kv-weuanic6nxgss" --name "fabric-mirror-secret" --value "<SECRET_VALUE>"
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Unauthorized" on connect | Verify SP has `Cosmos DB Built-in Data Reader` on account |
| "Forbidden" / 403 | Check control-plane `Cosmos DB Account Reader Role` assignment |
| No data flowing | Ensure containers have change feed enabled (default: on) |
| Secret expired | Regenerate: `az ad app credential reset --id <YOUR-SERVICE-PRINCIPAL-CLIENT-ID>` |
