import {
  Checkbox,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  tokens,
} from '@fluentui/react-components';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CaseStatus } from '../types/case';
import type { CaseSummary } from '../types/case';
import { getEffectiveCaseStatus, isActive, isClosed, isNeedsReview, isOpen } from '../utils/queueStatus';
import { DeadlineCountdown } from './DeadlineCountdown';
import { RiskBadge, StatusBadge } from './CaseBadges';

type SortKey = 'caseId' | 'merchant' | 'description' | 'network' | 'amount' | 'reasonCode' | 'winProbability' | 'riskLevel' | 'status' | 'lastActivity' | 'deadline';
type SortDir = 'asc' | 'desc';

const RISK_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function sortCases(cases: CaseSummary[], key: SortKey, dir: SortDir): CaseSummary[] {
  const sorted = [...cases].sort((a, b) => {
    let cmp = 0;
    switch (key) {
      case 'caseId':
        cmp = a.caseId.localeCompare(b.caseId);
        break;
      case 'merchant':
        cmp = (a.merchantName ?? '').localeCompare(b.merchantName ?? '');
        break;
      case 'description':
        cmp = (a.caseDescription ?? '').localeCompare(b.caseDescription ?? '');
        break;
      case 'network':
        cmp = (a.cardNetwork ?? '').localeCompare(b.cardNetwork ?? '');
        break;
      case 'amount':
        cmp = (a.transactionAmount ?? 0) - (b.transactionAmount ?? 0);
        break;
      case 'reasonCode':
        cmp = a.reasonCode.localeCompare(b.reasonCode);
        break;
      case 'winProbability':
        cmp = (a.winProbability ?? -1) - (b.winProbability ?? -1);
        break;
      case 'riskLevel':
        cmp = (RISK_ORDER[a.riskLevel ?? ''] ?? 99) - (RISK_ORDER[b.riskLevel ?? ''] ?? 99);
        break;
      case 'status':
        cmp = a.status.localeCompare(b.status);
        break;
      case 'lastActivity': {
        const ta = new Date(a.lastActivityAt ?? a.updatedAt ?? 0).getTime();
        const tb = new Date(b.lastActivityAt ?? b.updatedAt ?? 0).getTime();
        cmp = ta - tb;
        break;
      }
      case 'deadline':
        cmp = (a.deadline.daysRemaining ?? 999) - (b.deadline.daysRemaining ?? 999);
        break;
    }
    return dir === 'asc' ? cmp : -cmp;
  });
  return sorted;
}

interface CaseTableProps {
  cases: CaseSummary[];
  selectable?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
}

function toRelativeTime(iso?: string): string {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const deltaMs = Date.now() - t;
  const minutes = Math.max(0, Math.round(deltaMs / 60000));
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function activityLabel(activityType?: string): string {
  switch ((activityType || '').toLowerCase()) {
    case 'document_uploaded':
      return 'Customer/Analyst document uploaded';
    case 'customer_response':
      return 'Customer responded';
    case 'analyst_note':
      return 'Analyst note added';
    case 'status_change':
    case 'status_changed':
      return 'Case status updated';
    case 'case_closed_artifact_created':
      return 'Decision artifact created';
    case 'case_created':
      return 'Dispute submitted';
    default:
      return activityType ? activityType.replace(/_/g, ' ') : 'Case updated';
  }
}

function formatStatusLabel(status: CaseStatus): string {
  return status.replace(/_/g, ' ');
}

function getQueueContext(c: CaseSummary, effectiveStatus: CaseStatus): string {
  if (isClosed(c)) {
    return effectiveStatus === 'closed' ? 'Closed' : `Closed - ${formatStatusLabel(effectiveStatus)}`;
  }

  if (isNeedsReview(c)) {
    return isOpen(c) ? 'Needs Review · Open' : 'Needs Review';
  }

  if (isActive(c)) {
    return isOpen(c) ? 'Active · Open' : 'Active';
  }

  if (isOpen(c)) {
    return 'Open';
  }

  return 'Queue status unavailable';
}

const DEFAULT_COL_WIDTHS: Record<string, number> = {
  caseId: 155,
  merchant: 130,
  description: 250,
  network: 85,
  amount: 85,
  reasonCode: 135,
  winProbability: 72,
  riskLevel: 90,
  status: 145,
  lastActivity: 170,
  deadline: 95,
};

function ResizeHandle({ colKey, setColWidths }: { colKey: string; setColWidths: React.Dispatch<React.SetStateAction<Record<string, number>>> }) {
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    let currentWidth = 0;
    setColWidths((prev) => { currentWidth = prev[colKey] ?? DEFAULT_COL_WIDTHS[colKey] ?? 100; return prev; });
    const onMouseMove = (ev: MouseEvent) => {
      const newWidth = Math.max(40, currentWidth + ev.clientX - startX);
      setColWidths((prev) => ({ ...prev, [colKey]: newWidth }));
    };
    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };
  return (
    <div
      onMouseDown={handleMouseDown}
      title="Drag to resize column"
      style={{
        position: 'absolute', right: -4, top: '15%', bottom: '15%',
        width: 8, cursor: 'col-resize', userSelect: 'none', zIndex: 3,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div style={{ width: 3, height: '100%', background: '#999', borderRadius: 2 }} />
    </div>
  );
}

export function CaseTable({ cases, selectable, selectedIds, onSelectionChange }: CaseTableProps) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>('deadline');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [colWidths, setColWidths] = useState<Record<string, number>>(DEFAULT_COL_WIDTHS);

  const cellBorderStyle = `1px solid ${tokens.colorNeutralStroke2}`;
  const truncStyle: React.CSSProperties = {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    display: 'block',
  };
  const cw = (key: string) => ({ width: colWidths[key] ?? DEFAULT_COL_WIDTHS[key] ?? 100 });
  const headerCellStyle = {
    border: cellBorderStyle,
    backgroundColor: tokens.colorNeutralBackground4,
    fontWeight: 700,
    color: tokens.colorNeutralForeground1,
    letterSpacing: '0.01em' as const,
  };

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return <span style={{ opacity: 0.3, marginLeft: 4, fontSize: 10 }}>↕</span>;
    return <span style={{ marginLeft: 4, fontSize: 10 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>;
  }

  function sortableHeader(key: SortKey, label: string) {
    return (
      <TableHeaderCell
        style={{ ...headerCellStyle, ...cw(key), position: 'relative', cursor: 'pointer', userSelect: 'none', overflow: 'visible', whiteSpace: 'normal', wordBreak: 'break-word', lineHeight: 1.2, paddingRight: 14 }}
        onClick={() => handleSort(key)}
        data-testid={`sort-col-${key}`}
      >
        {label}{sortIndicator(key)}
        <ResizeHandle colKey={key} setColWidths={setColWidths} />
      </TableHeaderCell>
    );
  }

  const allSelected = cases.length > 0 && cases.every((c) => selectedIds?.has(c.caseId));
  const someSelected = cases.some((c) => selectedIds?.has(c.caseId)) && !allSelected;

  function handleSelectAll() {
    if (!onSelectionChange) return;
    if (allSelected) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(cases.map((c) => c.caseId)));
    }
  }

  function handleSelectOne(caseId: string) {
    if (!onSelectionChange || !selectedIds) return;
    const next = new Set(selectedIds);
    if (next.has(caseId)) {
      next.delete(caseId);
    } else {
      next.add(caseId);
    }
    onSelectionChange(next);
  }

  const displayCases = sortCases(cases, sortKey, sortDir);
  const totalWidth = (selectable ? 40 : 0) + Object.keys(DEFAULT_COL_WIDTHS).reduce((sum, k) => sum + (colWidths[k] ?? DEFAULT_COL_WIDTHS[k] ?? 100), 0);

  if (cases.length === 0) {
    return <Text style={{ padding: '24px', display: 'block', color: '#666' }}>No cases in queue.</Text>;
  }

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
    <Table arial-label="Case queue" style={{ tableLayout: 'fixed', width: totalWidth, borderCollapse: 'collapse' }}>
      <TableHeader>
        <TableRow>
          {selectable && (
            <TableHeaderCell style={{ width: 40, ...headerCellStyle }}>
              <Checkbox
                checked={allSelected ? true : someSelected ? 'mixed' : false}
                onChange={handleSelectAll}
                aria-label="Select all cases"
              />
            </TableHeaderCell>
          )}
          {sortableHeader('caseId', 'Case ID')}
          {sortableHeader('merchant', 'Merchant')}
          {sortableHeader('description', 'Description')}
          {sortableHeader('network', 'Network')}
          {sortableHeader('amount', 'Amount')}
          {sortableHeader('reasonCode', 'Reason Code')}
          {sortableHeader('winProbability', 'Win Prob')}
          {sortableHeader('riskLevel', 'Risk')}
          {sortableHeader('status', 'Status')}
          {sortableHeader('lastActivity', 'Recent Activity')}
          {sortableHeader('deadline', 'Deadline')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {displayCases.map((c, index) => {
          const isAtRisk = c.riskLevel === 'critical';
          const effectiveStatus = getEffectiveCaseStatus(c);
          const altBg = index % 2 === 1 ? tokens.colorNeutralBackground2 : undefined;
          const isChecked = selectedIds?.has(c.caseId) ?? false;
          return (
            <TableRow
              key={c.caseId}
              data-testid="case-row"
              onClick={() => void navigate(`/cases/${c.caseId}`)}
              style={{
                cursor: 'pointer',
                backgroundColor: isAtRisk ? tokens.colorStatusDangerBackground1 : altBg,
              }}
            >
              {selectable && (
                <TableCell style={{ width: 40, border: cellBorderStyle }}>
                  <Checkbox
                    checked={isChecked}
                    onChange={(e) => {
                      e.stopPropagation();
                      handleSelectOne(c.caseId);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    aria-label={`Select case ${c.merchantName ?? c.caseId}`}
                  />
                </TableCell>
              )}
              <TableCell style={{ border: cellBorderStyle, overflow: 'hidden' }}>
                <Text font="monospace" size={200} title={c.caseId} style={truncStyle}>
                  {c.caseId}
                </Text>
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, overflow: 'hidden' }}>
                <Text weight="regular" title={c.merchantName ?? ''} style={truncStyle}>
                  {c.merchantName ?? '—'}
                </Text>
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, overflow: 'hidden' }}>
                <Text size={200} title={c.caseDescription ?? ''} style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: '1.35' }}>
                  {c.caseDescription ?? '—'}
                </Text>
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, overflow: 'hidden' }}>
                <span style={truncStyle}>{c.cardNetwork?.toUpperCase() ?? '—'}</span>
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, overflow: 'hidden' }}>
                <span style={truncStyle}>
                  {c.transactionAmount !== undefined ? `$${c.transactionAmount.toFixed(2)}` : '—'}
                </span>
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, overflow: 'hidden' }}>
                <Text title={`${c.reasonCode}${c.reasonCodeLabel ? ' — ' + c.reasonCodeLabel : ''}`} style={truncStyle}>{c.reasonCode}</Text>
                {c.reasonCodeLabel && (
                  <Text size={200} style={{ color: '#666', ...truncStyle }}>
                    {c.reasonCodeLabel}
                  </Text>
                )}
              </TableCell>
              <TableCell style={{ border: cellBorderStyle }}>
                <span style={truncStyle}>
                  {c.winProbability !== undefined ? `${Math.round(c.winProbability * 100)}%` : '—'}
                </span>
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, paddingTop: 4, paddingBottom: 4 }}>
                {c.riskLevel ? <RiskBadge level={c.riskLevel} /> : '—'}
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, paddingTop: 4, paddingBottom: 4 }}>
                <StatusBadge status={effectiveStatus} />
                <Text size={100} style={{ color: tokens.colorNeutralForeground3, ...truncStyle, marginTop: '2px' }}>
                  {getQueueContext(c, effectiveStatus)}
                </Text>
              </TableCell>
              <TableCell style={{ border: cellBorderStyle, overflow: 'hidden' }}>
                <Text size={200} weight="semibold" style={truncStyle} title={activityLabel(c.lastActivityType)}>
                  {activityLabel(c.lastActivityType)}
                </Text>
                <Text size={100} style={{ color: tokens.colorNeutralForeground3, ...truncStyle }}>
                  {toRelativeTime(c.lastActivityAt ?? c.updatedAt)}
                  {c.lastActivityActor ? ` · ${c.lastActivityActor}` : ''}
                </Text>
                {c.lastActivityDetail && (
                  <Text size={100} title={c.lastActivityDetail} style={{ color: tokens.colorNeutralForeground3, ...truncStyle }}>
                    {c.lastActivityDetail}
                  </Text>
                )}
              </TableCell>
              <TableCell style={{ border: cellBorderStyle }}>
                <DeadlineCountdown
                  daysRemaining={c.deadline.daysRemaining}
                  dueDate={c.deadline.dueDate}
                />
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
    </div>
  );
}
