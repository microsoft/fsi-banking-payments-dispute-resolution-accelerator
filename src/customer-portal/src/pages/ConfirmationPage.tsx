import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Text,
  Title1,
  Body1,
  tokens,
  Button,
  Badge,
  Divider,
} from '@fluentui/react-components';
import { AppShell } from '../components/AppShell.tsx';
import { useWizard } from '../App.tsx';

export function ConfirmationPage() {
  const navigate = useNavigate();
  const { transaction, formData, documents, submittedCase, reset } = useWizard();

  useEffect(() => {
    if (!submittedCase) navigate('/');
  }, [submittedCase, navigate]);

  if (!submittedCase || !transaction || !formData) return null;

  const caseRef = submittedCase.disputeId;
  const submittedAt = new Date(submittedCase.createdAt).toLocaleString('en-US', {
    dateStyle: 'long', timeStyle: 'short',
  });
  const amountFormatted = new Intl.NumberFormat('en-US', { style: 'currency', currency: transaction.currency }).format(transaction.amount);

  function handleNewDispute() {
    reset();
    navigate('/');
  }

  return (
    <AppShell>
      {/* Success banner */}
      <div
        style={{
          backgroundColor: tokens.colorStatusSuccessBackground1,
          border: `1px solid ${tokens.colorStatusSuccessBorderActive}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: `${tokens.spacingVerticalXL} ${tokens.spacingHorizontalXXL}`,
          textAlign: 'center',
          marginBottom: tokens.spacingVerticalXL,
        }}
      >
        <div style={{ fontSize: '48px', marginBottom: tokens.spacingVerticalS }}>✅</div>
        <Title1 style={{ color: tokens.colorStatusSuccessForeground1, marginBottom: tokens.spacingVerticalXS }}>
          Dispute Submitted
        </Title1>
        <Body1 style={{ color: tokens.colorNeutralForeground2 }}>
          Your dispute has been received and a case has been opened. Keep your reference number safe.
        </Body1>
      </div>

      {/* Reference card */}
      <div
        style={{
          backgroundColor: tokens.colorNeutralBackground1,
          border: `2px solid ${tokens.colorBrandStroke1}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: tokens.spacingVerticalL,
          marginBottom: tokens.spacingVerticalXL,
          textAlign: 'center',
        }}
      >
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: tokens.spacingVerticalXS }}>
          Your dispute reference number
        </Text>
        <Text weight="bold" size={600} style={{ color: tokens.colorBrandForeground1, fontFamily: 'monospace', letterSpacing: '0.04em' }}>
          {caseRef}
        </Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: tokens.spacingVerticalXS }}>
          Submitted on {submittedAt}
        </Text>
      </div>

      {/* Summary */}
      <div
        style={{
          backgroundColor: tokens.colorNeutralBackground1,
          border: `1px solid ${tokens.colorNeutralStroke2}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: tokens.spacingVerticalM,
          marginBottom: tokens.spacingVerticalXL,
        }}
      >
        <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: tokens.spacingVerticalS }}>Case summary</Text>
        <Divider style={{ marginBottom: tokens.spacingVerticalM }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS }}>
          <SummaryRow label="Merchant" value={transaction.merchantName} />
          <SummaryRow label="Amount disputed" value={amountFormatted} />
          <SummaryRow label="Reason" value={formData.reasonCode} />
          <SummaryRow label="Status">
            <Badge appearance="tint" color="warning">Under Review</Badge>
          </SummaryRow>
          <SummaryRow label="Documents">
            <Text size={300}>{documents.length > 0 ? `${documents.length} file(s) attached` : 'None'}</Text>
          </SummaryRow>
        </div>
      </div>

      {/* Next steps */}
      <div
        style={{
          backgroundColor: tokens.colorNeutralBackground3,
          border: `1px solid ${tokens.colorNeutralStroke2}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: tokens.spacingVerticalM,
          marginBottom: tokens.spacingVerticalXL,
        }}
      >
        <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: tokens.spacingVerticalM }}>What happens next</Text>
        <ol style={{ margin: 0, paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS }}>
          <li><Text size={300}>Our team will review your dispute within <strong>3–5 business days</strong>.</Text></li>
          <li><Text size={300}>You may receive a request for additional information via email.</Text></li>
          <li><Text size={300}>A provisional credit may be applied to your account during the investigation.</Text></li>
          <li><Text size={300}>You will be notified of the outcome once a decision is reached (typically within 30–45 days).</Text></li>
        </ol>
      </div>

      <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap' }}>
        <Button appearance="primary" onClick={() => navigate('/status?from=submit')}>View dispute status</Button>
        <Button appearance="secondary" onClick={handleNewDispute}>Submit another dispute</Button>
        <Button
          appearance="secondary"
          onClick={() => {
            navigator.clipboard?.writeText(caseRef).catch(() => {});
          }}
        >
          Copy reference number
        </Button>
      </div>
    </AppShell>
  );
}

function SummaryRow({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap', alignItems: 'center' }}>
      <Text size={300} style={{ color: tokens.colorNeutralForeground3, minWidth: '160px' }}>{label}</Text>
      {children ?? <Text size={300} weight="semibold">{value}</Text>}
    </div>
  );
}
