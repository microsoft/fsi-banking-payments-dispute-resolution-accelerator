import { Text, tokens } from '@fluentui/react-components';
import type { Case } from '../types/case';

interface CaseMetadataProps {
  disputeCase: Case;
}

interface MetadataRow {
  label: string;
  value: string | undefined;
  monospace?: boolean;
}

export function CaseMetadata({ disputeCase: c }: CaseMetadataProps) {
  const rows: MetadataRow[] = [
    { label: 'Case ID', value: c.caseId, monospace: true },
    { label: 'Dispute Ref', value: c.disputeRef, monospace: true },
    { label: 'Orchestration ID', value: c.orchestrationId, monospace: true },
    { label: 'Network', value: c.cardNetwork?.toUpperCase() },
    { label: 'Merchant', value: c.merchantName },
    { label: 'Cardholder', value: c.cardholderName },
    { label: 'Transaction Date', value: c.transactionDate ? new Date(c.transactionDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : undefined },
    { label: 'Amount', value: c.transactionAmount !== undefined ? `$${c.transactionAmount.toFixed(2)}` : undefined },
    { label: 'Assigned To', value: c.assignedAnalystName ?? 'Unassigned' },
    { label: 'Created', value: c.createdAt ? new Date(c.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : undefined },
    { label: 'Last Updated', value: c.updatedAt ? new Date(c.updatedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : undefined },
    { label: 'Resolved', value: c.resolvedAt ? new Date(c.resolvedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : undefined },
  ].filter((r) => r.value !== undefined && r.value !== '') as MetadataRow[];

  return (
    <div>
      <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: '10px' }}>
        Case Details
      </Text>

      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
        {rows.map((row) => (
          <div key={row.label} style={{ display: 'contents' }}>
            <Text size={200} style={{ color: tokens.colorNeutralForeground3, whiteSpace: 'nowrap' }}>
              {row.label}
            </Text>
            <Text
              size={200}
              weight="semibold"
              style={{
                fontFamily: row.monospace ? 'monospace' : 'inherit',
                fontSize: row.monospace ? '11px' : undefined,
                wordBreak: 'break-all',
              }}
            >
              {row.value}
            </Text>
          </div>
        ))}
      </div>
    </div>
  );
}
