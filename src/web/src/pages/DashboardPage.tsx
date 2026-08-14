import { Text, Title1, Title2, tokens } from '@fluentui/react-components';
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getCases } from '../api/cases';
import { AnalystHeader } from '../components/AnalystHeader';
import { mockAnalyst } from '../mocks/analyst';
import { cardStyle, chartColors, kpiAccents } from '../styles/dashboard';
import type { CaseSummary } from '../types/case';

export function DashboardPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKpi, setSelectedKpi] = useState<string | null>(null);
  const [chartDrill, setChartDrill] = useState<{ type: string; label: string; cases: CaseSummary[] } | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    getCases().then(setCases).finally(() => setLoading(false));
  }, []);

  // Derived KPI data
  const kpis = useMemo(() => {
    const open = cases.filter((c) =>
      ['intake', 'evidence_gathering', 'ai_drafting', 'pending_review', 'escalated'].includes(c.status)
    );
    const needsReview = cases.filter((c) => c.status === 'pending_review');
    const atRisk = cases.filter(
      (c) => c.deadline.daysRemaining <= 3 && !['approved', 'denied', 'submitted', 'expired'].includes(c.status)
    );
    const totalAmount = cases.reduce((sum, c) => sum + (c.transactionAmount ?? 0), 0);
    const avgWin = cases.filter((c) => c.winProbability != null);
    const winRate = avgWin.length > 0
      ? avgWin.reduce((sum, c) => sum + (c.winProbability ?? 0), 0) / avgWin.length
      : 0;

    return { open: open.length, needsReview: needsReview.length, atRisk: atRisk.length, totalAmount, winRate };
  }, [cases]);

  // Chart: Cases by Network (pie)
  const networkData = useMemo(() => {
    const counts: Record<string, number> = {};
    cases.forEach((c) => {
      const net = c.cardNetwork?.toLowerCase() ?? 'other';
      counts[net] = (counts[net] ?? 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), value }));
  }, [cases]);

  // Chart: Cases by Status (bar)
  const statusData = useMemo(() => {
    const statusLabels: Record<string, string> = {
      intake: 'Intake',
      evidence_gathering: 'Evidence',
      ai_drafting: 'AI Draft',
      pending_review: 'Review',
      escalated: 'Escalated',
      approved: 'Approved',
      denied: 'Denied',
      submitted: 'Submitted',
      expired: 'Expired',
    };
    const counts: Record<string, number> = {};
    cases.forEach((c) => {
      const label = statusLabels[c.status] ?? c.status;
      counts[label] = (counts[label] ?? 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [cases]);

  // Chart: Dispute volume by day (area - from createdAt)
  const volumeData = useMemo(() => {
    const days: Record<string, number> = {};
    cases.forEach((c) => {
      if (c.createdAt) {
        const day = c.createdAt.slice(0, 10);
        days[day] = (days[day] ?? 0) + 1;
      }
    });
    return Object.entries(days)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-14)
      .map(([date, count]) => ({ date: date.slice(5), cases: count }));
  }, [cases]);

  // Chart: Risk distribution (horizontal bar)
  const riskData = useMemo(() => {
    const counts = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    cases.forEach((c) => {
      const risk = c.riskLevel ?? 'low';
      if (risk === 'critical') counts.Critical++;
      else if (risk === 'high') counts.High++;
      else if (risk === 'medium') counts.Medium++;
      else counts.Low++;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [cases]);

  // Actionable items
  const actionToday = cases.filter(
    (c) => c.deadline.daysRemaining <= 1 && !['approved', 'denied', 'submitted', 'expired'].includes(c.status)
  );

  const upcomingDeadlines = cases
    .filter(
      (c) =>
        c.deadline.daysRemaining > 0 &&
        c.deadline.daysRemaining <= 7 &&
        !['approved', 'denied', 'submitted', 'expired'].includes(c.status)
    )
    .sort((a, b) => a.deadline.daysRemaining - b.deadline.daysRemaining)
    .slice(0, 6);

  const NETWORK_COLORS: Record<string, string> = {
    Visa: chartColors.visa,
    Mastercard: chartColors.danger,
    Amex: chartColors.amex,
    Discover: chartColors.warning,
    Other: chartColors.muted,
  };

  const RISK_COLORS: Record<string, string> = {
    Critical: chartColors.danger,
    High: chartColors.warning,
    Medium: '#f7b825',
    Low: chartColors.success,
  };

  if (loading) {
    return (
      <div style={{ fontFamily: 'var(--fontFamilyBase)' }}>
        <AnalystHeader analyst={mockAnalyst} activeNetwork={null} onNetworkFilter={() => {}} />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '32px 24px', textAlign: 'center' }}>
          <Text>Loading dashboard…</Text>
        </div>
      </div>
    );
  }

  return (
    <div style={{ fontFamily: 'var(--fontFamilyBase)' }}>
      <AnalystHeader analyst={mockAnalyst} activeNetwork={null} onNetworkFilter={() => {}} />

      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '32px 24px' }}>
        {/* Title row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <Title1>Dashboard</Title1>
          <button
            onClick={() => navigate('/queue')}
            style={{
              background: tokens.colorBrandBackground,
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              padding: '8px 18px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'var(--fontFamilyBase)',
            }}
          >
            View Full Queue →
          </button>
        </div>

        {/* ─── KPI Row ─────────────────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px', marginBottom: '16px' }}>
          <KpiCard label="Total Cases" value={cases.length} accent={kpiAccents.blue} kpiKey="total" selected={selectedKpi === 'total'} onClick={() => setSelectedKpi(selectedKpi === 'total' ? null : 'total')} />
          <KpiCard label="Open Cases" value={kpis.open} accent={kpiAccents.teal} kpiKey="open" selected={selectedKpi === 'open'} onClick={() => setSelectedKpi(selectedKpi === 'open' ? null : 'open')} />
          <KpiCard label="Pending Review" value={kpis.needsReview} accent={kpiAccents.purple} kpiKey="review" selected={selectedKpi === 'review'} onClick={() => setSelectedKpi(selectedKpi === 'review' ? null : 'review')} />
          <KpiCard label="At Risk (≤3d)" value={kpis.atRisk} accent={kpiAccents.red} kpiKey="risk" selected={selectedKpi === 'risk'} onClick={() => setSelectedKpi(selectedKpi === 'risk' ? null : 'risk')} />
          <KpiCard label="Avg Win Rate" value={`${Math.round(kpis.winRate * 100)}%`} accent={kpiAccents.green} kpiKey="winrate" selected={selectedKpi === 'winrate'} onClick={() => setSelectedKpi(selectedKpi === 'winrate' ? null : 'winrate')} />
        </div>

        {/* ─── KPI Drill-Down ─────────────────────────────────────── */}
        {selectedKpi && (
          <KpiDrillDown kpiKey={selectedKpi} cases={cases} navigate={navigate} onClose={() => setSelectedKpi(null)} />
        )}

        {/* ─── Charts Row 1 ─────────────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px', marginBottom: '16px' }}>
          {/* Volume trend */}
          <div style={cardStyle()}>
            <Title2 style={{ fontSize: '14px', marginBottom: '12px' }}>Dispute Volume (Last 14 Days)</Title2>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={volumeData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }} onClick={(e) => {
                if (e?.activeLabel) {
                  const fullDate = Object.keys(
                    (() => { const d: Record<string, number> = {}; cases.forEach((c) => { if (c.createdAt) { d[c.createdAt.slice(0, 10)] = 1; } }); return d; })()
                  ).find((k) => k.slice(5) === e.activeLabel);
                  if (fullDate) {
                    const filtered = cases.filter((c) => c.createdAt?.slice(0, 10) === fullDate);
                    setChartDrill({ type: 'volume', label: `Cases from ${fullDate}`, cases: filtered });
                  }
                }
              }}>
                <defs>
                  <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartColors.primary} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={chartColors.primary} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.colorNeutralStroke2} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke={tokens.colorNeutralForeground3} />
                <YAxis tick={{ fontSize: 11 }} stroke={tokens.colorNeutralForeground3} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: tokens.colorNeutralBackground1,
                    border: `1px solid ${tokens.colorNeutralStroke2}`,
                    borderRadius: '6px',
                    fontSize: '12px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="cases"
                  stroke={chartColors.primary}
                  strokeWidth={2}
                  fill="url(#volumeGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Network distribution (donut) */}
          <div style={cardStyle()}>
            <Title2 style={{ fontSize: '14px', marginBottom: '12px' }}>Cases by Network</Title2>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={networkData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  dataKey="value"
                  stroke="none"
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                  labelLine={false}
                  onClick={(entry) => {
                    const network = entry.name?.toLowerCase();
                    const filtered = cases.filter((c) => (c.cardNetwork?.toLowerCase() ?? 'other') === network);
                    setChartDrill({ type: 'network', label: `${entry.name} Cases`, cases: filtered });
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  {networkData.map((entry) => (
                    <Cell key={entry.name} fill={NETWORK_COLORS[entry.name] ?? chartColors.muted} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend iconSize={10} wrapperStyle={{ fontSize: '11px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ─── Charts Row 2 ─────────────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
          {/* Status distribution */}
          <div style={cardStyle()}>
            <Title2 style={{ fontSize: '14px', marginBottom: '12px' }}>Cases by Status</Title2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={statusData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }} onClick={(e) => {
                if (e?.activeLabel) {
                  const statusLabels: Record<string, string> = {
                    Intake: 'intake', Evidence: 'evidence_gathering', 'AI Draft': 'ai_drafting',
                    Review: 'pending_review', Escalated: 'escalated', Approved: 'approved',
                    Denied: 'denied', Submitted: 'submitted', Expired: 'expired',
                  };
                  const status = statusLabels[e.activeLabel];
                  if (status) {
                    const filtered = cases.filter((c) => c.status === status);
                    setChartDrill({ type: 'status', label: `${e.activeLabel} Cases`, cases: filtered });
                  }
                }
              }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.colorNeutralStroke2} />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke={tokens.colorNeutralForeground3} />
                <YAxis tick={{ fontSize: 11 }} stroke={tokens.colorNeutralForeground3} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: tokens.colorNeutralBackground1,
                    border: `1px solid ${tokens.colorNeutralStroke2}`,
                    borderRadius: '6px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {statusData.map((_, idx) => (
                    <Cell key={idx} fill={idx < 5 ? chartColors.primary : chartColors.success} opacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Risk distribution */}
          <div style={cardStyle()}>
            <Title2 style={{ fontSize: '14px', marginBottom: '12px' }}>Risk Distribution</Title2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={riskData} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 50 }} onClick={(e) => {
                if (e?.activeLabel) {
                  const riskLevel = String(e.activeLabel).toLowerCase();
                  const filtered = cases.filter((c) => (c.riskLevel?.toLowerCase() ?? 'low') === riskLevel);
                  setChartDrill({ type: 'risk', label: `${e.activeLabel} Risk Cases`, cases: filtered });
                }
              }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.colorNeutralStroke2} />
                <XAxis type="number" tick={{ fontSize: 11 }} stroke={tokens.colorNeutralForeground3} allowDecimals={false} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} stroke={tokens.colorNeutralForeground3} />
                <Tooltip
                  contentStyle={{
                    background: tokens.colorNeutralBackground1,
                    border: `1px solid ${tokens.colorNeutralStroke2}`,
                    borderRadius: '6px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {riskData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name] ?? chartColors.muted} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ─── Chart Drill-Down Panel ─────────────────────────────── */}
        {chartDrill && chartDrill.cases.length > 0 && (
          <div style={{
            ...cardStyle({ marginBottom: '16px' }),
            borderTop: `3px solid ${chartColors.primary}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <Text weight="semibold" size={400}>{chartDrill.label}</Text>
                <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: '2px' }}>
                  {chartDrill.cases.length} case{chartDrill.cases.length !== 1 ? 's' : ''} matching this selection
                </Text>
              </div>
              <button
                onClick={() => setChartDrill(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: tokens.colorNeutralForeground3, padding: '4px' }}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 0.8fr 0.8fr 0.8fr 1fr 0.6fr', gap: '4px 12px', fontSize: '12px' }}>
                <Text size={200} weight="semibold">Merchant</Text>
                <Text size={200} weight="semibold">Network</Text>
                <Text size={200} weight="semibold">Amount</Text>
                <Text size={200} weight="semibold">Win Prob</Text>
                <Text size={200} weight="semibold">Status</Text>
                <Text size={200} weight="semibold">Deadline</Text>
                {chartDrill.cases.slice(0, 20).map((c) => (
                  <React.Fragment key={c.caseId}>
                    <Text
                      size={200}
                      weight="semibold"
                      style={{ cursor: 'pointer', color: tokens.colorBrandForeground1 }}
                      onClick={() => navigate(`/cases/${c.caseId}`)}
                    >
                      {c.merchantName ?? 'Unknown'}
                    </Text>
                    <Text size={200} style={{ textTransform: 'uppercase' }}>{c.cardNetwork ?? '—'}</Text>
                    <Text size={200}>${c.transactionAmount?.toLocaleString() ?? '—'}</Text>
                    <Text size={200}>{c.winProbability != null ? `${Math.round(c.winProbability * 100)}%` : '—'}</Text>
                    <Text size={200}>{c.status.replace(/_/g, ' ')}</Text>
                    <Text size={200} style={{ color: c.deadline.daysRemaining <= 3 ? chartColors.danger : undefined }}>
                      {c.deadline.daysRemaining}d
                    </Text>
                  </React.Fragment>
                ))}
              </div>
              {chartDrill.cases.length > 20 && (
                <Text
                  size={200}
                  style={{ color: tokens.colorBrandForeground1, cursor: 'pointer', display: 'block', marginTop: '8px' }}
                  onClick={() => navigate('/queue')}
                >
                  +{chartDrill.cases.length - 20} more → View in Queue
                </Text>
              )}
            </div>
          </div>
        )}

        {/* ─── Action Widgets Row ─────────────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          {/* Action Required Today */}
          <div style={cardStyle()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <Title2 style={{ fontSize: '14px' }}>🔥 Action Required Today</Title2>
                <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>Due within 24 hours</Text>
              </div>
              <span
                style={{
                  fontSize: '22px',
                  fontWeight: 700,
                  color: actionToday.length > 0 ? chartColors.danger : chartColors.success,
                }}
              >
                {actionToday.length}
              </span>
            </div>
            {actionToday.length === 0 && (
              <Text size={200} style={{ color: chartColors.success }}>✓ No urgent items today</Text>
            )}
            {actionToday.slice(0, 4).map((c) => (
              <CaseRow key={c.caseId} caseItem={c} onClick={() => navigate(`/cases/${c.caseId}`)} />
            ))}
          </div>

          {/* Upcoming Deadlines */}
          <div style={cardStyle()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <Title2 style={{ fontSize: '14px' }}>📅 Upcoming Deadlines</Title2>
                <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>Next 7 days</Text>
              </div>
              <span style={{ fontSize: '22px', fontWeight: 700, color: chartColors.primary }}>
                {upcomingDeadlines.length}
              </span>
            </div>
            {upcomingDeadlines.length === 0 && (
              <Text size={200} style={{ color: chartColors.success }}>✓ No deadlines in the next 7 days</Text>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
              {upcomingDeadlines.map((c) => (
                <div
                  key={c.caseId}
                  onClick={() => navigate(`/cases/${c.caseId}`)}
                  style={{
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: `1px solid ${c.deadline.daysRemaining <= 2 ? chartColors.danger : tokens.colorNeutralStroke2}`,
                    cursor: 'pointer',
                    background: c.deadline.daysRemaining <= 2 ? 'rgba(209,52,56,0.04)' : 'transparent',
                    transition: 'background 0.15s',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text size={200} weight="semibold" truncate style={{ maxWidth: '100px' }}>
                      {c.merchantName ?? 'Case'}
                    </Text>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        color: c.deadline.daysRemaining <= 2 ? chartColors.danger : chartColors.warning,
                      }}
                    >
                      {c.deadline.daysRemaining}d
                    </span>
                  </div>
                  <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                    {c.cardNetwork?.toUpperCase()} · {c.reasonCode}
                  </Text>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ─── Financial Summary Row ─────────────────────────────── */}
        <div
          style={{
            ...cardStyle({ marginTop: '16px' }),
            display: 'flex',
            justifyContent: 'space-around',
            alignItems: 'center',
            padding: '16px 24px',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>Total Disputed</Text>
            <Text weight="bold" style={{ fontSize: '18px' }}>
              ${kpis.totalAmount.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </Text>
          </div>
          <div style={{ width: '1px', height: '32px', background: tokens.colorNeutralStroke2 }} />
          <div style={{ textAlign: 'center' }}>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>Avg per Case</Text>
            <Text weight="bold" style={{ fontSize: '18px' }}>
              ${cases.length > 0 ? Math.round(kpis.totalAmount / cases.length).toLocaleString() : '0'}
            </Text>
          </div>
          <div style={{ width: '1px', height: '32px', background: tokens.colorNeutralStroke2 }} />
          <div style={{ textAlign: 'center' }}>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>Resolved</Text>
            <Text weight="bold" style={{ fontSize: '18px' }}>
              {cases.filter((c) => ['approved', 'denied', 'submitted'].includes(c.status)).length}
            </Text>
          </div>
          <div style={{ width: '1px', height: '32px', background: tokens.colorNeutralStroke2 }} />
          <div style={{ textAlign: 'center' }}>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>Queue Velocity</Text>
            <Text weight="bold" style={{ fontSize: '18px', color: chartColors.success }}>+12%</Text>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  accent,
  selected,
  onClick,
}: {
  label: string;
  value: number | string;
  accent: { bg: string; border: string; text: string };
  kpiKey: string;
  selected?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? `${accent.bg}` : accent.bg,
        borderLeft: `4px solid ${accent.border}`,
        border: selected ? `2px solid ${accent.border}` : undefined,
        borderLeftWidth: '4px',
        borderLeftStyle: 'solid',
        borderLeftColor: accent.border,
        borderRadius: '10px',
        padding: '16px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        cursor: 'pointer',
        transition: 'transform 0.15s, box-shadow 0.15s',
        boxShadow: selected ? `0 4px 12px ${accent.border}33` : undefined,
        transform: selected ? 'translateY(-2px)' : undefined,
      }}
    >
      <Text size={100} style={{ color: tokens.colorNeutralForeground3, textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 500 }}>
        {label}
      </Text>
      <span style={{ fontSize: '28px', fontWeight: 700, color: accent.text, lineHeight: 1.1 }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
    </div>
  );
}

function KpiDrillDown({
  kpiKey,
  cases,
  navigate,
  onClose,
}: {
  kpiKey: string;
  cases: CaseSummary[];
  navigate: ReturnType<typeof useNavigate>;
  onClose: () => void;
}) {
  const getDetails = () => {
    switch (kpiKey) {
      case 'total':
        return { title: 'All Cases', description: 'Complete list of dispute cases in the system.', items: cases };
      case 'open':
        return {
          title: 'Open Cases',
          description: 'Cases currently in progress (not yet resolved).',
          items: cases.filter((c) => ['intake', 'evidence_gathering', 'ai_drafting', 'pending_review', 'escalated'].includes(c.status)),
        };
      case 'review':
        return {
          title: 'Pending Review',
          description: 'Cases awaiting analyst review and decision.',
          items: cases.filter((c) => c.status === 'pending_review'),
        };
      case 'risk':
        return {
          title: 'At Risk (≤3 days)',
          description: 'Cases approaching deadline with 3 or fewer days remaining.',
          items: cases.filter((c) => c.deadline.daysRemaining <= 3 && !['approved', 'denied', 'submitted', 'expired'].includes(c.status)),
        };
      case 'winrate': {
        const withProb = cases.filter((c) => c.winProbability != null);
        return {
          title: 'Win Probability Breakdown',
          description: `${withProb.length} cases with assessed win probability. Average: ${withProb.length > 0 ? Math.round((withProb.reduce((s, c) => s + (c.winProbability ?? 0), 0) / withProb.length) * 100) : 0}%.`,
          items: withProb.sort((a, b) => (b.winProbability ?? 0) - (a.winProbability ?? 0)),
        };
      }
      default:
        return { title: '', description: '', items: [] };
    }
  };

  const { title, description, items } = getDetails();

  return (
    <div style={{
      ...cardStyle({ marginBottom: '16px' }),
      borderTop: `3px solid ${chartColors.primary}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <Text weight="semibold" size={400}>{title}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: '2px' }}>{description}</Text>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{items.length} case{items.length !== 1 ? 's' : ''}</Text>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: tokens.colorNeutralForeground3, padding: '4px' }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>
      </div>
      {items.length > 0 && (
        <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 0.8fr 0.8fr 0.8fr 1fr 0.6fr', gap: '4px 12px', fontSize: '12px' }}>
            <Text size={200} weight="semibold">Merchant</Text>
            <Text size={200} weight="semibold">Network</Text>
            <Text size={200} weight="semibold">Amount</Text>
            <Text size={200} weight="semibold">Win Prob</Text>
            <Text size={200} weight="semibold">Status</Text>
            <Text size={200} weight="semibold">Deadline</Text>
            {items.slice(0, 15).map((c) => (
              <React.Fragment key={c.caseId}>
                <Text
                  size={200}
                  weight="semibold"
                  style={{ cursor: 'pointer', color: tokens.colorBrandForeground1 }}
                  onClick={() => navigate(`/cases/${c.caseId}`)}
                >
                  {c.merchantName ?? 'Unknown'}
                </Text>
                <Text size={200} style={{ textTransform: 'uppercase' }}>{c.cardNetwork ?? '—'}</Text>
                <Text size={200}>${c.transactionAmount?.toLocaleString() ?? '—'}</Text>
                <Text size={200}>{c.winProbability != null ? `${Math.round(c.winProbability * 100)}%` : '—'}</Text>
                <Text size={200}>{c.status.replace(/_/g, ' ')}</Text>
                <Text size={200} style={{ color: c.deadline.daysRemaining <= 3 ? chartColors.danger : undefined }}>
                  {c.deadline.daysRemaining}d
                </Text>
              </React.Fragment>
            ))}
          </div>
          {items.length > 15 && (
            <Text
              size={200}
              style={{ color: tokens.colorBrandForeground1, cursor: 'pointer', display: 'block', marginTop: '8px' }}
              onClick={() => navigate('/queue')}
            >
              +{items.length - 15} more → View in Queue
            </Text>
          )}
        </div>
      )}
    </div>
  );
}

function CaseRow({ caseItem, onClick }: { caseItem: CaseSummary; onClick: () => void }) {
  const urgencyColor =
    caseItem.deadline.daysRemaining <= 1
      ? chartColors.danger
      : caseItem.deadline.daysRemaining <= 3
        ? chartColors.warning
        : tokens.colorNeutralForeground3;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 10px',
        borderRadius: '6px',
        cursor: 'pointer',
        marginBottom: '4px',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = tokens.colorNeutralBackground1Hover)}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div>
        <Text size={200} weight="semibold">{caseItem.merchantName ?? 'Unknown'}</Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, marginLeft: '8px' }}>
          {caseItem.reasonCode}
        </Text>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Text size={200}>${caseItem.transactionAmount?.toFixed(2) ?? '—'}</Text>
        <span style={{ fontSize: '11px', fontWeight: 600, color: urgencyColor }}>{caseItem.deadline.daysRemaining}d</span>
      </div>
    </div>
  );
}
