import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Text,
  Title2,
  Body1,
  tokens,
  Button,
  Badge,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { AppShell } from '../components/AppShell.tsx';
import { useWizard } from '../App.tsx';
import type { DocumentMeta } from '../types/dispute.ts';

const MAX_FILE_SIZE_MB = 10;
const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'text/plain'];
const ACCEPTED_EXTENSIONS = '.pdf,.jpg,.jpeg,.png,.webp,.txt';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentUploadPage() {
  const navigate = useNavigate();
  const { transaction, formData, documents, rawFiles, setDocuments, setRawFiles } = useWizard();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!transaction || !formData) navigate('/');
  }, [transaction, formData, navigate]);

  if (!transaction || !formData) return null;

  function addFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const toAdd: DocumentMeta[] = [];
    const filesToAdd: File[] = [];
    const errs: string[] = [];
    for (const file of Array.from(files)) {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        errs.push(`${file.name}: unsupported type (${file.type || 'unknown'})`);
        continue;
      }
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        errs.push(`${file.name}: exceeds ${MAX_FILE_SIZE_MB} MB limit`);
        continue;
      }
      if (documents.some(d => d.name === file.name)) {
        errs.push(`${file.name}: already added`);
        continue;
      }
      toAdd.push({ name: file.name, size: file.size, type: file.type });
      filesToAdd.push(file);
    }
    if (errs.length) setValidationError(errs.join(' · '));
    else setValidationError(null);
    if (toAdd.length) {
      setDocuments([...documents, ...toAdd]);
      setRawFiles([...rawFiles, ...filesToAdd]);
    }
  }

  function removeDoc(name: string) {
    setDocuments(documents.filter(d => d.name !== name));
    setRawFiles(rawFiles.filter(f => f.name !== name));
  }

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }, [documents]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AppShell step={3}>
      <Button appearance="subtle" onClick={() => navigate('/dispute')} style={{ marginBottom: tokens.spacingVerticalM }}>
        ← Back to dispute details
      </Button>

      <Title2 style={{ marginBottom: tokens.spacingVerticalXS }}>Upload supporting documents</Title2>
      <Body1 style={{ color: tokens.colorNeutralForeground2, marginBottom: tokens.spacingVerticalL, display: 'block' }}>
        Attach any documents that support your dispute — receipts, screenshots, correspondence, or delivery confirmations.
        This step is <strong>optional</strong> but may speed up your case.
      </Body1>

      {/* Drop zone */}
      <div
        onDragEnter={() => setDragOver(true)}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? tokens.colorBrandStroke1 : tokens.colorNeutralStroke1}`,
          borderRadius: tokens.borderRadiusMedium,
          backgroundColor: dragOver ? tokens.colorBrandBackground2 : tokens.colorNeutralBackground1,
          padding: `${tokens.spacingVerticalXXL} ${tokens.spacingHorizontalXXL}`,
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'background-color 0.15s, border-color 0.15s',
          marginBottom: tokens.spacingVerticalL,
        }}
      >
        <div style={{ fontSize: '36px', marginBottom: tokens.spacingVerticalS }}>📎</div>
        <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: tokens.spacingVerticalXS }}>
          Drag &amp; drop files here, or click to browse
        </Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          PDF, JPEG, PNG, WEBP, TXT — up to {MAX_FILE_SIZE_MB} MB each
        </Text>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        style={{ display: 'none' }}
        onChange={e => addFiles(e.target.files)}
      />

      {validationError && (
        <MessageBar intent="warning" style={{ marginBottom: tokens.spacingVerticalM }}>
          <MessageBarBody>{validationError}</MessageBarBody>
        </MessageBar>
      )}

      {/* File list */}
      {documents.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS, marginBottom: tokens.spacingVerticalL }}>
          <Text weight="semibold" size={300} style={{ color: tokens.colorNeutralForeground2 }}>
            {documents.length} file{documents.length !== 1 ? 's' : ''} selected
          </Text>
          {documents.map(doc => (
            <div
              key={doc.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: tokens.spacingHorizontalM,
                backgroundColor: tokens.colorNeutralBackground1,
                border: `1px solid ${tokens.colorNeutralStroke2}`,
                borderRadius: tokens.borderRadiusMedium,
                padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM}`,
              }}
            >
              <span style={{ fontSize: '20px' }}>
                {doc.type === 'application/pdf' ? '📄' : doc.type.startsWith('image/') ? '🖼️' : '📝'}
              </span>
              <div style={{ flex: 1 }}>
                <Text size={300} weight="semibold">{doc.name}</Text>
                <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>
                  {formatBytes(doc.size)} · {doc.type}
                </Text>
              </div>
              <Badge appearance="tint" color="success">Ready</Badge>
              <Button
                appearance="subtle"
                size="small"
                onClick={() => removeDoc(doc.name)}
                aria-label={`Remove ${doc.name}`}
              >
                ✕
              </Button>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: tokens.spacingHorizontalM }}>
        <Button appearance="secondary" onClick={() => navigate('/dispute')}>Back</Button>
        <Button appearance="primary" onClick={() => navigate('/review')}>
          {documents.length > 0 ? 'Next: Review & Submit' : 'Skip & Review'}
        </Button>
      </div>
    </AppShell>
  );
}
