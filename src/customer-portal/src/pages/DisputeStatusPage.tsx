import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Text,
  Title1,
  Title2,
  Body1,
  tokens,
  Button,
  Badge,
  Divider,
  Spinner,
  Input,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import type { BadgeProps } from '@fluentui/react-components';
import { AppShell } from '../components/AppShell.tsx';
import { useWizard } from '../App.tsx';
import { getDispute, USE_MOCK } from '../api/disputes.ts';
import type { DisputeCreatedResponse } from '../types/dispute.ts';

// ── Status display config ─────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: BadgeProps['color']; icon: string }> = {
  intake:     { label: 'Received',      color: 'informative', icon: '📥' },
  gathering:  { label: 'Gathering Evidence', color: 'warning', icon: '🔍' },
  drafting:   { label: 'Drafting Rebuttal',  color: 'warning', icon: '📝' },
  review:     { label: 'Under Review',  color: 'warning',     icon: '👀' },
  approved:   { label: 'Approved',      color: 'success',     icon: '✅' },
  rejected:   { label: 'Rejected',      color: 'danger',      icon: '❌' },
  submitted:  { label: 'Submitted to Network', color: 'brand', icon: '📤' },
  escalated:  { label: 'Escalated',     color: 'danger',      icon: '⚠️' },
  closed:     { label: 'Closed',        color: 'subtle',      icon: '📁' },
};

function getStatusDisplay(status: string) {
  return STATUS_CONFIG[status] ?? { label: status, color: 'subtle' as const, icon: '❓' };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function DisputeStatusPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { submittedCase } = useWizard();

  // State
  const [dispute, setDispute] = useState<DisputeCreatedResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lookupId, setLookupId] = useState('');

  // On mount: use submittedCase from wizard context, or ?id= query param
  const loadDispute = useCallback(async (disputeId: string, networkCode: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getDispute(disputeId, networkCode);
      setDispute(result);
    } catch (err) {
      // In dev/demo mode, fall back to the submitted case data if available
      if ((USE_MOCK || import.meta.env.DEV) && submittedCase) {
        setDispute(submittedCase);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load dispute');
      }
    } finally {
      setLoading(false);
    }
  }, [submittedCase]);

  useEffect(() => {
    const queryId = searchParams.get('id');
    const queryNetwork = searchParams.get('network');
    const fromSubmit = searchParams.get('from') === 'submit';

    if (queryId && queryNetwork) {
      loadDispute(queryId, queryNetwork);
    } else if (fromSubmit && submittedCase) {
      // Only auto-show the case when coming from the confirmation page
      setDispute(submittedCase);
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Lookup form ───────────────────────────────────────────────────────────

  if (!dispute && !loading && !error) {
    return (
      <AppShell>
        <Title1 style={{ marginBottom: tokens.spacingVerticalL }}>Check Dispute Status</Title1>
        <Body1 style={{ color: tokens.colorNeutralForeground2, marginBottom: tokens.spacingVerticalXL, display: 'block' }}>
          Enter your dispute reference number to view the current status of your case.
        </Body1>

        <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'end', flexWrap: 'wrap', marginBottom: tokens.spacingVerticalXL }}>
          <div style={{ flex: 1, minWidth: '240px' }}>
            <Text size={200} weight="semibold" style={{ display: 'block', marginBottom: tokens.spacingVerticalXS }}>
              Dispute Reference Number
            </Text>
            <Input
              placeholder="e.g. a1b2c3d4-e5f6-..."
              value={lookupId}
              onChange={(_, data) => setLookupId(data.value)}
              style={{ width: '100%' }}
            />
          </div>
          <Button
            appearance="primary"
            disabled={!lookupId.trim()}
            onClick={() => {
              // For lookup without network code, try with empty string
              // The backend will do a cross-partition query
              navigate(`/status?id=${encodeURIComponent(lookupId.trim())}&network=`);
              loadDispute(lookupId.trim(), '');
            }}
          >
            Look up
          </Button>
        </div>

        <div style={{ display: 'flex', gap: tokens.spacingHorizontalM }}>
          <Button appearance="secondary" onClick={() => navigate('/')}>
            File a new dispute
          </Button>
        </div>
      </AppShell>
    );
  }

  // ── Loading ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <AppShell>
        <div style={{ textAlign: 'center', padding: tokens.spacingVerticalXXXL }}>
          <Spinner size="large" label="Loading dispute status..." />
        </div>
      </AppShell>
    );
  }

  // ── Error ─────────────────────────────────────────────────────────────────

  if (error) {
    return (
      <AppShell>
        <MessageBar intent="error" style={{ marginBottom: tokens.spacingVerticalL }}>
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
        <Button appearance="primary" onClick={() => { setError(null); setDispute(null); }}>
          Try again
        </Button>
      </AppShell>
    );
  }

  // ── Status display ────────────────────────────────────────────────────────

  if (!dispute) return null;

  const statusInfo = getStatusDisplay(dispute.status);
  const createdDate = new Date(dispute.createdAt).toLocaleString('en-US', { dateStyle: 'long', timeStyle: 'short' });
  const deadlineDate = new Date(dispute.deadlineUtc).toLocaleString('en-US', { dateStyle: 'long' });
  const amountFormatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: dispute.transactionCurrency ?? 'USD',
  }).format(dispute.transactionAmount);

  // Days remaining until deadline
  const now = new Date();
  const deadline = new Date(dispute.deadlineUtc);
  const daysRemaining = Math.max(0, Math.ceil((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));
  const isUrgent = daysRemaining <= 7;

  return (
    <AppShell>
      {/* Status header */}
      <div
        style={{
          backgroundColor: tokens.colorNeutralBackground1,
          border: `2px solid ${tokens.colorBrandStroke1}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: `${tokens.spacingVerticalL} ${tokens.spacingHorizontalXL}`,
          marginBottom: tokens.spacingVerticalXL,
          display: 'flex',
          alignItems: 'center',
          gap: tokens.spacingHorizontalL,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontSize: '40px' }}>{statusInfo.icon}</span>
        <div style={{ flex: 1 }}>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: tokens.spacingVerticalXXS }}>
            Current Status
          </Text>
          <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalM }}>
            <Title2>{statusInfo.label}</Title2>
            <Badge appearance="filled" color={statusInfo.color} size="large">
              {dispute.status}
            </Badge>
          </div>
        </div>
      </div>

      {/* Reference + deadline */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: tokens.spacingHorizontalL,
          marginBottom: tokens.spacingVerticalXL,
        }}
      >
        {/* Reference card */}
        <div
          style={{
            backgroundColor: tokens.colorNeutralBackground1,
            border: `1px solid ${tokens.colorNeutralStroke2}`,
            borderRadius: tokens.borderRadiusMedium,
            padding: tokens.spacingVerticalM,
            textAlign: 'center',
          }}
        >
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: tokens.spacingVerticalXS }}>
            Reference Number
          </Text>
          <Text weight="bold" size={500} style={{ fontFamily: 'monospace', color: tokens.colorBrandForeground1 }}>
            {dispute.disputeId}
          </Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: tokens.spacingVerticalXS }}>
            Filed {createdDate}
          </Text>
        </div>

        {/* Deadline card */}
        <div
          style={{
            backgroundColor: isUrgent ? tokens.colorStatusDangerBackground1 : tokens.colorNeutralBackground1,
            border: `1px solid ${isUrgent ? tokens.colorStatusDangerBorderActive : tokens.colorNeutralStroke2}`,
            borderRadius: tokens.borderRadiusMedium,
            padding: tokens.spacingVerticalM,
            textAlign: 'center',
          }}
        >
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: tokens.spacingVerticalXS }}>
            Response Deadline
          </Text>
          <Text weight="bold" size={500} style={{ color: isUrgent ? tokens.colorStatusDangerForeground1 : tokens.colorNeutralForeground1 }}>
            {deadlineDate}
          </Text>
          <Text size={200} style={{ color: isUrgent ? tokens.colorStatusDangerForeground1 : tokens.colorNeutralForeground3, display: 'block', marginTop: tokens.spacingVerticalXS }}>
            {daysRemaining} day{daysRemaining !== 1 ? 's' : ''} remaining
          </Text>
        </div>
      </div>

      {/* Case details */}
      <div
        style={{
          backgroundColor: tokens.colorNeutralBackground1,
          border: `1px solid ${tokens.colorNeutralStroke2}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: tokens.spacingVerticalM,
          marginBottom: tokens.spacingVerticalXL,
        }}
      >
        <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: tokens.spacingVerticalS }}>Case Details</Text>
        <Divider style={{ marginBottom: tokens.spacingVerticalM }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS }}>
          <DetailRow label="Cardholder" value={dispute.cardholderName} />
          <DetailRow label="Card" value={`•••• ${dispute.cardLastFour} (${dispute.networkCode})`} />
          <DetailRow label="Merchant" value={dispute.merchantName} />
          <DetailRow label="Amount" value={amountFormatted} />
          <DetailRow label="Transaction Date" value={new Date(dispute.transactionDate).toLocaleDateString('en-US', { dateStyle: 'long' })} />
          <DetailRow label="Reason Code" value={dispute.reasonCode} />
        </div>
      </div>

      {/* Status timeline (static for now — will be enhanced when timeline API is wired) */}
      <div
        style={{
          backgroundColor: tokens.colorNeutralBackground1,
          border: `1px solid ${tokens.colorNeutralStroke2}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: tokens.spacingVerticalM,
          marginBottom: tokens.spacingVerticalXL,
        }}
      >
        <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: tokens.spacingVerticalS }}>Timeline</Text>
        <Divider style={{ marginBottom: tokens.spacingVerticalM }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM, paddingLeft: tokens.spacingHorizontalM }}>
          <TimelineEntry
            date={createdDate}
            title="Dispute Filed"
            detail={`Dispute submitted for ${amountFormatted} charge at ${dispute.merchantName}`}
            active={dispute.status === 'intake'}
          />
          {dispute.status !== 'intake' && (
            <TimelineEntry
              date=""
              title={statusInfo.label}
              detail={`Case is currently ${statusInfo.label.toLowerCase()}`}
              active
            />
          )}
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap' }}>
        <Button appearance="primary" onClick={() => navigate('/')}>
          File another dispute
        </Button>
        <Button
          appearance="secondary"
          onClick={() => { navigator.clipboard?.writeText(dispute.disputeId).catch(() => {}); }}
        >
          Copy reference number
        </Button>
      </div>
    </AppShell>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap', alignItems: 'center' }}>
      <Text size={300} style={{ color: tokens.colorNeutralForeground3, minWidth: '160px' }}>{label}</Text>
      <Text size={300} weight="semibold">{value}</Text>
    </div>
  );
}

function TimelineEntry({ date, title, detail, active }: { date: string; title: string; detail: string; active?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'flex-start' }}>
      <div
        style={{
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          backgroundColor: active ? tokens.colorBrandBackground : tokens.colorNeutralStroke1,
          marginTop: '6px',
          flexShrink: 0,
        }}
      />
      <div>
        <Text size={300} weight="semibold">{title}</Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>{detail}</Text>
        {date && <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{date}</Text>}
      </div>
    </div>
  );
}
