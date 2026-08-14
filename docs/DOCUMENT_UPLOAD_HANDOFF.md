# Document Upload Pipeline — Team Handoff

**Branch:** `DN_work` (commit `86b72c6`)  
**PR:** Ready to merge into `develop`  
**Author:** Danna  
**Date:** 2026-07-09  

---

## What's New

Evidence document upload with AI-powered analysis. Users upload dispute evidence (receipts, delivery proofs, terminal logs) and the system classifies the document, scores its evidentiary value, and recommends win probability adjustments.

### Files Changed/Added

| File | Type | Description |
|------|------|-------------|
| `src/api/services/document_service.py` | **New** | Storage backend (local + Azure Blob) + AI analysis engine |
| `src/api/dev_server.py` | Modified | Added `POST` and `GET` `/api/cases/{caseId}/documents` routes |
| `src/web/src/components/DocumentUploadPanel.tsx` | Modified | Wired UI to API, shows analysis results (badge, score, recommendation) |
| `src/api/uploads/.gitignore` | **New** | Keeps upload dir tracked without files |

---

## How to Run Locally

### Prerequisites
- Python 3.10+ (tested on 3.14)
- Node.js 18+ (tested on 24.x)
- No Azure connectivity required — runs in local/heuristic mode by default

### Steps

```bash
# 1. Pull the branch
git checkout DN_work
git pull origin DN_work

# 2. Start the Flask API (terminal 1)
cd src/api
pip install flask flask-cors
python dev_server.py
# → Running on http://localhost:7071

# 3. Start the Vite frontend (terminal 2)
cd src/web
npm install
npm run dev
# → Running on http://localhost:5176

# 4. Test it
#    - Open http://localhost:5176
#    - Navigate to any case detail page
#    - Upload a file via the Documents & Evidence panel
#    - See: document type, evidence score badge, win probability change
```

### Quick API Test (curl)

```bash
# Upload a document
curl -X POST http://localhost:7071/api/cases/{CASE_ID}/documents \
  -F "file=@receipt.pdf"

# List documents for a case
curl http://localhost:7071/api/cases/{CASE_ID}/documents
```

---

## How It Works

```
User drops file → Frontend POSTs FormData → Flask receives file
                                                    ↓
                                           Store (local disk or Azure Blob)
                                                    ↓
                                           Analyze (heuristic or Azure Doc Intelligence)
                                                    ↓
                                           Return: {documentType, evidenceScore, recommendation}
                                                    ↓
                                           Frontend shows badge + score delta
```

### Document Classification

| Filename Pattern | Classified As | Evidence Score |
|-----------------|---------------|----------------|
| `receipt`, `invoice`, `transaction` | transaction_receipt | 80% |
| `terminal`, `log`, `pos` | terminal_log | 90% |
| `delivery`, `tracking`, `shipping`, `signed` | delivery_proof | 85% |
| `refund`, `credit`, `reversal` | refund_evidence | 75% |
| `auth`, `signature`, `consent`, `agreement` | authorization_proof | 85% |
| Images | photo_evidence | 60% |
| Other | general_document | 50% |

*Note: Files < 1KB get a 50% score penalty (likely not useful evidence).*

---

## Azure Production Configuration

When deploying to the App Service (which is on the VNet with private endpoint access):

```env
# In App Service Configuration → Application Settings:
AZURE_STORAGE_MODE=azure
AZURE_STORAGE_ACCOUNT_NAME=<STORAGE_ACCOUNT_NAME>
AZURE_STORAGE_CONTAINER=documents
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://<AI_SERVICES_NAME>.cognitiveservices.azure.com/
```

### Additional Azure requirements:
1. **Storage container**: Create a `documents` container in `<STORAGE_ACCOUNT_NAME>`
2. **RBAC roles** (on the App Service managed identity):
   - `Storage Blob Data Contributor` on the storage account
   - `Cognitive Services User` on the AI Services resource
3. **Python packages** (add to `requirements.txt`):
   ```
   azure-storage-blob
   azure-identity
   azure-ai-documentintelligence
   ```

### Subscription/Tenant Info
- **Tenant:** ``
- **Subscription:** ``
- **Resource Group:** `` (West US 2)
- **AI Services:** `` (local auth disabled — uses managed identity)
- **Storage:** `` (public network disabled — private endpoint only)

---

## What to Change / Customize

| Want to... | Edit... |
|-----------|---------|
| Change accepted file types | `ACCEPTED_TYPES` in `DocumentUploadPanel.tsx` and add validation in Flask route |
| Change max file size | `MAX_SIZE_MB` in `DocumentUploadPanel.tsx` and `10 * 1024 * 1024` check in `dev_server.py` |
| Add new document classifications | `_analyze_heuristic()` in `document_service.py` — add keywords to the if/elif chain |
| Change score impact formula | `compute_updated_score()` in `document_service.py` — adjust the `* 0.10` multiplier |
| Change storage container name | `AZURE_STORAGE_CONTAINER` env var (default: `documents`) |
| Switch to Azure in dev | Set `AZURE_STORAGE_MODE=azure` + ensure VPN/private endpoint access |

---

## API Response Shape

### POST `/api/cases/{caseId}/documents`

```json
{
  "document": {
    "documentId": "uuid",
    "caseId": "uuid",
    "filename": "receipt_visa_4521.pdf",
    "contentType": "application/pdf",
    "sizeBytes": 245000,
    "uploadedAt": "2026-07-09T14:30:00Z",
    "blobUrl": "/uploads/caseId/docId_filename.pdf",
    "analysis": {
      "method": "heuristic",
      "documentType": "transaction_receipt",
      "evidenceScore": 0.8,
      "checklistItemsSatisfied": ["transaction_evidence"],
      "recommendation": "✅ HIGH VALUE — Transaction receipt validates the disputed charge.",
      "note": "Analyzed using filename heuristics. Connect Azure Document Intelligence for OCR-based analysis."
    }
  },
  "scoreUpdate": {
    "adjustedWinProbability": 0.53,
    "adjustment": 0.03,
    "reason": "Based on 1 document(s) with avg evidence quality",
    "documentsAnalyzed": 1
  },
  "message": "Document 'receipt_visa_4521.pdf' uploaded and analyzed."
}
```

---

## Questions? Ping Danna.
