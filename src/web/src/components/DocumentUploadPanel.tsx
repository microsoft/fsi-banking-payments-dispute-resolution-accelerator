import { Badge, Spinner, Text, Title2, tokens } from '@fluentui/react-components';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNotifications } from './NotificationProvider';

interface AnalysisResult {
  method: string;
  documentType: string;
  evidenceScore: number;
  recommendation: string;
  checklistItemsSatisfied?: string[];
  note?: string;
}

interface ScoreUpdate {
  adjustedWinProbability: number;
  adjustment: number;
  reason: string;
  documentsAnalyzed: number;
}

interface UploadedDoc {
  documentId: string;
  filename: string;
  sizeBytes: number;
  contentType: string;
  uploadedAt: string;
  analysis: AnalysisResult;
  scoreUpdate?: ScoreUpdate;
}

interface DocumentUploadPanelProps {
  caseId: string;
}

const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE_MB = 10;
const API_BASE = '/api';

export function DocumentUploadPanel({ caseId }: DocumentUploadPanelProps) {
  const [uploads, setUploads] = useState<UploadedDoc[]>([]);
  const [loadingExisting, setLoadingExisting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { notifySuccess, notifyWarning, notifyError } = useNotifications();

  const uploadFile = useCallback(async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/cases/${caseId}/documents`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(body.error || `Upload failed (${res.status})`);
    }

    return res.json();
  }, [caseId]);

  useEffect(() => {
    let active = true;
    const loadExisting = async () => {
      setLoadingExisting(true);
      try {
        const res = await fetch(`${API_BASE}/cases/${caseId}/documents`);
        if (!res.ok) return;
        const body = await res.json() as { documents?: UploadedDoc[] };
        if (!active) return;
        setUploads(body.documents ?? []);
      } catch {
        // Keep the panel usable even if initial list load fails.
      } finally {
        if (active) setLoadingExisting(false);
      }
    };
    void loadExisting();
    return () => {
      active = false;
    };
  }, [caseId]);

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files) return;
    setError(null);

    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError(`"${file.name}" is not a supported file type. Use PDF, JPG, PNG, or WebP.`);
        continue;
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        setError(`"${file.name}" exceeds ${MAX_SIZE_MB}MB limit.`);
        continue;
      }
      validFiles.push(file);
    }

    if (validFiles.length === 0) return;

    setUploading(true);
    try {
      for (const file of validFiles) {
        const result = await uploadFile(file);
        const doc: UploadedDoc = {
          ...result.document,
          scoreUpdate: result.scoreUpdate,
        };
        setUploads((prev) => {
          const index = prev.findIndex((d) => d.documentId === doc.documentId);
          if (index >= 0) {
            const copy = [...prev];
            copy[index] = doc;
            return copy;
          }
          return [...prev, doc];
        });

        const score = doc.analysis.evidenceScore;
        if (score >= 0.8) {
          notifySuccess('High-value evidence uploaded', `"${file.name}" — ${Math.round(score * 100)}% evidence score`);
        } else if (score >= 0.6) {
          notifyWarning('Document uploaded', `"${file.name}" — moderate evidence value (${Math.round(score * 100)}%)`);
        } else {
          notifyWarning('Low-value document', `"${file.name}" scored ${Math.round(score * 100)}%. Consider uploading stronger evidence.`);
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setError(msg);
      notifyError('Upload failed', msg);
    } finally {
      setUploading(false);
    }
  }, [uploadFile]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const scoreBadgeColor = (score: number) => {
    if (score >= 0.8) return 'success' as const;
    if (score >= 0.6) return 'warning' as const;
    return 'informative' as const;
  };

  return (
    <div>
      <Title2 style={{ marginBottom: '12px' }}>Documents & Evidence</Title2>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? tokens.colorBrandStroke1 : tokens.colorNeutralStroke2}`,
          borderRadius: '8px',
          padding: '32px',
          textAlign: 'center',
          cursor: uploading ? 'wait' : 'pointer',
          background: dragOver ? tokens.colorBrandBackground2 : 'transparent',
          transition: 'all 150ms ease',
          marginBottom: '12px',
          opacity: uploading ? 0.6 : 1,
        }}
      >
        {uploading ? (
          <Spinner size="small" label="Uploading & analyzing..." />
        ) : (
          <>
            <Text size={300} style={{ display: 'block', marginBottom: '8px' }}>
              📎 Drag & drop files here, or click to browse
            </Text>
            <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
              PDF, JPG, PNG, WebP — max {MAX_SIZE_MB}MB per file
            </Text>
          </>
        )}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES.join(',')}
          aria-label="Upload evidence documents"
          onChange={(e) => { handleFiles(e.target.files); e.target.value = ''; }}
          style={{ display: 'none' }}
        />
      </div>

      {error && (
        <Text size={200} style={{ color: tokens.colorPaletteRedForeground1, display: 'block', marginBottom: '8px' }}>
          ⚠️ {error}
        </Text>
      )}

      {/* Uploaded files with analysis results */}
      {loadingExisting && uploads.length === 0 && (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '8px' }}>
          Loading existing documents...
        </Text>
      )}

      {uploads.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {uploads.map((doc) => (
            <div
              key={doc.documentId}
              style={{
                padding: '12px',
                borderRadius: '8px',
                border: `1px solid ${tokens.colorNeutralStroke2}`,
                background: tokens.colorNeutralBackground1,
              }}
            >
              {/* File info row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <div>
                  <Text size={300} weight="semibold" style={{ display: 'block' }}>{doc.filename}</Text>
                  <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                    {(doc.sizeBytes / 1024).toFixed(0)} KB · {doc.contentType.split('/')[1]?.toUpperCase()}
                  </Text>
                </div>
                <Badge color={scoreBadgeColor(doc.analysis.evidenceScore)} appearance="filled">
                  {Math.round(doc.analysis.evidenceScore * 100)}% evidence value
                </Badge>
              </div>

              {/* Analysis details */}
              <div style={{ padding: '8px', borderRadius: '6px', background: tokens.colorNeutralBackground3, fontSize: '12px' }}>
                <Text size={200} style={{ display: 'block', marginBottom: '4px' }}>
                  <strong>Type:</strong> {doc.analysis.documentType.replace(/_/g, ' ')}
                </Text>
                <Text size={200} style={{ display: 'block', marginBottom: '4px' }}>
                  {doc.analysis.recommendation}
                </Text>
                {doc.analysis.checklistItemsSatisfied && doc.analysis.checklistItemsSatisfied.length > 0 && (
                  <Text size={200} style={{ display: 'block', color: tokens.colorPaletteGreenForeground1 }}>
                    ✓ Checklist items satisfied: {doc.analysis.checklistItemsSatisfied.join(', ').replace(/_/g, ' ')}
                  </Text>
                )}
                {doc.scoreUpdate && doc.scoreUpdate.adjustment !== 0 && (
                  <Text size={200} style={{
                    display: 'block',
                    marginTop: '4px',
                    color: doc.scoreUpdate.adjustment > 0 ? tokens.colorPaletteGreenForeground1 : tokens.colorPaletteRedForeground1,
                  }}>
                    Win probability: {doc.scoreUpdate.adjustment > 0 ? '↑' : '↓'} {Math.abs(doc.scoreUpdate.adjustment * 100).toFixed(1)}%
                    → {Math.round(doc.scoreUpdate.adjustedWinProbability * 100)}%
                  </Text>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
