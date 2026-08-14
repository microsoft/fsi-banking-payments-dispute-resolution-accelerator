# 6. Deployment Guidance

## Prerequisites

Check you have all of these **before starting** (5 min total):

### 1. Azure Subscription
- Free tier: $200 credits (good for testing)
- Pay-as-you-go: Recommended for production
- **Check**: Log into https://portal.azure.com — see your resources

### 2. Command-Line Tools
```powershell
# Check if installed
az --version
azd version
git --version
node --version
python --version

# Install if missing (Windows with winget)
winget install Microsoft.AzureCLI
winget install Microsoft.AzureDeveloperCLI
winget install Git.Git
winget install OpenJS.NodeJS
winget install Python.Python.3.11
```

### 3. GitHub Account
- Fork or clone the repo: https://github.com/yortch/payment-disputes
- SSH key configured (or use HTTPS credentials)

### 4. Code Editor
- VS Code recommended (free)
- Bicep extension: `ms-azuretools.vscode-bicep`

---

## 5-Minute Setup

### Step 1: Clone & Navigate (1 min)
```bash
git clone https://github.com/yortch/payment-disputes.git
cd payment-disputes
code .  # Open in VS Code (optional)
```

### Step 2: Authenticate (1 min)
```bash
azd auth login
# Browser opens, sign in to your Azure subscription
# Returns to terminal when done
```

### Step 3: Provision & Deploy (3 min)
```bash
azd up
# Prompts:
#   - Environment name (e.g., "dev-disputes-1")
#   - Azure region (e.g., "eastus", "westus2")
#   - Confirm resource creation
# Then deploys all services (Functions, SWAs, Cosmos, Storage, Key Vault)
```

### Done! ✅
```bash
azd env list-outputs
# Shows:
#   - ANALYST_PORTAL_ENDPOINT: https://{env}-web.azurestaticapps.net
#   - CUSTOMER_PORTAL_ENDPOINT: https://{env}-portal.azurestaticapps.net
#   - API_ENDPOINT: https://{env}-api.azurewebsites.net/api
```

**Open these URLs in your browser to verify deployment.**

---

## Configuration Options

### 1. Azure Function Plan
**Current**: Consumption (default, per-execution pricing)
```bash
# In infra/parameters.json, change:
"functionPlanSku": "EP1"  # Premium plan (fixed monthly cost)
```
- **Consumption**: $0.20 per million executions + compute time
- **Premium**: ~$60/month but guarantees faster cold starts
- **Recommendation**: Consumption for MVP, upgrade if latency issues

### 2. Cosmos DB Throughput
**Current**: Autopilot (scales 0-40,000 RU/s)
```bicep
# In infra/modules/cosmos.bicep, change:
autoscaleSettings: {
  maxThroughput: 4000  # Reduce to save costs
}
```
- **Autopilot 0-4K RU/s**: $4-40/day (~$100-1200/month)
- **Manual 400 RU/s**: ~$20/month (fixed, no auto-scaling)
- **Recommendation**: Autopilot for production (flexible), Manual for testing

### 3. Enable Authentication
**Current**: Optional (dev mode, anon)
```powershell
# In Azure Portal → Function App Settings → Configuration
# Add: AUTH_ENABLED=true

# Then in .env.production
AZURE_ENTRA_TENANT_ID=your-tenant-id
AZURE_ENTRA_CLIENT_ID=your-app-id
```
- Requires Entra ID app registration (see Phase 2 plan)
- Adds ~15 min to setup

### 4. AI Scoring Configuration
**Current**: Hardcoded in `src/api/config.py`
```python
MIN_APPROVAL_SCORE = 0.65  # Only recommend if ≥65% confidence
CONFIDENCE_THRESHOLD = 0.50  # Hide low-confidence scores
```
- Tune these based on your risk tolerance
- Re-deploy with `azd deploy` after changes

### 5. Logging & Diagnostics
**Current**: Application Insights (auto-enabled)
```bash
# View logs
az monitor app-insights query \
  --app {app_insights_name} \
  --analytics-query "requests | head 100"
```
- Free tier: 5 GB/month data
- Logs retained 90 days

---

## Troubleshooting

### "azd: command not found"
```bash
# Install Azure Dev CLI
winget install Microsoft.AzureDeveloperCLI
# Or: brew install azure-dev (macOS)
# Or: https://aka.ms/azure-dev/install
```

### "Resource group already exists"
```bash
# Cleanup old environment
azd down --force
# Then re-run azd up with a new environment name
```

### "Function not found" or 404 on /api endpoints
```bash
# Rebuild Functions app
cd src/api
pip install -r requirements.txt
# Then re-deploy
cd ../..
azd deploy
```

### "Cosmos connection timeout"
```bash
# Check Key Vault has cosmos-connection-string
az keyvault secret list --vault-name {vault_name}

# If missing, get it from Azure Portal → Cosmos DB → Connection String
# Then set: az keyvault secret set --vault-name {vault_name} --name cosmos-connection-string --value "AccountEndpoint=..."
```

### "Portal shows 404 on case detail"
```bash
# Clear browser cache
Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)

# Refresh page
F5

# If still 404, check browser console for API errors (F12)
# If API returns 500, check Application Insights logs
```

### "Deploy takes >10 minutes"
```bash
# Check Azure Portal → Resource Group → Deployments
# Look for which resource is slow (usually Static Web App publish)
# This is normal for first deploy; subsequent deploys are faster (~2 min)
```

### "Out of quota" or "Operation did not complete within the time allowed"
```bash
# Check Azure subscription quotas
az vm list-usage --location eastus

# If vCPU quota exceeded:
# 1. Request quota increase in Azure Portal
# 2. Or use different region (less crowded)
# 3. Or reduce Function plan tier
```

---

## Deployment for Updates

### When you make code changes:

1. **Local testing** (optional):
   ```bash
   # Test Functions locally
   cd src/api
   func start
   # Open http://localhost:7071/api/disputes in browser
   
   # In another terminal, test portal
   cd src/web
   npm run dev
   # Open http://localhost:5173
   ```

2. **Commit & push**:
   ```bash
   git add src/...
   git commit -m "Fix: sorting now persists on page load"
   git push origin main
   ```

3. **Deploy**:
   ```bash
   azd deploy
   # Redeploys just the changed services
   # Usually 2-3 min (vs 5 min for azd up)
   ```

### Rollback if deployment breaks:
```bash
git revert <commit_hash>
git push origin main
azd deploy
# System rolls back to previous commit
```

---

## Monitoring Deployment Health

### After `azd up` or `azd deploy`, verify:

1. **Check endpoints are live**:
   ```bash
   curl https://{env}-api.azurewebsites.net/api/disputes
   # Should return 200 (even if empty array)
   ```

2. **Check Cosmos is healthy**:
   ```bash
   az cosmosdb check-name-availability --name {cosmos_name}
   # Should return "available": false (meaning it exists)
   ```

3. **Check Static Web Apps are deployed**:
   ```bash
   curl -I https://{env}-web.azurestaticapps.net
   # Should return 200, not 404
   ```

4. **Monitor costs**:
   ```bash
   az costmanagement query --timef-period "P7D" | jq '.properties.rows'
   # Shows last 7 days spending
   ```

---

## Upgrades

### Minor Updates (dependencies, patches)
```bash
cd src/api
pip install --upgrade -r requirements.txt
cd ../..
azd deploy
```

### Major Changes (new services, schema changes)
```bash
# Update Bicep templates in infra/
# Then re-provision
azd provision
azd deploy
```

### Rollback Cosmos schema (Phase 2)
```bash
# Cosmos is schema-flexible; just don't use new fields
# Old code can still read documents with new fields (they're ignored)
# No migration needed
```

---

## Cost Estimation

**Typical Monthly Bill** (light usage: 100 cases/month):
- Azure Functions: $5 (Consumption plan)
- Cosmos DB: $20 (Autopilot 0-4K RU/s)
- Blob Storage: $1 (<1 GB)
- Static Web Apps: Free (first 2 instances)
- Key Vault: $0.60 (operations)
- **Total: ~$27/month**

**At Scale** (10,000 cases/month):
- Functions: $50
- Cosmos: $200 (Autopilot scales to 40K RU/s)
- Blob: $10
- **Total: ~$260/month**

---

## Getting Help

| Issue | Where to Look |
|---|---|
| **azd/CLI errors** | `azd up --help`, Azure Dev CLI docs |
| **API errors** | Function App logs (Application Insights) |
| **Portal not loading** | Browser console (F12), SWA diagnostics (Azure Portal) |
| **Cosmos/Storage issues** | Azure Portal → Resource diagnostics |
| **General questions** | GitHub Issues or Discussions |

---

**Document Version**: 1.0 | **Last Updated**: 2026-07-22
