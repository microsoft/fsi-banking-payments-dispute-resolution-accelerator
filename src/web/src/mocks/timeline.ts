import type { TimelineEvent } from '../types/case';

/**
 * Mock timeline data for local development.
 * Maps caseId → array of timeline events.
 */
export const mockTimelines: Record<string, TimelineEvent[]> = {};

// Generate timeline events for each synthetic case ID
const syntheticCaseIds = [
  '2cadeebd-4faf-586e-aefe-ade8d61b894a',
  'bd3f6fe3-ad20-5e96-b926-da3b87c18834',
  '1b496d7e-e91a-5bb8-8417-c1b15dc4e035',
  'b59f0f2e-93b8-56a5-9aa7-02710c7de3b2',
  '76aa7019-e71f-5595-b5f5-f3fb279cc0b0',
  'b91440d2-d49c-5606-8439-a7f1f4585d29',
  '23bcc2f3-90bc-58fc-9843-148e830f6092',
  'd10550c8-f345-5c76-8109-8e00c2391bed',
  '77293238-7e17-5fd3-93b6-e8ec55151a54',
  '1f60a711-3c46-5a82-bc8c-ba072291e75e',
];

function generateTimeline(caseId: string, index: number): TimelineEvent[] {
  const baseDate = new Date('2026-06-15T08:00:00Z');
  baseDate.setDate(baseDate.getDate() + index * 2);
  const t = baseDate.getTime();

  const events: TimelineEvent[] = [
    // ── Transaction Events ────────────────────────────────────────────────
    {
      eventId: `evt-${caseId}-t01`,
      disputeId: caseId,
      eventType: 'authorization',
      timestamp: new Date(t - 864000_000).toISOString(), // 10 days before case
      actor: 'system',
      description: 'Authorization approved — Visa network',
      metadata: { amount: '1,247.50', authCode: 'A8F21K', responseCode: '00' },
    },
    {
      eventId: `evt-${caseId}-t02`,
      disputeId: caseId,
      eventType: 'clearing',
      timestamp: new Date(t - 777600_000).toISOString(), // 9 days before
      actor: 'system',
      description: 'Transaction cleared through acquiring bank',
      metadata: { acquirerRef: 'ACQ-9281734' },
    },
    {
      eventId: `evt-${caseId}-t03`,
      disputeId: caseId,
      eventType: 'settlement',
      timestamp: new Date(t - 691200_000).toISOString(), // 8 days before
      actor: 'system',
      description: 'Settlement completed — funds transferred to merchant',
      metadata: { amount: '1,247.50', settlementId: 'STL-44921' },
    },
    {
      eventId: `evt-${caseId}-t04`,
      disputeId: caseId,
      eventType: 'chargeback',
      timestamp: new Date(t - 172800_000).toISOString(), // 2 days before case
      actor: 'system',
      description: 'Chargeback initiated by cardholder — Reason Code 13.1',
      metadata: { amount: '1,247.50', reasonCode: '13.1' },
    },

    // ── Customer Activity ─────────────────────────────────────────────────
    {
      eventId: `evt-${caseId}-c01`,
      disputeId: caseId,
      eventType: 'customer_login',
      timestamp: new Date(t - 950400_000).toISOString(), // 11 days before
      actor: 'system',
      description: 'Customer authenticated via mobile banking app',
      metadata: { device: 'iPhone 15 Pro', location: 'Atlanta, GA', ip: '72.14.201.xx' },
    },
    {
      eventId: `evt-${caseId}-c02`,
      disputeId: caseId,
      eventType: 'mfa_event',
      timestamp: new Date(t - 950000_000).toISOString(),
      actor: 'system',
      description: 'MFA challenge passed — SMS verification code',
      metadata: { method: 'SMS', device: 'iPhone 15 Pro' },
    },
    {
      eventId: `evt-${caseId}-c03`,
      disputeId: caseId,
      eventType: 'previous_purchase',
      timestamp: new Date(t - 2592000_000).toISOString(), // 30 days before
      actor: 'system',
      description: 'Previous purchase at same merchant — $89.99 (no dispute)',
      metadata: { amount: '89.99', merchant: 'Same Merchant' },
    },
    {
      eventId: `evt-${caseId}-c04`,
      disputeId: caseId,
      eventType: 'geolocation',
      timestamp: new Date(t - 864000_000).toISOString(),
      actor: 'system',
      description: 'Transaction location matches customer home address',
      metadata: { location: 'Atlanta, GA', matchType: 'home_address' },
    },
    {
      eventId: `evt-${caseId}-c05`,
      disputeId: caseId,
      eventType: 'device_change',
      timestamp: new Date(t - 432000_000).toISOString(), // 5 days before
      actor: 'system',
      description: 'New device detected — desktop browser (previously mobile only)',
      metadata: { device: 'Chrome/Windows', risk: 'medium' },
    },

    // ── Fraud Signals ─────────────────────────────────────────────────────
    {
      eventId: `evt-${caseId}-f01`,
      disputeId: caseId,
      eventType: 'velocity_alert',
      timestamp: new Date(t - 860000_000).toISOString(),
      actor: 'Fraud Engine',
      description: 'Velocity check: 3 transactions in 2 hours (within threshold)',
      metadata: { score: 35, risk: 'low' },
    },
    {
      eventId: `evt-${caseId}-f02`,
      disputeId: caseId,
      eventType: 'device_reputation',
      timestamp: new Date(t - 860000_000).toISOString(),
      actor: 'Fraud Engine',
      description: 'Device fingerprint: known trusted device (18 prior sessions)',
      metadata: { score: 92, risk: 'low', sessions: 18 },
    },
    {
      eventId: `evt-${caseId}-f03`,
      disputeId: caseId,
      eventType: 'ip_reputation',
      timestamp: new Date(t - 860000_000).toISOString(),
      actor: 'Fraud Engine',
      description: 'IP reputation: residential ISP, no proxy/VPN detected',
      metadata: { score: 88, risk: 'low', ip: '72.14.201.xx' },
    },

    // ── Case Activity (existing) ──────────────────────────────────────────
    {
      eventId: `evt-${caseId}-001`,
      disputeId: caseId,
      eventType: 'case_created',
      timestamp: new Date(t).toISOString(),
      actor: 'system',
      description: 'Dispute case created from network notification',
    },
    {
      eventId: `evt-${caseId}-002`,
      disputeId: caseId,
      eventType: 'evidence_retrieved',
      timestamp: new Date(t + 3600_000).toISOString(),
      actor: 'system',
      description: 'Transaction record retrieved from Core Banking',
      metadata: { sourceSystem: 'CoreBanking', evidenceType: 'transaction' },
    },
    {
      eventId: `evt-${caseId}-003`,
      disputeId: caseId,
      eventType: 'evidence_retrieved',
      timestamp: new Date(t + 7200_000).toISOString(),
      actor: 'system',
      description: 'Shipping confirmation pulled from ShipTrack',
      metadata: { sourceSystem: 'ShipTrack', evidenceType: 'shipping' },
    },
    {
      eventId: `evt-${caseId}-004`,
      disputeId: caseId,
      eventType: 'status_changed',
      timestamp: new Date(t + 10800_000).toISOString(),
      actor: 'system',
      description: 'Status changed: intake → evidence_gathering',
      metadata: { from: 'intake', to: 'evidence_gathering' },
    },
    {
      eventId: `evt-${caseId}-005`,
      disputeId: caseId,
      eventType: 'evidence_gap_detected',
      timestamp: new Date(t + 14400_000).toISOString(),
      actor: 'system',
      description: 'Evidence gap identified: signed delivery confirmation missing',
      metadata: { impact: 'high' },
    },
    {
      eventId: `evt-${caseId}-006`,
      disputeId: caseId,
      eventType: 'ai_draft_generated',
      timestamp: new Date(t + 86400_000).toISOString(),
      actor: 'AI Rebuttal Agent',
      description: 'AI-generated rebuttal draft ready for review',
      metadata: { confidence: 0.82, wordCount: 340 },
    },
    {
      eventId: `evt-${caseId}-007`,
      disputeId: caseId,
      eventType: 'status_changed',
      timestamp: new Date(t + 90000_000).toISOString(),
      actor: 'system',
      description: 'Status changed: ai_drafting → pending_review',
      metadata: { from: 'ai_drafting', to: 'pending_review' },
    },
    {
      eventId: `evt-${caseId}-008`,
      disputeId: caseId,
      eventType: 'analyst_assigned',
      timestamp: new Date(t + 93600_000).toISOString(),
      actor: 'system',
      description: 'Case assigned to Sarah Chen (auto-routing)',
      metadata: { analystId: 'analyst-001', analystName: 'Sarah Chen' },
    },
  ];

  // Add friendly fraud indicator for even-indexed cases
  if (index % 2 === 0) {
    events.push({
      eventId: `evt-${caseId}-f04`,
      disputeId: caseId,
      eventType: 'friendly_fraud_indicator',
      timestamp: new Date(t + 95000_000).toISOString(),
      actor: 'Fraud Engine',
      description: 'Friendly fraud pattern: cardholder has 3 prior disputes in 12 months',
      metadata: { score: 72, risk: 'high', priorDisputes: 3 },
    });
  }

  // Add high-risk indicator for certain cases
  if (index % 4 === 0) {
    events.push({
      eventId: `evt-${caseId}-f05`,
      disputeId: caseId,
      eventType: 'high_risk_indicator',
      timestamp: new Date(t + 96000_000).toISOString(),
      actor: 'Fraud Engine',
      description: 'High-risk: transaction amount exceeds 95th percentile for merchant category',
      metadata: { score: 15, risk: 'high' },
    });
  }

  // Add escalation event for critical cases
  if (index % 3 === 0) {
    events.push({
      eventId: `evt-${caseId}-009`,
      disputeId: caseId,
      eventType: 'deadline_warning',
      timestamp: new Date(t + 172800_000).toISOString(),
      actor: 'system',
      description: 'SLA deadline approaching — 3 days remaining',
      metadata: { daysRemaining: 3 },
    });
  }

  return events;
}

// Populate the mock timeline store
syntheticCaseIds.forEach((id, index) => {
  mockTimelines[id] = generateTimeline(id, index);
});
