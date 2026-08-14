import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Text,
  Title2,
  Body1,
  tokens,
  Button,
  Divider,
  Badge,
  MessageBar,
  MessageBarBody,
  Spinner,
} from '@fluentui/react-components';
import { AppShell } from '../components/AppShell.tsx';
import { useWizard } from '../App.tsx';
import { submitDispute, uploadDocument, computeDeadlineUtc, USE_MOCK } from '../api/disputes.ts';
import { markTransactionDisputed } from '../utils/disputedTransactions.ts';
import { storeDispute } from '../utils/storedDisputes.ts';
import { getCustomerId, setPreferredCardholderName } from '../utils/customerProfile.ts';
import type { DisputeSubmissionPayload } from '../types/dispute.ts';

export function ReviewPage() {
  const navigate = useNavigate();
  const { transaction, formData, documents, rawFiles, setSubmittedCase } = useWizard();
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  useEffect(() => {
    if (!transaction || !formData) navigate('/');
  }, [transaction, formData, navigate]);

  if (!transaction || !formData) return null;

  async function handleSubmit() {
    if (!transaction || !formData) return;
    setSubmitting(true);
    setSubmitError(null);
    setUploadProgress(null);
    try {
      const customerId = getCustomerId();
      setPreferredCardholderName(formData.cardholderName);

      const payload: DisputeSubmissionPayload = {
        networkCode: transaction.cardNetwork,
        reasonCode: formData.reasonCode,
        cardholderName: formData.cardholderName,
        cardLastFour: transaction.cardLastFour,
        transactionAmount: transaction.amount,
        transactionCurrency: transaction.currency,
        transactionDate: transaction.date,
        merchantName: transaction.merchantName,
        // Only estimate a deadline client-side in mock/demo mode. On the real
        // API path we omit the field entirely so the server auto-calculates
        // the correct per-network SLA deadline (see api/disputes.ts header).
        ...(USE_MOCK ? { deadlineUtc: computeDeadlineUtc() } : {}),
        metadata: {
          description: formData.description,
          attachments: documents,
          merchantCategory: transaction.merchantCategory,
          portalSubmission: true,
          customerId,
        },
      };
      const result = await submitDispute(payload);

      // Upload files after dispute creation
      if (rawFiles.length > 0) {
        const caseId = result.id || result.disputeId;
        for (let i = 0; i < rawFiles.length; i++) {
          setUploadProgress(`Uploading ${i + 1} of ${rawFiles.length}: ${rawFiles[i].name}`);
          await uploadDocument(caseId, rawFiles[i], {
            submittedBy: customerId,
            submittedFrom: 'customer_portal',
            note: formData.description,
          });
        }
        setUploadProgress(null);
      }

      markTransactionDisputed(transaction);
      setSubmittedCase(result);
      storeDispute(result, formData.reasonCode, formData.description);
      navigate('/confirmation');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'An unexpected error occurred. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  const txnDateFormatted = new Date(transaction.date + 'T00:00:00').toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const amountFormatted = new Intl.NumberFormat('en-US', { style: 'currency', currency: transaction.currency }).format(transaction.amount);

  return (
    <AppShell step={4}>
      <Button appearance="subtle" onClick={() => navigate('/upload')} style={{ marginBottom: tokens.spacingVerticalM }}>
        ← Back to documents
      </Button>

      <Title2 style={{ marginBottom: tokens.spacingVerticalXS }}>Review your submission</Title2>
      <Body1 style={{ color: tokens.colorNeutralForeground2, marginBottom: tokens.spacingVerticalL, display: 'block' }}>
        Please confirm the details below before submitting. Once submitted, your case will be assigned a reference number.
      </Body1>

      {/* Transaction */}
      <SectionCard title="Transaction">
        <ReviewRow label="Merchant" value={transaction.merchantName} />
        <ReviewRow label="Amount" value={amountFormatted} />
        <ReviewRow label="Date" value={txnDateFormatted} />
        <ReviewRow label="Card" value={`${transaction.cardNetwork.charAt(0).toUpperCase() + transaction.cardNetwork.slice(1)} ···· ${transaction.cardLastFour}`} />
        <ReviewRow label="Category" value={transaction.merchantCategory} />
      </SectionCard>

      {/* Dispute details */}
      <SectionCard title="Dispute Details">
        <ReviewRow label="Cardholder name" value={formData.cardholderName} />
        <ReviewRow label="Reason code" value={formData.reasonCode} />
        <ReviewRow label="Description" value={formData.description} />
      </SectionCard>

      {/* Documents */}
      <SectionCard title="Supporting Documents">
        {documents.length === 0 ? (
          <Text size={300} style={{ color: tokens.colorNeutralForeground3 }}>No documents attached.</Text>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS }}>
            {documents.map(doc => (
              <div key={doc.name} style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS }}>
                <Badge appearance="tint" color="success" size="small">✓</Badge>
                <Text size={300}>{doc.name}</Text>
                <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                  ({(doc.size / 1024).toFixed(0)} KB)
                </Text>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {uploadProgress && (
        <MessageBar intent="info" style={{ marginBottom: tokens.spacingVerticalM }}>
          <MessageBarBody>{uploadProgress}</MessageBarBody>
        </MessageBar>
      )}

      {submitError && (
        <MessageBar intent="error" style={{ marginBottom: tokens.spacingVerticalM }}>
          <MessageBarBody>{submitError}</MessageBarBody>
        </MessageBar>
      )}

      <MessageBar intent="warning" style={{ marginBottom: tokens.spacingVerticalL }}>
        <MessageBarBody>
          By submitting, you confirm that all information provided is accurate to the best of your knowledge.
        </MessageBarBody>
      </MessageBar>

      <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'center' }}>
        <Button appearance="secondary" onClick={() => navigate('/upload')} disabled={submitting}>Back</Button>
        <Button
          appearance="primary"
          onClick={handleSubmit}
          disabled={submitting}
          icon={submitting ? <Spinner size="tiny" /> : undefined}
        >
          {submitting ? (uploadProgress ? 'Uploading…' : 'Submitting…') : 'Submit Dispute'}
        </Button>
      </div>
    </AppShell>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        backgroundColor: tokens.colorNeutralBackground1,
        border: `1px solid ${tokens.colorNeutralStroke2}`,
        borderRadius: tokens.borderRadiusMedium,
        padding: tokens.spacingVerticalM,
        marginBottom: tokens.spacingVerticalM,
      }}
    >
      <Text weight="semibold" size={400} style={{ marginBottom: tokens.spacingVerticalS, display: 'block' }}>{title}</Text>
      <Divider style={{ marginBottom: tokens.spacingVerticalM }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS }}>
        {children}
      </div>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap' }}>
      <Text size={300} style={{ color: tokens.colorNeutralForeground3, minWidth: '160px' }}>{label}</Text>
      <Text size={300} weight="semibold">{value}</Text>
    </div>
  );
}
