import { Text, tokens } from '@fluentui/react-components';
import { useState } from 'react';
import type { TimelineCategory, TimelineEvent, TimelineEventType } from '../types/case';

interface TimelinePanelProps {
  events: TimelineEvent[];
  loading?: boolean;
}

// ── Category mapping ──────────────────────────────────────────────────────────

const CATEGORY_MAP: Record<TimelineEventType, TimelineCategory> = {
  authorization: 'transaction',
  clearing: 'transaction',
  settlement: 'transaction',
  refund: 'transaction',
  chargeback: 'transaction',
  representment: 'transaction',
  arbitration: 'transaction',
  customer_login: 'customer_activity',
  device_change: 'customer_activity',
  mfa_event: 'customer_activity',
  geolocation: 'customer_activity',
  previous_purchase: 'customer_activity',
  velocity_alert: 'fraud_signals',
  device_reputation: 'fraud_signals',
  ip_reputation: 'fraud_signals',
  high_risk_indicator: 'fraud_signals',
  friendly_fraud_indicator: 'fraud_signals',
  case_created: 'case_activity',
  evidence_retrieved: 'case_activity',
  evidence_gap_detected: 'case_activity',
  score_generated: 'case_activity',
  ai_draft_generated: 'case_activity',
  status_changed: 'case_activity',
  status_change: 'case_activity',
  analyst_assigned: 'case_activity',
  analyst_action: 'case_activity',
  escalated: 'case_activity',
  deadline_warning: 'case_activity',
  document_uploaded: 'case_activity',
  comment_added: 'case_activity',
  analyst_note: 'case_activity',
  ai_recommendation_response: 'case_activity',
  evidence_gap_requested: 'case_activity',
  customer_response: 'case_activity',
  case_closed_artifact_created: 'case_activity',
  customer_response_requested: 'case_activity',
  customer_response_received: 'case_activity',
};

const CATEGORY_CONFIG: Record<TimelineCategory, { label: string; icon: string; color: string }> = {
  transaction: { label: 'Transaction Events', icon: '💳', color: tokens.colorPaletteBlueBorderActive },
  customer_activity: { label: 'Customer Activity', icon: '👤', color: tokens.colorPaletteTealBorderActive },
  fraud_signals: { label: 'Fraud Signals', icon: '🚨', color: tokens.colorPaletteRedBorderActive },
  case_activity: { label: 'Case Activity', icon: '📋', color: tokens.colorPaletteGreenBorderActive },
};

const eventIcons: Record<string, string> = {
  case_created: '📋', evidence_retrieved: '📥', evidence_gap_detected: '⚠️',
  score_generated: '⚡', ai_draft_generated: '🤖', status_changed: '🔄', status_change: '🔄', analyst_assigned: '👤',
  analyst_action: '✅', ai_recommendation_response: '🧠', evidence_gap_requested: '📨', escalated: '🚨', deadline_warning: '⏰',
  document_uploaded: '📎', comment_added: '💬', customer_response: '👤', case_closed_artifact_created: '📁',
  authorization: '🔐', clearing: '📤', settlement: '💰',
  refund: '↩️', chargeback: '⚡', representment: '📨', arbitration: '⚖️',
  customer_login: '🔑', device_change: '📱', mfa_event: '🛡️',
  geolocation: '📍', previous_purchase: '🛒',
  velocity_alert: '⚡', device_reputation: '🖥️', ip_reputation: '🌐',
  high_risk_indicator: '🔴', friendly_fraud_indicator: '🟡',
};

const eventColors: Record<string, string> = {
  case_created: tokens.colorPaletteBlueBorderActive,
  evidence_retrieved: tokens.colorPaletteGreenBorderActive,
  evidence_gap_detected: tokens.colorPaletteYellowBorderActive,
  score_generated: tokens.colorPaletteMarigoldBorderActive,
  ai_draft_generated: tokens.colorPalettePurpleBorderActive,
  status_changed: tokens.colorPaletteBlueBorderActive,
  status_change: tokens.colorPaletteBlueBorderActive,
  analyst_assigned: tokens.colorPaletteTealBorderActive,
  analyst_action: tokens.colorPaletteGreenBorderActive,
  ai_recommendation_response: tokens.colorPalettePurpleBorderActive,
  evidence_gap_requested: tokens.colorPaletteBlueBorderActive,
  escalated: tokens.colorPaletteRedBorderActive,
  deadline_warning: tokens.colorPaletteRedBorderActive,
  document_uploaded: tokens.colorPaletteBlueBorderActive,
  customer_response: tokens.colorPaletteTealBorderActive,
  case_closed_artifact_created: tokens.colorPaletteGreenBorderActive,
  comment_added: tokens.colorNeutralStroke1,
  authorization: tokens.colorPaletteBlueBorderActive,
  clearing: tokens.colorPaletteBlueBorderActive,
  settlement: tokens.colorPaletteGreenBorderActive,
  refund: tokens.colorPaletteYellowBorderActive,
  chargeback: tokens.colorPaletteRedBorderActive,
  representment: tokens.colorPalettePurpleBorderActive,
  arbitration: tokens.colorPaletteRedBorderActive,
  customer_login: tokens.colorPaletteTealBorderActive,
  device_change: tokens.colorPaletteYellowBorderActive,
  mfa_event: tokens.colorPaletteGreenBorderActive,
  geolocation: tokens.colorPaletteTealBorderActive,
  previous_purchase: tokens.colorPaletteBlueBorderActive,
  velocity_alert: tokens.colorPaletteRedBorderActive,
  device_reputation: tokens.colorPaletteYellowBorderActive,
  ip_reputation: tokens.colorPaletteYellowBorderActive,
  high_risk_indicator: tokens.colorPaletteRedBorderActive,
  friendly_fraud_indicator: tokens.colorPaletteYellowBorderActive,
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const hours = Math.floor(diff / 3600_000);
  const days = Math.floor(diff / 86400_000);

  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function renderMetadata(event: TimelineEvent): React.ReactNode {
  const m = event.metadata;
  if (!m) return null;
  const pills: string[] = [];
  if (m.device) pills.push(`Device: ${m.device}`);
  if (m.location) pills.push(`📍 ${m.location}`);
  if (m.ip) pills.push(`IP: ${m.ip}`);
  if (m.score !== undefined) pills.push(`Score: ${m.score}`);
  if (m.risk) pills.push(`Risk: ${m.risk}`);
  if (m.amount) pills.push(`$${m.amount}`);
  if (pills.length === 0) return null;
  return (
    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
      {pills.map((pill) => (
        <span key={pill} style={{ fontSize: '10px', background: tokens.colorNeutralBackground3, padding: '1px 6px', borderRadius: '3px', color: tokens.colorNeutralForeground3 }}>
          {pill}
        </span>
      ))}
    </div>
  );
}

// ── Section component ─────────────────────────────────────────────────────────

function TimelineSection({ category, events }: { category: TimelineCategory; events: TimelineEvent[] }) {
  const [expanded, setExpanded] = useState(true);
  const config = CATEGORY_CONFIG[category];
  const sorted = [...events].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  if (sorted.length === 0) return null;

  return (
    <div style={{ marginBottom: '16px' }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', padding: '6px 0', userSelect: 'none' }}
      >
        <span style={{ fontSize: '10px', transition: 'transform 150ms', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
        <span>{config.icon}</span>
        <Text weight="semibold" size={200} style={{ color: config.color }}>{config.label}</Text>
        <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>({sorted.length})</Text>
      </div>

      {expanded && (
        <div style={{ position: 'relative', paddingLeft: '24px', marginTop: '4px' }}>
          {sorted.length > 1 && (
            <div style={{ position: 'absolute', left: '9px', top: '8px', bottom: '8px', width: '2px', background: tokens.colorNeutralStroke2 }} />
          )}
          {sorted.map((event) => {
            const color = eventColors[event.eventType] ?? tokens.colorNeutralStroke1;
            const icon = eventIcons[event.eventType] ?? '•';
            return (
              <div key={event.eventId} style={{ position: 'relative', marginBottom: '12px', paddingBottom: '2px' }}>
                <div style={{ position: 'absolute', left: '-20px', top: '2px', width: '12px', height: '12px', borderRadius: '50%', background: color }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text size={200} style={{ display: 'block' }}>
                      <span style={{ marginRight: '4px' }}>{icon}</span>
                      {event.description}
                    </Text>
                    {event.actor && event.actor !== 'system' && (
                      <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>by {event.actor}</Text>
                    )}
                    {renderMetadata(event)}
                  </div>
                  <Text size={100} style={{ color: tokens.colorNeutralForeground3, whiteSpace: 'nowrap', flexShrink: 0 }}>
                    {formatTimestamp(event.timestamp)}
                  </Text>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const SECTION_ORDER: TimelineCategory[] = ['transaction', 'customer_activity', 'fraud_signals', 'case_activity'];

export function TimelinePanel({ events, loading }: TimelinePanelProps) {
  const grouped = events.reduce<Record<TimelineCategory, TimelineEvent[]>>(
    (acc, event) => {
      const cat = CATEGORY_MAP[event.eventType] ?? 'case_activity';
      acc[cat].push(event);
      return acc;
    },
    { transaction: [], customer_activity: [], fraud_signals: [], case_activity: [] }
  );

  return (
    <div>
      <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: '12px' }}>
        Complete Timeline
      </Text>

      {loading && (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>Loading timeline…</Text>
      )}

      {!loading && events.length === 0 && (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>No activity recorded yet.</Text>
      )}

      {!loading && SECTION_ORDER.map((category) => (
        <TimelineSection key={category} category={category} events={grouped[category]} />
      ))}
    </div>
  );
}
