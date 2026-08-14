# 8. Learning Log

## What Worked ✅

### 1. Shared Cosmos DB for Both Portals
**Why it worked**: No sync complexity. Customer uploads evidence → both portals see it instantly on next load.  
**Lesson**: Eliminate data silos. One source of truth beats eventual consistency.

### 2. Timeline Events as Audit Log
**Why it worked**: Every decision is a lightweight document. Easy to query, easy to display, compliance-ready.  
**Pattern**: Instead of separate audit table, make events first-class documents.
```json
{
  "event_type": "customer_cancellation",
  "actor": "customer",
  "timestamp": "2026-07-22T10:30Z",
  "detail": "Merchant refunded charge"
}
```
**Lesson**: Structure events around business actions, not technical concerns.

### 3. Client-Side Sorting (CaseTable)
**Why it worked**: No backend queries needed. Fast, no latency, UX matches expectations.  
**Code Pattern**: 
```typescript
const [sortKey, setSortKey] = useState<string>('deadline');
const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

function sortCases(cases, key, dir) {
  return [...cases].sort((a, b) => {
    const comp = a[key] < b[key] ? -1 : 1;
    return dir === 'asc' ? comp : -comp;
  });
}
```
**Lesson**: Keep sorting logic on frontend for responsive UX.

### 4. Azure Dev CLI (azd) for 5-Minute Setup
**Why it worked**: One `azd up` command handles all provisioning + deployment. Non-engineers can deploy.  
**vs Alternative**: Manual portal clicks = error-prone, hard to reproduce.  
**Lesson**: Invest in automation early. It pays for itself in team efficiency.

### 5. Managed Identity (No Secrets in Code)
**Why it worked**: Functions authenticate to Cosmos/Blob using Entra ID. Zero risk of leaked credentials.  
**Pattern**: 
```python
from azure.identity import DefaultAzureCredential
credential = DefaultAzureCredential()  # Automatic (FI or local MSI)
```
**Lesson**: Use platform-native identity. Scales securely to 100s of services.

### 6. Foundry Agents for AI (Inference Only)
**Why it worked**: No GPU provisioning, no model training. Call endpoint, get score back.  
**Cost**: ~$0.02 per inference vs $1000s for infra.  
**Lesson**: Managed services for AI beats DIY. You're not an ML infra company.

### 7. Dispute Status Tracking with 'closed' State
**Why it worked**: When customer cancels, status='closed' automatically routes case to Closed tab.  
**No**: Separate "cancelled" field.  
**Yes**: Treat cancellation as a status.  
**Lesson**: Status = single source of truth for routing/filtering.

### 8. Bicep IaC for Reproducible Deployments
**Why it worked**: Version-controlled, readable, scales to 10s of environments (dev/staging/prod).  
**vs Alternative**: Terraform (more verbose), Manual portal (error-prone).  
**Lesson**: Azure-native tooling when you're all-in on Azure.

### 9. GitHub Actions CI/CD Pipeline
**Why it worked**: Build → Test → Deploy automatically on main branch push. One less human step = fewer mistakes.  
**Lesson**: Automate repetitive tasks. Humans should review, not execute.

### 10. Fluent UI Components for Consistency
**Why it worked**: Pre-built, accessible, matches Microsoft Office look-and-feel. Team doesn't need a designer.  
**vs Custom CSS**: Saves 20 hours of styling.  
**Lesson**: Use UI libraries. Focus on business logic, not component design.

---

## What Didn't Work ❌

### 1. WebSockets for Real-Time Updates (Deferred to Phase 2)
**Why it failed**: Over-engineered for MVP. Real-time expectation created scope creep.  
**Lesson**: Refresh-on-load is MVP-acceptable. Sell "speed of turnaround" not "live updates."

### 2. Auto-Triggering AI on Evidence Upload (Deferred to Phase 2)
**Why it failed**: Opens Pandora's box:
- Analyst thinks they clicked once, gets charged twice
- Case re-analyzed without analyst permission
- Score changes without visibility
**Lesson**: MVP = explicit (button-click = action). Phase 2 = implicit (auto-trigger with confirmation).

### 3. Complex Merchant Portal (Deferred to Phase 3)
**Why it failed**: Scope creep. Merchants rarely use self-service; they call their bank.  
**Lesson**: Ship with two portals (customer + analyst). Merchant portal is Phase 3 nice-to-have.

### 4. SQL Database (Rejected in Favor of Cosmos)
**Why it failed**: For disputes, schema is flexible:
- Dispute can have 2 evidence items or 20
- Metadata varies by merchant type
- Timeline events are polymorphic
**Lesson**: NoSQL for schema-flexible domains (disputes, events). SQL for rigid (users, transactions).

### 5. Service-to-Service Authentication (Too Complex for MVP)
**Why it failed**: Portal → API → Cosmos is one team. Mutual auth added 5 hours of work for 0 actual security benefit.  
**Current**: VNet isolation + Managed Identity sufficient.  
**Lesson**: Simple beats secure-but-complex. Revisit when multi-team.

---

## Risks & Mitigations 🚨

| Risk | Impact | Mitigation |
|---|---|---|
| **Cosmos cost explodes at scale** | Budget overrun | Monitor RU consumption daily; migrate to fixed plan if >10K avg RU/s |
| **AI agent latency (Foundry timeout)** | Cases stuck "pending score" | Cache scores, fall back to "pending analyst review" |
| **Customer loses internet mid-upload** | Orphaned artifacts in Blob | Implement resumable upload (Phase 2) |
| **Cancelled case re-analyzed** | Wasted AI cost | Add 'closed' check in /score endpoint (simple fix) |
| **Analyst makes typo in decision** | Dispute outcome wrong | Implement undo for analysts (Phase 2) |
| **Blob storage blob versioning fills up** | Cost spike | 90-day lifecycle policy (auto-cleanup old versions) |
| **No backup for Cosmos data** | Catastrophic data loss | Enable point-in-time restore + manual backup schedule |
| **Foundry API key exposed** | Unauthorized AI calls | Rotate key monthly, add rate limiting per API key |
| **Portal SQL injection in search** | Data leak | Use Cosmos parameterized queries (already done) |

### Risk Acceptance
- **Single-region**: Accepted. Regional outage <1% annual probability. Recovery: 30 min manual failover.
- **No customer auth**: Accepted (MVP). Phase 2: Entra ID SSO fixes this.
- **AI sometimes wrong**: Accepted. Analysts override. Quarterly audits improve model.

---

## Improvements for Next Teams 🚀

### Phase 2 (3-4 weeks)
1. **Auto-reprocess chain**: Trigger AI re-scoring when evidence improves
2. **Entra ID auth**: Mandatory for both portals + RBAC
3. **Appeal workflow**: Customers can request analyst re-review
4. **Real-time updates**: WebSocket notifications on case status changes

### Phase 3 (2-3 months)
1. **Merchant portal**: Let merchants view disputes filed against them
2. **Analytics dashboard**: Approval rate trends, AI accuracy, analyst performance
3. **Multi-region failover**: Cosmos replicas in backup region
4. **Advanced AI**: Fine-tuned models on customer data

### Patterns for Future Teams
- ✅ Use timeline events for audit trails
- ✅ Status field (not separate "cancelled" flag) for routing
- ✅ Managed Identity for auth (not secrets)
- ✅ Client-side sorting for fast UX
- ✅ Event-driven (though Phase 1 uses polling)
- ✅ Bicep + azd for Azure projects
- ✅ Foundry for AI inference (not training)

### Anti-Patterns to Avoid
- ❌ Multiple databases (causes sync issues)
- ❌ Service-to-service auth for single-team projects
- ❌ Complex real-time updates before MVP validation
- ❌ Storing credentials in code
- ❌ Manual deployments

---

## Code Patterns Worth Stealing

### Pattern 1: Timeline Events
```python
def write_event(db, dispute_id, event_type, actor, detail):
    event = {
        "id": f"event-{uuid4()}",
        "dispute_id": dispute_id,
        "event_type": event_type,  # "intake", "customer_response", "cancellation"
        "actor": actor,              # "customer" or "analyst"
        "timestamp": now_iso(),
        "detail": detail
    }
    db.create_item(container="timeline_events", item=event)
    return event["id"]
```

### Pattern 2: Status-Based Routing
```typescript
const CLOSED_STATUSES = new Set([
  'approved', 'denied', 'expired', 'escalated', 'closed'
]);

function getTabForStatus(status) {
  if (CLOSED_STATUSES.has(status)) return 'Closed';
  if (status === 'pending_review') return 'Ready for Review';
  return 'Open';
}
```

### Pattern 3: Client-Side Sorting
```typescript
function sortCases(cases, key, dir) {
  return [...cases].sort((a, b) => {
    const val_a = a[key];
    const val_b = b[key];
    const comp = val_a < val_b ? -1 : val_a > val_b ? 1 : 0;
    return dir === 'asc' ? comp : -comp;
  });
}
```

### Pattern 4: Managed Identity for Cosmos
```python
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

url = os.environ['AZURE_COSMOS_ENDPOINT']
credential = DefaultAzureCredential()
client = CosmosClient(url=url, credential=credential)
db = client.get_database_client(os.environ['COSMOS_DB_NAME'])
```

---

## Key Decisions (Rationale)

| Decision | Why | Cost of Being Wrong |
|---|---|---|
| **Cosmos over SQL** | Schema flexibility for dispute metadata | Would need to redesign schema (2-3 days) |
| **Functions over App Service** | Serverless, simple, auto-scaling | Would need to manage pool of VMs (ongoing) |
| **Static Web Apps (SWA) over App Service** | Free tier, built-in auth, CDN | Would lose fast edge caching (~300ms savings) |
| **Client-side sorting** | Fast, no backend latency | Would add 2-3s round-trip for each sort |
| **azd + Bicep over Terraform** | Azure-native, simpler for 1-cloud | Would need to learn Terraform (learning curve) |
| **Timeline events as docs** | Single query for full history | Would need JOINs across 3 tables (complexity) |

---

## Interview Questions for New Team Members

When handing off to the Phase 2 team, ask these to verify understanding:

1. **"Why is the Cosmos DB shared between both portals?"**
   - ✅ Answer: To ensure both see same data immediately; no sync delays.

2. **"How does a cancelled case end up in the Closed tab?"**
   - ✅ Answer: When status='closed', the filterByTab logic routes to CLOSED_STATUSES.

3. **"What happens if an analyst clicks 'Score Case' and it fails?"**
   - ✅ Answer: API returns 500; analyst sees error; can retry or skip. Case stays as-is.

4. **"How do we prevent the same customer from submitting duplicate disputes?"**
   - ✅ Answer: Phase 2 feature. MVP: manual analyst review.

5. **"Why use Managed Identity instead of connection strings?"**
   - ✅ Answer: No secrets in code; Entra ID handles rotation; scales to many services.

---

## Metrics That Matter

**Track these to know if Phase 2 is working**:

| Metric | Current (MVP) | Target (Phase 2) | Why |
|---|---|---|---|
| **Case resolution time** | 3-5 days | 1-2 days | AI + auto-reprocess speeds decisions |
| **Analyst approval rate** | 65% | 75% | Better evidence + rebuttal drafting |
| **AI accuracy** | 80% (baseline) | 90%+ | More training data + fine-tuning |
| **Analyst hours per case** | 45 min | 20 min | Auto-draft rebuttal + gap detection |
| **Customer satisfaction** | ? | >85% NPS | Transparency + speed wins hearts |

---

**Document Version**: 1.0 | **Last Updated**: 2026-07-22

**Maintained by**: the project team  
**Feedback**: Open GitHub issue if you find patterns that don't work or new patterns to steal.
