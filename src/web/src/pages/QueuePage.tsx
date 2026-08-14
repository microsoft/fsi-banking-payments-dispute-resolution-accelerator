import {
  Badge,
  Button,
  Divider,
  Input,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  Text,
  tokens,
} from '@fluentui/react-components';
import {
  SearchRegular,
  DismissRegular,
  CheckmarkCircleRegular,
  PersonAddRegular,
  ArrowExportRegular,
} from '@fluentui/react-icons';
import { useEffect, useMemo, useState } from 'react';
import { getCases, postAction } from '../api/cases';
import { AnalystHeader } from '../components/AnalystHeader';
import { CaseTable } from '../components/CaseTable';
import { KpiCards, type QueueKpiKey } from '../components/KpiCards';
import { useNotifications } from '../components/NotificationProvider';
import { mockAnalyst } from '../mocks/analyst';
import type { CaseSummary } from '../types/case';
import {
  filterByTab,
  isActive,
  isClosed,
  isNeedsReview,
  isOpen,
  type QueueTab,
} from '../utils/queueStatus';

export function QueuePage() {
  const { notifyWarning } = useNotifications();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState<QueueTab>('needs-review');
  const [networkFilter, setNetworkFilter] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);
  const [selectedKpi, setSelectedKpi] = useState<QueueKpiKey | null>(null);
  const [showCustomerUpdatesOnly, setShowCustomerUpdatesOnly] = useState(false);
  const [quickFilter, setQuickFilter] = useState<'urgent' | null>(null);

  const CUSTOMER_ACTIVITY_TYPES = new Set(['customer_response', 'document_uploaded']);
  const LAST_SEEN_CUSTOMER_UPDATE_KEY = 'queue:lastSeenCustomerActivityAt';

  const toMillis = (value?: string) => {
    if (!value) return 0;
    const ms = new Date(value).getTime();
    return Number.isNaN(ms) ? 0 : ms;
  };

  const isCustomerActivityCase = (c: CaseSummary) => {
    const type = (c.lastActivityType || '').toLowerCase();
    const actor = (c.lastActivityActor || '').toLowerCase();
    return CUSTOMER_ACTIVITY_TYPES.has(type) && (type === 'customer_response' || actor.includes('customer'));
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getCases()
      .then((data) => {
        if (!cancelled) {
          setCases(data);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load cases.');
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Apply network filter first, then search, then tab filter
  const networkFiltered = networkFilter
    ? cases.filter((c) => c.cardNetwork?.toLowerCase() === networkFilter.toLowerCase())
    : cases;

  const searchFiltered = searchQuery.trim()
    ? networkFiltered.filter((c) => {
        const q = searchQuery.toLowerCase();
        return (
          c.caseId.toLowerCase().includes(q) ||
          (c.merchantName?.toLowerCase().includes(q) ?? false) ||
          (c.caseDescription?.toLowerCase().includes(q) ?? false) ||
          c.reasonCode.toLowerCase().includes(q) ||
          (c.reasonCodeLabel?.toLowerCase().includes(q) ?? false) ||
          (c.assignedAnalystName?.toLowerCase().includes(q) ?? false)
        );
      })
    : networkFiltered;

  // When searching, show results across all tabs; otherwise filter by selected tab.
  const filteredCases = searchQuery.trim()
    ? searchFiltered
    : filterByTab(searchFiltered, selectedTab);

  const customerUpdateCases = useMemo(() => {
    return [...cases]
      .filter((c) => !isClosed(c) && isCustomerActivityCase(c))
      .sort((a, b) => toMillis(b.lastActivityAt ?? b.updatedAt) - toMillis(a.lastActivityAt ?? a.updatedAt));
  }, [cases]);

  const customerUpdateCaseIds = useMemo(
    () => new Set(customerUpdateCases.map((c) => c.caseId)),
    [customerUpdateCases]
  );

  const selectQueueTab = (tab: QueueTab) => {
    setSelectedTab(tab);
    setShowCustomerUpdatesOnly(false);
    setQuickFilter(null);
  };

  const selectUrgentFilter = () => {
    setSelectedTab('open');
    setShowCustomerUpdatesOnly(false);
    setQuickFilter('urgent');
  };

  const toggleCustomerUpdatesOnly = () => {
    setShowCustomerUpdatesOnly((prev) => {
      const next = !prev;
      // Enabling this mode jumps to Open for clearer triage semantics.
      if (next) {
        setSelectedTab('open');
      }
      return next;
    });
  };

  const customerFilteredCases = showCustomerUpdatesOnly
    ? searchFiltered.filter((c) => customerUpdateCaseIds.has(c.caseId))
    : filteredCases;

  const visibleCases = quickFilter === 'urgent'
    ? customerFilteredCases.filter((c) => !isClosed(c) && c.deadline.daysRemaining <= 3)
    : customerFilteredCases;

  const sortedFilteredCases = useMemo(() => {
    return [...visibleCases].sort((a, b) => {
      const aTs = toMillis(a.lastActivityAt ?? a.updatedAt ?? a.createdAt);
      const bTs = toMillis(b.lastActivityAt ?? b.updatedAt ?? b.createdAt);
      return bTs - aTs;
    });
  }, [visibleCases]);

  useEffect(() => {
    if (customerUpdateCases.length === 0) return;
    const newest = customerUpdateCases[0];
    const newestTs = toMillis(newest.lastActivityAt ?? newest.updatedAt);
    if (!newestTs) return;

    const lastSeenTs = toMillis(localStorage.getItem(LAST_SEEN_CUSTOMER_UPDATE_KEY) ?? undefined);
    if (newestTs > lastSeenTs) {
      notifyWarning(
        'Customer updates need review',
        `${customerUpdateCases.length} dispute(s) have new customer activity. Most recent: ${newest.merchantName ?? newest.caseId}.`
      );
      localStorage.setItem(LAST_SEEN_CUSTOMER_UPDATE_KEY, new Date(newestTs).toISOString());
    }
  }, [customerUpdateCases, notifyWarning]);

  const counts = {
    open: searchFiltered.filter(isOpen).length,
    active: searchFiltered.filter(isActive).length,
    'needs-review': searchFiltered.filter(isNeedsReview).length,
    closed: searchFiltered.filter(isClosed).length,
  };

  const urgentCount = searchFiltered.filter((c) => !isClosed(c) && c.deadline.daysRemaining <= 3).length;
  const exposure = searchFiltered
    .filter((c) => !isClosed(c))
    .reduce((sum, c) => sum + (c.transactionAmount ?? 0), 0);

  const mostRecentCustomerUpdate = customerUpdateCases[0];

  const summaryCards = [
    {
      key: 'active',
      label: 'Active',
      value: counts.active,
      accent: '#1778d4',
      onClick: () => selectQueueTab('active'),
    },
    {
      key: 'urgent',
      label: 'Urgent',
      value: urgentCount,
      accent: '#d13438',
      onClick: selectUrgentFilter,
    },
    {
      key: 'exposure',
      label: 'Exposure',
      value: `$${Math.round(exposure).toLocaleString()}`,
      accent: '#8a5d00',
      onClick: () => selectQueueTab('open'),
    },
    {
      key: 'needs-review',
      label: 'Need Review',
      value: counts['needs-review'],
      accent: '#9c27b0',
      onClick: () => selectQueueTab('needs-review'),
    },
  ];

  // Preserve existing KPI-card drill-down interaction.
  const kpiDrillCases = useMemo(() => {
    if (!selectedKpi) return [];
    switch (selectedKpi) {
      case 'open':
        return searchFiltered.filter(isOpen);
      case 'active':
        return searchFiltered.filter(isActive);
      case 'needs-review':
        return searchFiltered.filter(isNeedsReview);
      case 'decision-rate':
        return searchFiltered.filter(isClosed);
      case 'exposure':
        return searchFiltered.filter((c) => !isClosed(c));
      case 'urgent':
        return searchFiltered.filter((c) => !isClosed(c) && c.deadline.daysRemaining <= 3);
    }
  }, [selectedKpi, searchFiltered]);

  const kpiDrillTitle: Record<QueueKpiKey, string> = {
    open: 'Open Cases - All non-closed cases',
    active: 'Active Cases - Intake, evidence gathering, or drafting',
    'needs-review': 'Needs Review - Pending review or escalated',
    'decision-rate': 'Approval/Denial Breakdown - Closed decisions',
    exposure: 'Total Exposure - All open disputed amounts',
    urgent: 'Urgent Cases - Deadline <= 3 days',
  };

  function handleKpiClick(key: QueueKpiKey) {
    // Keep KPI interactions and queue controls in sync so every triage control
    // updates the primary case table, not just the KPI drill-down panel.
    if (key === 'open' || key === 'active' || key === 'needs-review') {
      selectQueueTab(key);
    } else if (key === 'urgent') {
      selectUrgentFilter();
    } else if (key === 'decision-rate') {
      selectQueueTab('closed');
    } else if (key === 'exposure') {
      selectQueueTab('open');
    }
    setSelectedKpi((prev) => (prev === key ? null : key));
  }

  // Clear selection when switching tabs or filters
  useEffect(() => {
    setSelectedIds(new Set());
  }, [selectedTab, networkFilter, searchQuery, showCustomerUpdatesOnly, quickFilter]);

  async function handleBatchApprove() {
    setBatchLoading(true);
    const ids = [...selectedIds];
    await Promise.all(
      ids.map((id) =>
        postAction(id, 'approve', { analystId: mockAnalyst.analystId, comment: 'Batch approved' })
      )
    );
    const updated = await getCases();
    setCases(updated);
    setSelectedIds(new Set());
    setBatchLoading(false);
  }

  async function handleBatchAssign() {
    setBatchLoading(true);
    const ids = [...selectedIds];
    await Promise.all(
      ids.map((id) =>
        postAction(id, 'reroute', { analystId: mockAnalyst.analystId, comment: 'Batch assigned' })
      )
    );
    const updated = await getCases();
    setCases(updated);
    setSelectedIds(new Set());
    setBatchLoading(false);
  }

  function handleBatchExport() {
    const selected = sortedFilteredCases.filter((c) => selectedIds.has(c.caseId));
    const csv = [
      'Case ID,Merchant,Description,Network,Amount,Reason Code,Status,Risk,Deadline',
      ...selected.map(
        (c) =>
          `${c.caseId},${c.merchantName ?? ''},${(c.caseDescription ?? '').split(',').join(';')},${c.cardNetwork ?? ''},${c.transactionAmount ?? ''},${c.reasonCode},${c.status},${c.riskLevel ?? ''},${c.deadline.dueDate}`
      ),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dispute-cases-export-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={{ fontFamily: 'var(--fontFamilyBase)' }}>
      <AnalystHeader analyst={mockAnalyst} activeNetwork={networkFilter} onNetworkFilter={setNetworkFilter} />

      <div
        style={{
          maxWidth: '1360px',
          margin: '0 auto',
          padding: '14px 16px 24px',
        }}
      >
        {!loading && !error && (
          <div style={{ marginBottom: '12px' }}>
            <KpiCards cases={searchFiltered} selectedKpi={selectedKpi} onKpiClick={handleKpiClick} />
          </div>
        )}

        {selectedKpi && kpiDrillCases.length > 0 && (
          <div
            style={{
              marginBottom: '14px',
              border: `1px solid ${tokens.colorNeutralStroke2}`,
              borderRadius: '10px',
              background: tokens.colorNeutralBackground1,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
                background: tokens.colorNeutralBackground3,
              }}
            >
              <Text weight="semibold">{kpiDrillTitle[selectedKpi]} ({kpiDrillCases.length})</Text>
              <Button
                appearance="subtle"
                icon={<DismissRegular />}
                size="small"
                onClick={() => setSelectedKpi(null)}
                aria-label="Close drill-down"
              />
            </div>
            <div style={{ maxHeight: '320px', overflow: 'auto' }}>
              <CaseTable cases={kpiDrillCases} />
            </div>
          </div>
        )}

        {!loading && !error && (
          <div
            style={{
              marginBottom: '12px',
              border: `1px solid ${tokens.colorNeutralStroke2}`,
              borderRadius: '14px',
              background: tokens.colorNeutralBackground1,
              padding: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                <Text size={500} weight="semibold">All Cases</Text>
                <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                  Analyst queue, prioritization, and customer response triage.
                </Text>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <Badge appearance="filled" color={showCustomerUpdatesOnly ? 'warning' : 'subtle'}>
                  {showCustomerUpdatesOnly ? 'Customer updates focus' : 'Full queue view'}
                </Badge>
                <Badge appearance="outline" color="informative">
                  {sortedFilteredCases.length} visible case{sortedFilteredCases.length === 1 ? '' : 's'}
                </Badge>
              </div>
            </div>

            <Divider style={{ margin: '10px 0 12px' }} />

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '300px minmax(0, 1fr)',
                gap: '12px',
                alignItems: 'start',
              }}
            >
              <div style={{ display: 'grid', gap: '10px' }}>
                <div
                  style={{
                    padding: '10px',
                    border: `1px solid ${tokens.colorNeutralStroke2}`,
                    borderRadius: '12px',
                    background: `linear-gradient(180deg, ${tokens.colorNeutralBackground2}, ${tokens.colorNeutralBackground1})`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>
                    <Text size={300} weight="semibold">Operations Center</Text>
                    <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                      Smart triage for today.
                    </Text>
                  </div>

                  <div
                    style={{
                      marginTop: '8px',
                      display: 'grid',
                      gap: '8px',
                      gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                    }}
                  >
                    {summaryCards.map((card) => (
                      <button
                        key={card.key}
                        type="button"
                        data-testid={`summary-card-${card.key}`}
                        onClick={card.onClick}
                        style={{
                          textAlign: 'left',
                          border: `1px solid ${tokens.colorNeutralStroke2}`,
                          borderTop: `3px solid ${card.accent}`,
                          borderRadius: '10px',
                          background: card.key === 'urgent' && quickFilter === 'urgent'
                            ? tokens.colorBrandBackground2
                            : tokens.colorNeutralBackground1,
                          padding: '8px 10px',
                          cursor: 'pointer',
                        }}
                      >
                        <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>
                          {card.label}
                        </Text>
                        <Text size={400} weight="semibold">
                          {card.value}
                        </Text>
                      </button>
                    ))}
                  </div>

                  <div
                    style={{
                      marginTop: '8px',
                      paddingTop: '8px',
                      borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
                    }}
                  >
                    <Text size={200} weight="semibold">Recent customer activity</Text>
                    <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: 4 }}>
                      {mostRecentCustomerUpdate
                        ? `${mostRecentCustomerUpdate.merchantName ?? mostRecentCustomerUpdate.caseId} (${(mostRecentCustomerUpdate.lastActivityType ?? 'update').replace(/_/g, ' ')})`
                        : 'No recent customer activity awaiting response.'}
                    </Text>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                      <Button
                        size="small"
                        appearance={showCustomerUpdatesOnly ? 'primary' : 'secondary'}
                        onClick={toggleCustomerUpdatesOnly}
                      >
                        {showCustomerUpdatesOnly ? 'Showing customer updates only' : 'Filter to customer updates'}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <Text size={300} weight="semibold">Queue Controls</Text>
                  <Input
                    placeholder="Search merchant, reason code, case ID, or analyst"
                    value={searchQuery}
                    onChange={(_, data) => setSearchQuery(data.value)}
                    contentBefore={<SearchRegular />}
                    contentAfter={
                      searchQuery ? (
                        <DismissRegular
                          style={{ cursor: 'pointer' }}
                          onClick={() => setSearchQuery('')}
                        />
                      ) : undefined
                    }
                    style={{ width: '100%', maxWidth: '460px' }}
                  />
                </div>

                <Divider style={{ margin: '10px 0' }} />

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {([
                      ['open', 'Open', counts.open, 'informative'],
                      ['active', 'Active', counts.active, 'success'],
                      ['needs-review', 'Needs Review', counts['needs-review'], 'warning'],
                      ['closed', 'Closed', counts.closed, 'subtle'],
                    ] as const).map(([value, label, count, badgeColor]) => {
                      const selected = selectedTab === value && quickFilter === null;
                      return (
                        <button
                          key={value}
                          type="button"
                          data-testid={`queue-tab-${value}`}
                          aria-label={`Queue tab ${label}`}
                          onClick={() => selectQueueTab(value)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 8,
                            padding: '8px 10px',
                            borderRadius: '999px',
                            border: `1px solid ${selected ? tokens.colorBrandStroke1 : tokens.colorNeutralStroke2}`,
                            background: selected ? tokens.colorBrandBackground2 : tokens.colorNeutralBackground1,
                            color: tokens.colorNeutralForeground1,
                            cursor: 'pointer',
                            fontWeight: selected ? 700 : 500,
                          }}
                        >
                          <span>{label}</span>
                          <Badge appearance="filled" color={badgeColor} size="small">
                            {count}
                          </Badge>
                        </button>
                      );
                    })}
                  </div>

                  <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                    Open = non-closed, Active = intake/evidence/drafting, Needs Review = pending review/escalated.
                  </Text>
                </div>
              </div>
            </div>
          </div>
        )}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '48px' }}>
            <Spinner size="large" label="Loading cases..." />
          </div>
        )}

        {error && (
          <MessageBar intent="error">
            <MessageBarBody>
              <MessageBarTitle>Error loading cases</MessageBarTitle>
              {error}
            </MessageBarBody>
          </MessageBar>
        )}

        {!loading && !error && (
          <div
            style={{
              background: tokens.colorNeutralBackground1,
              border: `1px solid ${tokens.colorNeutralStroke2}`,
              borderRadius: '8px',
              overflowX: 'auto',
              overflowY: 'hidden',
            }}
          >
            <CaseTable
              cases={sortedFilteredCases}
              selectable
              selectedIds={selectedIds}
              onSelectionChange={setSelectedIds}
            />
          </div>
        )}

        {selectedIds.size > 0 && (
          <div
            style={{
              position: 'fixed',
              bottom: 24,
              left: '50%',
              transform: 'translateX(-50%)',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 20px',
              background: tokens.colorNeutralBackground1,
              border: `1px solid ${tokens.colorNeutralStroke1}`,
              borderRadius: '8px',
              boxShadow: tokens.shadow16,
              zIndex: 1000,
            }}
          >
            <Text weight="semibold">
              {selectedIds.size} case{selectedIds.size !== 1 ? 's' : ''} selected
            </Text>
            <Button
              appearance="primary"
              icon={<CheckmarkCircleRegular />}
              disabled={batchLoading}
              onClick={() => void handleBatchApprove()}
            >
              Approve
            </Button>
            <Button
              appearance="secondary"
              icon={<PersonAddRegular />}
              disabled={batchLoading}
              onClick={() => void handleBatchAssign()}
            >
              Assign to Me
            </Button>
            <Button
              appearance="subtle"
              icon={<ArrowExportRegular />}
              onClick={handleBatchExport}
            >
              Export CSV
            </Button>
            <Button
              appearance="subtle"
              icon={<DismissRegular />}
              onClick={() => setSelectedIds(new Set())}
              aria-label="Clear selection"
            />
          </div>
        )}
      </div>
    </div>
  );
}
