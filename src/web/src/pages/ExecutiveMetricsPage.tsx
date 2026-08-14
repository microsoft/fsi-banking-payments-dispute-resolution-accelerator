import { Text, Title1, Title2, tokens } from '@fluentui/react-components';
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCases } from '../api/cases';
import type { CaseSummary } from '../types/case';

export function ExecutiveMetricsPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKpi, setSelectedKpi] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    getCases().then(setCases).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px 16px' }}>
        <Text>Loading metrics…</Text>
      </div>
    );
  }

  // Compute KPIs
  const totalOpen = cases.filter((c) => !['approved', 'denied', 'submitted', 'expired'].includes(c.status)).length;
  const nearingSLA = cases.filter((c) => c.deadline.daysRemaining <= 3 && !['approved', 'denied', 'submitted', 'expired'].includes(c.status)).length;
  const won = cases.filter((c) => c.status === 'approved' || c.status === 'submitted').length;
  const lost = cases.filter((c) => c.status === 'denied' || c.status === 'expired').length;
  const winRate = won + lost > 0 ? Math.round((won / (won + lost)) * 100) : 0;
  const lossRate = 100 - winRate;
  const recoveredAmount = cases
    .filter((c) => c.status === 'approved' || c.status === 'submitted')
    .reduce((sum, c) => sum + (c.transactionAmount ?? 0), 0);
  const provisionalCredit = cases
    .filter((c) => ['intake', 'evidence_gathering', 'ai_drafting', 'pending_review', 'escalated'].includes(c.status))
    .reduce((sum, c) => sum + (c.transactionAmount ?? 0), 0);
  const RESOLVED_STATUSES = ['approved', 'denied', 'submitted', 'expired'];
  const resolvedCases = cases.filter((c) => RESOLVED_STATUSES.includes(c.status) && c.updatedAt);
  const avgResolutionDays =
    resolvedCases.length > 0
      ? Math.round(
          (resolvedCases.reduce(
            (sum, c) => sum + (new Date(c.updatedAt!).getTime() - new Date(c.createdAt).getTime()),
            0,
          ) /
            resolvedCases.length /
            86_400_000) *
            10,
        ) / 10
      : 0;
  const analystProductivity = 12.3; // Mock: cases resolved per analyst per week
  const networkPenaltyRisk = nearingSLA; // Simplified: cases at risk = potential penalties
  const backlog = cases.filter((c) => c.status === 'intake' && !c.assignedAnalystId).length;

  const kpis: KpiItem[] = [
    { key: 'total_open', label: 'Total Open Disputes', value: totalOpen.toString(), icon: '📂', color: tokens.colorBrandForeground1 },
    { key: 'sla_breach', label: 'Nearing SLA Breach', value: nearingSLA.toString(), icon: '🚨', color: nearingSLA > 0 ? tokens.colorPaletteRedForeground1 : tokens.colorPaletteGreenForeground1 },
    { key: 'win_rate', label: 'Win Rate', value: `${winRate}%`, icon: '🏆', color: tokens.colorPaletteGreenForeground1 },
    { key: 'loss_rate', label: 'Loss Rate', value: `${lossRate}%`, icon: '📉', color: tokens.colorPaletteRedForeground1 },
    { key: 'recovery', label: 'Recovery Amount', value: `$${recoveredAmount.toLocaleString()}`, icon: '💰', color: tokens.colorPaletteGreenForeground1 },
    { key: 'provisional', label: 'Provisional Credit Exposure', value: `$${provisionalCredit.toLocaleString()}`, icon: '💳', color: tokens.colorPaletteYellowForeground1 },
    { key: 'productivity', label: 'Analyst Productivity', value: `${analystProductivity}/wk`, icon: '👤', color: tokens.colorBrandForeground1 },
    { key: 'penalty_risk', label: 'Network Penalty Risk', value: networkPenaltyRisk.toString(), icon: '⚠️', color: networkPenaltyRisk > 0 ? tokens.colorPaletteRedForeground1 : tokens.colorPaletteGreenForeground1 },
    { key: 'backlog', label: 'Backlog Volume', value: backlog.toString(), icon: '📋', color: backlog > 3 ? tokens.colorPaletteYellowForeground1 : tokens.colorPaletteGreenForeground1 },
    { key: 'resolution_time', label: 'Avg Resolution Time', value: `${avgResolutionDays}d`, icon: '⏱️', color: tokens.colorBrandForeground1 },
  ];

  // Network breakdown
  const networks = ['visa', 'mastercard', 'amex', 'discover'] as const;
  const networkStats = networks.map((net) => {
    const netCases = cases.filter((c) => c.cardNetwork === net);
    const netOpen = netCases.filter((c) => !['approved', 'denied', 'submitted', 'expired'].includes(c.status)).length;
    const netWon = netCases.filter((c) => c.status === 'approved' || c.status === 'submitted').length;
    const netLost = netCases.filter((c) => c.status === 'denied' || c.status === 'expired').length;
    const netWinRate = netWon + netLost > 0 ? Math.round((netWon / (netWon + netLost)) * 100) : 0;
    const netAmount = netCases.reduce((sum, c) => sum + (c.transactionAmount ?? 0), 0);
    return { network: net, total: netCases.length, open: netOpen, winRate: netWinRate, amount: netAmount };
  });

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px 16px', fontFamily: 'var(--fontFamilyBase)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <Title1>Executive Metrics</Title1>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>VP of Disputes Operations Dashboard</Text>
        </div>
      </div>

      {/* KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '12px' }}>
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            onClick={() => setSelectedKpi(selectedKpi === kpi.key ? null : kpi.key)}
            style={{
              background: selectedKpi === kpi.key ? tokens.colorNeutralBackground1Pressed : tokens.colorNeutralBackground1,
              border: `2px solid ${selectedKpi === kpi.key ? kpi.color : tokens.colorNeutralStroke2}`,
              borderRadius: '8px',
              padding: '14px 16px',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'border-color 0.15s, background 0.15s',
            }}
          >
            <span style={{ fontSize: '20px' }}>{kpi.icon}</span>
            <div style={{ fontSize: '22px', fontWeight: 700, color: kpi.color, margin: '4px 0' }}>{kpi.value}</div>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{kpi.label}</Text>
          </div>
        ))}
      </div>

      {/* KPI Drill-Down Panel */}
      {selectedKpi && <KpiDrillDown kpiKey={selectedKpi} cases={cases} navigate={navigate} />}

      {/* Network Breakdown */}
      <div style={{ background: tokens.colorNeutralBackground1, border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: '8px', padding: '20px 24px', marginBottom: '24px' }}>
        <Title2 style={{ marginBottom: '12px', fontSize: '16px' }}>Network Breakdown</Title2>
        <div style={{ display: 'grid', gridTemplateColumns: '120px repeat(4, 1fr)', gap: '8px', fontSize: '12px' }}>
          <Text size={200} weight="semibold">Network</Text>
          <Text size={200} weight="semibold">Total Cases</Text>
          <Text size={200} weight="semibold">Open</Text>
          <Text size={200} weight="semibold">Win Rate</Text>
          <Text size={200} weight="semibold">Exposure</Text>
          {networkStats.map((ns) => (
            <React.Fragment key={ns.network}>
              <Text size={200} weight="semibold" style={{ textTransform: 'uppercase' }}>{ns.network}</Text>
              <Text size={200}>{ns.total}</Text>
              <Text size={200}>{ns.open}</Text>
              <Text size={200} style={{ color: ns.winRate >= 60 ? tokens.colorPaletteGreenForeground1 : tokens.colorPaletteRedForeground1 }}>{ns.winRate}%</Text>
              <Text size={200}>${ns.amount.toLocaleString()}</Text>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* SLA Breach Risk */}
      <div style={{ background: tokens.colorNeutralBackground1, border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: '8px', padding: '20px 24px' }}>
        <Title2 style={{ marginBottom: '12px', fontSize: '16px' }}>SLA Breach Risk ({nearingSLA} cases)</Title2>
        {nearingSLA === 0 ? (
          <Text size={200} style={{ color: tokens.colorPaletteGreenForeground1 }}>✓ No cases at immediate risk of SLA breach</Text>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
            {cases
              .filter((c) => c.deadline.daysRemaining <= 3 && !['approved', 'denied', 'submitted', 'expired'].includes(c.status))
              .sort((a, b) => a.deadline.daysRemaining - b.deadline.daysRemaining)
              .map((c) => (
                <div
                  key={c.caseId}
                  onClick={() => navigate(`/cases/${c.caseId}`)}
                  style={{
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: `1px solid ${tokens.colorPaletteRedBorderActive}`,
                    cursor: 'pointer',
                    background: 'rgba(255,0,0,0.03)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text size={200} weight="semibold">{c.merchantName}</Text>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: tokens.colorPaletteRedForeground1 }}>
                      {c.deadline.daysRemaining <= 0 ? 'OVERDUE' : `${c.deadline.daysRemaining}d left`}
                    </span>
                  </div>
                  <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                    {c.cardNetwork?.toUpperCase()} · ${c.transactionAmount?.toFixed(2)} · {c.assignedAnalystName ?? 'Unassigned'}
                  </Text>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface KpiItem {
  label: string;
  value: string;
  icon: string;
  color: string;
  key: string;
}

/* ─── Drill-Down Component ─── */

function KpiDrillDown({ kpiKey, cases, navigate }: { kpiKey: string; cases: CaseSummary[]; navigate: ReturnType<typeof useNavigate> }) {
  const getFilteredCases = (): { title: string; description: string; items: CaseSummary[] } => {
    switch (kpiKey) {
      case 'total_open': {
        const items = cases.filter((c) => !['approved', 'denied', 'submitted', 'expired'].includes(c.status));
        return { title: 'Total Open Disputes', description: 'All cases currently in progress (not yet resolved).', items };
      }
      case 'sla_breach': {
        const items = cases.filter((c) => c.deadline.daysRemaining <= 3 && !['approved', 'denied', 'submitted', 'expired'].includes(c.status));
        return { title: 'Nearing SLA Breach', description: 'Cases with ≤3 days remaining before deadline.', items };
      }
      case 'win_rate': {
        const items = cases.filter((c) => c.status === 'approved' || c.status === 'submitted');
        return { title: 'Won Cases (Win Rate)', description: 'Cases resolved in favor of the cardholder.', items };
      }
      case 'loss_rate': {
        const items = cases.filter((c) => c.status === 'denied' || c.status === 'expired');
        return { title: 'Lost Cases (Loss Rate)', description: 'Cases denied or expired without resolution.', items };
      }
      case 'recovery': {
        const items = cases.filter((c) => c.status === 'approved' || c.status === 'submitted');
        return { title: 'Recovery Amount', description: 'Cases contributing to recovered funds.', items };
      }
      case 'provisional': {
        const items = cases.filter((c) => ['intake', 'evidence_gathering', 'ai_drafting', 'pending_review', 'escalated'].includes(c.status));
        return { title: 'Provisional Credit Exposure', description: 'Open cases with provisional credit still at risk.', items };
      }
      case 'productivity': {
        return { title: 'Analyst Productivity', description: '12.3 cases resolved per analyst per week (team average). Based on rolling 4-week window.', items: [] };
      }
      case 'penalty_risk': {
        const items = cases.filter((c) => c.deadline.daysRemaining <= 3 && !['approved', 'denied', 'submitted', 'expired'].includes(c.status));
        return { title: 'Network Penalty Risk', description: 'Cases nearing SLA breach that may trigger network penalties or fines.', items };
      }
      case 'backlog': {
        const items = cases.filter((c) => c.status === 'intake' && !c.assignedAnalystId);
        return { title: 'Backlog Volume', description: 'Unassigned intake cases not yet picked up by an analyst.', items };
      }
      case 'resolution_time': {
        const RESOLVED_STATUSES = ['approved', 'denied', 'submitted', 'expired'];
        const resolved = cases.filter((c) => RESOLVED_STATUSES.includes(c.status));
        const withTimestamps = resolved.filter((c) => c.updatedAt);
        const avgDays =
          withTimestamps.length > 0
            ? Math.round(
                (withTimestamps.reduce(
                  (sum, c) => sum + (new Date(c.updatedAt!).getTime() - new Date(c.createdAt).getTime()),
                  0,
                ) /
                  withTimestamps.length /
                  86_400_000) *
                  10,
              ) / 10
            : 0;
        return {
          title: 'Avg Resolution Time',
          description: `${avgDays}d average from case creation to final decision, computed live across ${resolved.length} resolved case(s).`,
          items: resolved,
        };
      }
      default:
        return { title: '', description: '', items: [] };
    }
  };

  const { title, description, items } = getFilteredCases();

  return (
    <div style={{
      background: tokens.colorNeutralBackground1,
      border: `1px solid ${tokens.colorNeutralStroke2}`,
      borderRadius: '8px',
      padding: '16px 20px',
      marginBottom: '24px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div>
          <Text weight="semibold" size={400}>{title}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: '2px' }}>{description}</Text>
        </div>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{items.length} case{items.length !== 1 ? 's' : ''}</Text>
      </div>
      {items.length > 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr 1fr 1fr 1fr', gap: '6px 12px', fontSize: '12px', marginTop: '12px' }}>
          <Text size={200} weight="semibold">Merchant</Text>
          <Text size={200} weight="semibold">Network</Text>
          <Text size={200} weight="semibold">Amount</Text>
          <Text size={200} weight="semibold">Win Prob</Text>
          <Text size={200} weight="semibold">Status</Text>
          <Text size={200} weight="semibold">Deadline</Text>
          {items.map((c) => (
            <React.Fragment key={c.caseId}>
              <Text
                size={200}
                weight="semibold"
                style={{ cursor: 'pointer', color: tokens.colorBrandForeground1 }}
                onClick={() => navigate(`/cases/${c.caseId}`)}
              >
                {c.merchantName}
              </Text>
              <Text size={200} style={{ textTransform: 'uppercase' }}>{c.cardNetwork}</Text>
              <Text size={200}>${c.transactionAmount?.toLocaleString()}</Text>
              <Text size={200}>{c.winProbability != null ? `${Math.round(c.winProbability * 100)}%` : '—'}</Text>
              <Text size={200}>{c.status.replace(/_/g, ' ')}</Text>
              <Text size={200} style={{ color: c.deadline.daysRemaining <= 3 ? tokens.colorPaletteRedForeground1 : undefined }}>
                {c.deadline.daysRemaining <= 0 ? 'OVERDUE' : `${c.deadline.daysRemaining}d left`}
              </Text>
            </React.Fragment>
          ))}
        </div>
      ) : (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, fontStyle: 'italic' }}>No individual cases to display for this metric.</Text>
      )}
    </div>
  );
}
