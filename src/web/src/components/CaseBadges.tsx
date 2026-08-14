import { Badge } from '@fluentui/react-components';
import type { CaseStatus, CompletenessLevel, ImpactLevel, RiskLevel } from '../types/case';

/** Risk level badge */
export function RiskBadge({ level }: { level: RiskLevel }) {
  const color =
    level === 'critical' ? 'danger' :
    level === 'high'     ? 'severe' :
    level === 'medium'   ? 'warning' :
                           'success';
  return (
    <Badge color={color} appearance="tint" size="medium">
      {level.toUpperCase()}
    </Badge>
  );
}

/** Case status badge */
export function StatusBadge({ status }: { status: CaseStatus }) {
  const color =
    status === 'approved'            ? 'success' :
    status === 'denied'              ? 'danger'  :
    status === 'escalated'           ? 'severe'  :
    status === 'expired'             ? 'danger'  :
    status === 'closed'              ? 'subtle'  :
    status === 'pending_review'      ? 'brand'   :
    status === 'evidence_gathering'  ? 'warning' :
    status === 'ai_drafting'         ? 'warning' :
                                       'informative';
  const label =
    status === 'closed' ? 'Closed' :
    status.replace(/_/g, ' ');
  return (
    <Badge color={color} appearance="tint" size="medium">
      {label}
    </Badge>
  );
}

/** Evidence completeness badge */
export function CompletenessBadge({ level }: { level: CompletenessLevel }) {
  const color =
    level === 'complete' ? 'success' :
    level === 'partial'  ? 'warning' :
                           'danger';
  return (
    <Badge color={color} appearance="tint" size="small">
      {level}
    </Badge>
  );
}

/** Evidence gap impact badge */
export function ImpactBadge({ level }: { level: ImpactLevel }) {
  const color =
    level === 'critical' ? 'danger'  :
    level === 'high'     ? 'severe'  :
    level === 'medium'   ? 'warning' :
                           'informative';
  return (
    <Badge color={color} appearance="filled" size="small">
      {level.toUpperCase()}
    </Badge>
  );
}
