import { Text, Title3, tokens } from '@fluentui/react-components';
import type { CaseSummary } from '../types/case';
import { isActive, isClosed, isNeedsReview, isOpen } from '../utils/queueStatus';

export type QueueKpiKey = 'open' | 'active' | 'needs-review' | 'decision-rate' | 'exposure' | 'urgent';

interface KpiCardsProps {
  cases: CaseSummary[];
  selectedKpi?: QueueKpiKey | null;
  onKpiClick?: (key: QueueKpiKey) => void;
}

interface KpiItem {
  key: QueueKpiKey;
  label: string;
  value: string;
  trend?: string;
  color?: string;
}

export function KpiCards({ cases, selectedKpi, onKpiClick }: KpiCardsProps) {
  const openCount = cases.filter(isOpen).length;
  const activeCount = cases.filter(isActive).length;
  const needsReview = cases.filter(isNeedsReview).length;
  const closedCases = cases.filter(isClosed);
  const closedCount = closedCases.length;

  const approvalCount = closedCases.filter((c) => c.status === 'approved' || c.status === 'submitted').length;
  const denialCount = closedCases.filter((c) => c.status === 'denied').length;
  const decisionTotal = approvalCount + denialCount;
  const approvalRate = decisionTotal > 0 ? Math.round((approvalCount / decisionTotal) * 100) : 0;
  const denialRate = decisionTotal > 0 ? Math.round((denialCount / decisionTotal) * 100) : 0;

  const totalExposure = cases
    .filter((c) => !isClosed(c))
    .reduce((sum, c) => sum + (c.transactionAmount ?? 0), 0);

  const urgentCount = cases.filter(
    (c) => !isClosed(c) && c.deadline.daysRemaining <= 3
  ).length;

  const kpis: KpiItem[] = [
    { key: 'open', label: 'Open Cases', value: String(openCount), color: tokens.colorPaletteBlueBackground2 },
    { key: 'active', label: 'Active', value: String(activeCount), color: tokens.colorPaletteGreenBackground2 },
    { key: 'needs-review', label: 'Needs Review', value: String(needsReview), color: tokens.colorPaletteYellowBackground2 },
    {
      key: 'decision-rate',
      label: 'Approval / Denial Rate',
      value: `${approvalRate}% / ${denialRate}%`,
      trend: `${decisionTotal} decided (${closedCount} closed total)`,
    },
    { key: 'exposure', label: 'Total Exposure', value: `$${totalExposure.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` },
    { key: 'urgent', label: 'Urgent (≤3 days)', value: String(urgentCount), color: urgentCount > 0 ? tokens.colorPaletteRedBackground2 : undefined },
  ];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: '12px',
        marginBottom: '20px',
      }}
    >
      {kpis.map((kpi) => {
        const isSelected = selectedKpi === kpi.key;
        return (
          <div
            key={kpi.label}
            onClick={() => onKpiClick?.(kpi.key)}
            style={{
              padding: '16px',
              borderRadius: '8px',
              border: `1px solid ${isSelected ? (kpi.color ?? tokens.colorBrandStroke1) : tokens.colorNeutralStroke2}`,
              background: isSelected ? tokens.colorNeutralBackground1Hover : tokens.colorNeutralBackground1,
              borderLeft: kpi.color ? `4px solid ${kpi.color}` : undefined,
              cursor: onKpiClick ? 'pointer' : undefined,
              boxShadow: isSelected ? tokens.shadow4 : undefined,
              transition: 'all 0.15s ease',
            }}
          >
            <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '4px' }}>
              {kpi.label}
            </Text>
            <Title3 style={{ margin: 0 }}>{kpi.value}</Title3>
            {kpi.trend && (
              <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: '2px' }}>
                {kpi.trend}
              </Text>
            )}
          </div>
        );
      })}
    </div>
  );
}
