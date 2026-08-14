import { Text, Title2, tokens } from '@fluentui/react-components';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CaseSummary } from '../types/case';
import { StatusBadge } from './CaseBadges';

interface RelatedCasesPanelProps {
  currentCaseId: string;
  merchantName?: string;
  cardholderName?: string;
  allCases: CaseSummary[];
}

// Mock outcome data for similar cases (in production this comes from API)
const MOCK_OUTCOMES: Record<string, { outcome: 'won' | 'lost'; evidence: string[]; reason: string; lesson: string }> = {};

function getOutcome(caseId: string, index: number) {
  if (MOCK_OUTCOMES[caseId]) return MOCK_OUTCOMES[caseId];
  const outcomes: Array<{ outcome: 'won' | 'lost'; evidence: string[]; reason: string; lesson: string }> = [
    { outcome: 'won', evidence: ['AVS match', 'CVV match', 'Delivery signature'], reason: 'Strong delivery proof + auth verification', lesson: 'Signed delivery is strongest evidence for "not received" disputes' },
    { outcome: 'won', evidence: ['IP match', 'Device fingerprint', 'MFA pass'], reason: 'Digital identity confirmed — true cardholder', lesson: 'Combine device + MFA evidence for auth fraud claims' },
    { outcome: 'lost', evidence: ['Transaction record', 'Merchant receipt'], reason: 'Missing delivery confirmation for physical goods', lesson: 'Always obtain tracking + delivery proof for physical shipments' },
    { outcome: 'won', evidence: ['Chat transcript', 'Refund policy', 'Terms accepted'], reason: 'Customer acknowledged policy at checkout', lesson: 'Screenshot terms acceptance for service disputes' },
    { outcome: 'lost', evidence: ['Authorization log'], reason: 'Insufficient evidence — no proof of service delivery', lesson: 'Service merchants need signed work orders or completion confirmations' },
  ];
  const result = outcomes[index % outcomes.length];
  MOCK_OUTCOMES[caseId] = result;
  return result;
}

export function RelatedCasesPanel({
  currentCaseId,
  merchantName,
  cardholderName,
  allCases,
}: RelatedCasesPanelProps) {
  const navigate = useNavigate();

  const sameMerchant = merchantName
    ? allCases.filter((c) => c.caseId !== currentCaseId && c.merchantName === merchantName)
    : [];

  const customerHistory = allCases.filter(
    (c) => c.caseId !== currentCaseId && c.merchantName !== merchantName
  ).slice(0, 3);

  const hasRelated = sameMerchant.length > 0 || customerHistory.length > 0;

  if (!hasRelated) return null;

  return (
    <div>
      <Title2 style={{ marginBottom: '12px' }}>Similar Cases & History</Title2>

      {sameMerchant.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <Text size={200} weight="semibold" style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '8px' }}>
            Same Merchant — {merchantName}
          </Text>
          {sameMerchant.map((c, i) => (
            <RelatedCaseRow key={c.caseId} caseItem={c} index={i} onClick={() => navigate(`/cases/${c.caseId}`)} />
          ))}
        </div>
      )}

      {customerHistory.length > 0 && (
        <div>
          <Text size={200} weight="semibold" style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '8px' }}>
            Customer History {cardholderName ? `— ${cardholderName}` : ''}
          </Text>
          {customerHistory.map((c, i) => (
            <RelatedCaseRow key={c.caseId} caseItem={c} index={i + sameMerchant.length} onClick={() => navigate(`/cases/${c.caseId}`)} />
          ))}
        </div>
      )}
    </div>
  );
}

function RelatedCaseRow({ caseItem, index, onClick }: { caseItem: CaseSummary; index: number; onClick: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const amount = caseItem.transactionAmount !== undefined
    ? `$${caseItem.transactionAmount.toFixed(2)}`
    : '—';
  const outcome = getOutcome(caseItem.caseId, index);

  return (
    <div style={{ marginBottom: '8px', borderRadius: '6px', border: `1px solid ${tokens.colorNeutralStroke2}`, overflow: 'hidden' }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          cursor: 'pointer',
          transition: 'background 150ms ease',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = tokens.colorNeutralBackground1Hover)}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text size={300} weight="semibold">{caseItem.merchantName ?? 'Unknown'}</Text>
            <span style={{
              fontSize: '11px',
              padding: '1px 6px',
              borderRadius: '3px',
              background: outcome.outcome === 'won' ? tokens.colorPaletteGreenBackground2 : tokens.colorPaletteRedBackground2,
              color: outcome.outcome === 'won' ? tokens.colorPaletteGreenForeground1 : tokens.colorPaletteRedForeground1,
              fontWeight: 600,
            }}>
              {outcome.outcome === 'won' ? '✓ Won' : '✗ Lost'}
            </span>
          </div>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>
            {caseItem.reasonCode} · {caseItem.cardNetwork?.toUpperCase()}
          </Text>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Text size={300}>{amount}</Text>
          <StatusBadge status={caseItem.status} />
          <span style={{ fontSize: '10px', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 150ms' }}>▶</span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '0 12px 12px', borderTop: `1px solid ${tokens.colorNeutralStroke2}`, paddingTop: '10px' }}>
          <div style={{ marginBottom: '8px' }}>
            <Text size={200} weight="semibold" style={{ display: 'block', marginBottom: '2px' }}>Evidence Used:</Text>
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              {outcome.evidence.map((e) => (
                <span key={e} style={{ fontSize: '11px', background: tokens.colorNeutralBackground3, padding: '2px 6px', borderRadius: '3px' }}>{e}</span>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: '8px' }}>
            <Text size={200} weight="semibold" style={{ display: 'block', marginBottom: '2px' }}>Decision Reason:</Text>
            <Text size={200}>{outcome.reason}</Text>
          </div>
          <div style={{ marginBottom: '8px' }}>
            <Text size={200} weight="semibold" style={{ display: 'block', marginBottom: '2px' }}>💡 Lesson Learned:</Text>
            <Text size={200} style={{ color: tokens.colorPaletteBlueForeground2, fontStyle: 'italic' }}>{outcome.lesson}</Text>
          </div>
          <div style={{ textAlign: 'right' }}>
            <Text
              size={200}
              style={{ color: tokens.colorBrandForeground1, cursor: 'pointer', textDecoration: 'underline' }}
              onClick={(e) => { e.stopPropagation(); onClick(); }}
            >
              View Full Case →
            </Text>
          </div>
        </div>
      )}
    </div>
  );
}
