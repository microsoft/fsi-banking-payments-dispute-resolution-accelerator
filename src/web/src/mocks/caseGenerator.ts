/**
 * Mock data generator for dispute case management system.
 * Produces 50 realistic, deterministic CaseSummary and Case objects.
 */
import type {
  Case,
  CaseSummary,
  CaseStatus,
  CardNetwork,
  RiskLevel,
  EvidenceType,
  CompletenessLevel,
  ImpactLevel,
  ReasonCodeChecklistItem,
  Evidence,
  EvidenceGap,
  RebuttalDraft,
  Citation,
} from '../types/case';

// ── Helper Arrays ─────────────────────────────────────────────────────────────

const MERCHANT_NAMES: string[] = [
  'CloudNine Electronics',
  'Pacific Rim Imports',
  'GreenLeaf Organics',
  'StellarTech Solutions',
  'Midnight Express Delivery',
  'Urban Threads Apparel',
  'Blue Horizon Travel',
  'Quantum Fitness Pro',
  'Maple & Oak Furniture',
  'Zenith Digital Services',
  'Ivory Coast Cosmetics',
  'Red Mountain Outfitters',
  'Apex Gaming Lounge',
  'Silver Creek Winery',
  'NovaStar Auto Parts',
  'Petal & Bloom Florist',
  'TerraVista Landscaping',
  'Cobalt Media Group',
  'Summit Health Supplements',
  'Echo Valley Records',
  'Nimbus Cloud Hosting',
  'Artisan Bread Co',
  'Falcon Security Systems',
  'Sunridge Solar Energy',
  'Opal & Jade Jewelry',
  'Maverick Sports Gear',
  'Tidewater Marine Supply',
  'Pinnacle Consulting LLC',
  'Velvet Lounge Restaurant',
  'Brightline Education',
  'Iron Wolf Gym',
  'Aurora Borealis Spa',
  'Granite Peak Adventures',
  'Digital Frontier Labs',
  'Harmony Music Academy',
  'Coral Reef Aquatics',
  'Ember & Stone Pizza',
  'Cascade Software Inc',
  'Prairie Wind Farms',
  'Atlas Global Shipping',
  'Crimson Fox Publishing',
  'Sapphire Bay Resorts',
  'Thunderbolt Electric',
  'Willow Creek Pharmacy',
  'Obsidian Craft Brewery',
  'Nordic Trail Equipment',
  'Cerulean Wave Surfboards',
  'Phoenix Rise Marketing',
  'Driftwood Antiques',
  'Vertex Aerospace Parts',
];

const CARDHOLDER_NAMES: string[] = [
  'James Whitfield',
  'Maria Gonzalez',
  'David Park',
  'Amara Okafor',
  'Rebecca Torres',
  'Samuel Richardson',
  'Yuki Tanaka',
  'Isabella Martinez',
  'Thomas Andersen',
  'Fatima Al-Rashid',
  'Nathan Brooks',
  'Sophia Patel',
  'Eric Johansson',
  'Carmen Delgado',
  'Kevin O\'Brien',
  'Lena Novak',
  'Robert Chang',
  'Olivia Hawkins',
  'Hassan Mahmoud',
  'Claire Dubois',
];

const ANALYSTS = [
  { id: 'analyst-001', name: 'Sarah Chen' },
  { id: 'analyst-002', name: 'Marcus Rivera' },
  { id: 'analyst-003', name: 'Priya Sharma' },
];

interface ReasonCodeConfig {
  code: string;
  label: string;
  network: CardNetwork;
  checklistItems: string[];
}

const REASON_CODES: ReasonCodeConfig[] = [
  // Visa
  { code: '13.1', label: 'Merchandise/Services Not Received', network: 'visa', checklistItems: ['Proof of delivery', 'Shipping confirmation', 'Customer communication', 'Delivery receipt'] },
  { code: '10.4', label: 'Other Fraud – Card Absent Environment', network: 'visa', checklistItems: ['AVS match', 'CVV verification', '3D Secure authentication', 'Device fingerprint', 'IP geolocation'] },
  { code: '13.3', label: 'Not as Described', network: 'visa', checklistItems: ['Product description at purchase', 'Return policy disclosure', 'Customer complaint details', 'Photos of received item'] },
  { code: '13.6', label: 'Credit Not Processed', network: 'visa', checklistItems: ['Refund policy', 'Return receipt', 'Refund processing evidence', 'Communication log'] },
  { code: '13.7', label: 'Cancelled Merchandise/Services', network: 'visa', checklistItems: ['Cancellation policy', 'Service agreement', 'Cancellation request record'] },
  // Mastercard
  { code: '4837', label: 'No Cardholder Authorization', network: 'mastercard', checklistItems: ['Authorization log', 'Chip/PIN verification', 'Signature comparison', 'Transaction receipt'] },
  { code: '4853', label: 'Cardholder Dispute – Defective', network: 'mastercard', checklistItems: ['Product specifications', 'Quality inspection report', 'Return authorization', 'Repair offer evidence'] },
  { code: '4855', label: 'Goods or Services Not Provided', network: 'mastercard', checklistItems: ['Delivery confirmation', 'Service completion record', 'Tracking number', 'Customer sign-off'] },
  { code: '4834', label: 'Point of Interaction Error', network: 'mastercard', checklistItems: ['Terminal transaction log', 'Batch settlement record', 'Duplicate check'] },
  { code: '4863', label: 'Cardholder Does Not Recognize', network: 'mastercard', checklistItems: ['Billing descriptor clarification', 'Purchase confirmation email', 'Account login evidence'] },
  // Amex
  { code: 'C08', label: 'Goods/Services Not Received', network: 'amex', checklistItems: ['Shipping proof', 'Tracking information', 'Delivery confirmation', 'Customer notification'] },
  { code: 'C28', label: 'Cancelled Recurring Billing', network: 'amex', checklistItems: ['Subscription agreement', 'Cancellation policy', 'Prior notification', 'Billing history'] },
  { code: 'FR2', label: 'Fraud – Full Recourse', network: 'amex', checklistItems: ['Fraud detection records', 'Authentication evidence', 'Velocity checks', 'Device data'] },
  { code: 'F29', label: 'Card Not Present Fraud', network: 'amex', checklistItems: ['SafeKey authentication', 'AVS result', 'CID match', 'Order details', 'IP address log'] },
  { code: 'C32', label: 'Goods/Services Damaged or Defective', network: 'amex', checklistItems: ['Quality report', 'Return instructions sent', 'Inspection evidence'] },
  // Discover
  { code: 'UA01', label: 'Fraud – Card Present', network: 'discover', checklistItems: ['Chip read verification', 'Signature comparison', 'Video evidence', 'Terminal ID log'] },
  { code: 'UA02', label: 'Fraud – Card Not Present', network: 'discover', checklistItems: ['CVV verification', 'AVS match', 'Device fingerprint', '3DS result'] },
  { code: 'DA', label: 'Declined Authorization', network: 'discover', checklistItems: ['Authorization response code', 'Force-post evidence', 'System logs'] },
  { code: 'RG', label: 'Non-Receipt of Goods/Services', network: 'discover', checklistItems: ['Shipping confirmation', 'Delivery proof', 'Tracking details', 'Customer communication'] },
  { code: 'NR', label: 'No Refund/Return Policy Violation', network: 'discover', checklistItems: ['Published return policy', 'Refund timeline', 'Return receipt'] },
];

const EVIDENCE_TYPES: EvidenceType[] = [
  'transaction', 'shipping', 'communication', 'receipt',
  'contract', 'fraud_signal', 'order', 'photo',
  'fraud_screening', 'device_fingerprint',
];

const SOURCE_SYSTEMS: string[] = [
  'PaymentGateway', 'ShippingProvider', 'CRM', 'FraudEngine',
  'OrderManagement', 'CustomerPortal', 'EmailArchive', 'DocumentStore',
];

const EVIDENCE_GAP_ITEMS: string[] = [
  'Delivery confirmation with signature',
  'Return merchandise authorization form',
  'Customer communication log showing resolution attempt',
  'Fraud screening report from transaction time',
  'Device fingerprint matching previous purchases',
  'IP geolocation data for transaction',
  'CVV/AVS verification record',
  '3D Secure authentication result',
  'Billing descriptor explanation to customer',
  'Cancellation policy as shown at checkout',
  'Refund processing receipt',
  'Service completion acknowledgment',
];

const EVIDENCE_GAP_REASONS: string[] = [
  'Source system unavailable during retrieval window',
  'Document expired past retention period',
  'Customer did not respond to request',
  'Third-party vendor has not provided data',
  'Record not found in expected system',
  'Integration timeout during evidence collection',
];

// ── Status distribution (indices into the 50-case array) ──────────────────────

interface CaseConfig {
  index: number;
  status: CaseStatus;
}

function buildStatusDistribution(): CaseConfig[] {
  const configs: CaseConfig[] = [];
  const statuses: { status: CaseStatus; count: number }[] = [
    { status: 'intake', count: 8 },
    { status: 'evidence_gathering', count: 10 },
    { status: 'ai_drafting', count: 8 },
    { status: 'pending_review', count: 12 },
    { status: 'escalated', count: 4 },
    { status: 'approved', count: 4 },
    { status: 'denied', count: 2 },
    { status: 'submitted', count: 1 },
    { status: 'expired', count: 1 },
  ];

  let idx = 0;
  for (const { status, count } of statuses) {
    for (let i = 0; i < count; i++) {
      configs.push({ index: idx, status });
      idx++;
    }
  }
  return configs;
}

// ── Deterministic pseudo-random (seeded) ──────────────────────────────────────

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

// ── UUID helpers ──────────────────────────────────────────────────────────────

function makeCaseId(index: number): string {
  const num = (100 + index).toString().padStart(12, '0');
  return `00000000-0000-0000-0000-${num}`;
}

function makeEvidenceId(caseIndex: number, evidenceIndex: number): string {
  const num = (caseIndex * 10 + evidenceIndex).toString().padStart(12, '0');
  return `eeeeeeee-eeee-eeee-eeee-${num}`;
}

// ── Date helpers ──────────────────────────────────────────────────────────────

const BASE_DATE = new Date('2026-05-01T00:00:00Z').getTime();
const END_DATE = new Date('2026-07-08T00:00:00Z').getTime();
const DATE_RANGE = END_DATE - BASE_DATE;
const TODAY = new Date('2026-07-09T00:00:00Z');

function randomDate(rand: () => number): string {
  const ts = BASE_DATE + Math.floor(rand() * DATE_RANGE);
  return new Date(ts).toISOString();
}

function addDays(isoDate: string, days: number): string {
  const d = new Date(isoDate);
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

function dateOnly(isoDate: string): string {
  return isoDate.split('T')[0];
}

// ── Amount generation ─────────────────────────────────────────────────────────

function generateAmount(rand: () => number, index: number): number {
  // Create variety: some low, some mid, some high
  const bucket = index % 5;
  let amount: number;
  switch (bucket) {
    case 0: amount = 15 + rand() * 85; break;           // $15-$100
    case 1: amount = 100 + rand() * 400; break;         // $100-$500
    case 2: amount = 500 + rand() * 1500; break;        // $500-$2000
    case 3: amount = 2000 + rand() * 4000; break;       // $2000-$6000
    case 4: amount = 6000 + rand() * 6000; break;       // $6000-$12000
    default: amount = 200 + rand() * 800;
  }
  return Math.round(amount * 100) / 100;
}

// ── Risk level from amount + status ───────────────────────────────────────────

function determineRiskLevel(amount: number, status: CaseStatus, rand: () => number): RiskLevel {
  if (status === 'escalated' || amount > 8000) return 'critical';
  if (amount > 4000 || (status === 'denied' && rand() > 0.5)) return 'high';
  if (amount > 1000 || status === 'pending_review') return 'medium';
  return 'low';
}

// ── Win probability ───────────────────────────────────────────────────────────

function generateWinProbability(status: CaseStatus, riskLevel: RiskLevel, rand: () => number): number | undefined {
  if (status === 'intake') return undefined;

  let base: number;
  switch (status) {
    case 'approved':
    case 'submitted':
      base = 0.7 + rand() * 0.25; break;
    case 'denied':
    case 'expired':
      base = 0.15 + rand() * 0.2; break;
    case 'escalated':
      base = 0.2 + rand() * 0.3; break;
    case 'pending_review':
      base = 0.5 + rand() * 0.4; break;
    default:
      base = 0.35 + rand() * 0.45;
  }

  // Risk penalty
  if (riskLevel === 'critical') base -= 0.15;
  else if (riskLevel === 'high') base -= 0.08;

  return Math.round(Math.max(0.15, Math.min(0.95, base)) * 100) / 100;
}

// ── Deadline generation ───────────────────────────────────────────────────────

function generateDeadlineDays(index: number, status: CaseStatus, rand: () => number): number {
  if (status === 'expired') return -3;
  if (status === 'approved' || status === 'submitted' || status === 'denied') {
    return Math.floor(rand() * 15) + 5; // 5-20 days (already resolved)
  }
  // ~10 cases with ≤3 days remaining
  if (index % 5 === 0 && index < 40) {
    return Math.floor(rand() * 6) - 2; // -2 to 3
  }
  return Math.floor(rand() * 27) + 4; // 4-30
}

// ── Checklist generation ──────────────────────────────────────────────────────

function generateChecklist(
  reasonCodeConfig: ReasonCodeConfig,
  status: CaseStatus,
  rand: () => number
): ReasonCodeChecklistItem[] {
  const items = reasonCodeConfig.checklistItems;
  const count = Math.min(items.length, 2 + Math.floor(rand() * 3)); // 2-4 items
  const selected = items.slice(0, count);

  return selected.map((item, i) => {
    let satisfied: boolean;
    if (status === 'intake') {
      satisfied = false;
    } else if (status === 'approved' || status === 'submitted') {
      satisfied = true;
    } else {
      satisfied = i < count - 1 ? rand() > 0.3 : rand() > 0.6;
    }
    return { item, required: true, satisfied };
  });
}

// ── Evidence generation ───────────────────────────────────────────────────────

function generateEvidence(
  caseIndex: number,
  status: CaseStatus,
  createdAt: string,
  rand: () => number
): Evidence[] {
  let count: number;
  switch (status) {
    case 'intake': count = 0; break;
    case 'evidence_gathering': count = 1 + Math.floor(rand() * 2); break;
    case 'ai_drafting': count = 2 + Math.floor(rand() * 2); break;
    case 'pending_review':
    case 'approved':
    case 'submitted': count = 3 + Math.floor(rand() * 2); break;
    case 'escalated': count = 2 + Math.floor(rand() * 2); break;
    case 'denied':
    case 'expired': count = 1 + Math.floor(rand() * 2); break;
    default: count = 1;
  }

  const evidence: Evidence[] = [];
  for (let i = 0; i < count; i++) {
    const typeIndex = (caseIndex * 3 + i) % EVIDENCE_TYPES.length;
    const sourceIndex = (caseIndex + i) % SOURCE_SYSTEMS.length;
    const completeness: CompletenessLevel =
      rand() > 0.7 ? 'complete' : rand() > 0.4 ? 'partial' : 'missing';

    evidence.push({
      evidenceId: makeEvidenceId(caseIndex, i),
      type: EVIDENCE_TYPES[typeIndex],
      sourceSystem: SOURCE_SYSTEMS[sourceIndex],
      retrievedAt: addDays(createdAt, 1 + Math.floor(rand() * 3)),
      contentRef: `blob://evidence-store/${makeCaseId(caseIndex)}/${i}.pdf`,
      completeness,
    });
  }
  return evidence;
}

// ── Evidence gaps ─────────────────────────────────────────────────────────────

function generateEvidenceGaps(
  status: CaseStatus,
  winProb: number | undefined,
  rand: () => number
): EvidenceGap[] {
  if (status === 'intake' || status === 'approved' || status === 'submitted') return [];

  const maxGaps = (winProb !== undefined && winProb < 0.4) ? 3 : (winProb !== undefined && winProb < 0.6) ? 2 : 1;
  const count = Math.floor(rand() * (maxGaps + 1));

  const gaps: EvidenceGap[] = [];
  for (let i = 0; i < count; i++) {
    const itemIdx = Math.floor(rand() * EVIDENCE_GAP_ITEMS.length);
    const reasonIdx = Math.floor(rand() * EVIDENCE_GAP_REASONS.length);
    const impacts: ImpactLevel[] = ['critical', 'high', 'medium', 'low'];
    const impactIdx = Math.floor(rand() * impacts.length);

    gaps.push({
      missingItem: EVIDENCE_GAP_ITEMS[itemIdx],
      reason: EVIDENCE_GAP_REASONS[reasonIdx],
      impact: impacts[impactIdx],
    });
  }
  return gaps;
}

// ── Rebuttal draft ────────────────────────────────────────────────────────────

const REBUTTAL_TEMPLATES: string[] = [
  'Based on the evidence gathered, the transaction on {date} for ${amount} at {merchant} was authorized by the cardholder. Our records indicate that the goods were delivered on {deliveryDate} as confirmed by tracking number {tracking}. The delivery was signed for at the address on file.',
  'We respectfully dispute this chargeback. The cardholder completed a verified 3D Secure authentication at the time of purchase. Additionally, the shipping address matches the billing address, and the device fingerprint matches three previous successful transactions on this account.',
  'The services described in the original order were fully rendered as agreed. Our system logs confirm the cardholder accessed and utilized the service on multiple occasions after the transaction date. Customer support records show no complaints were filed prior to the dispute.',
  'This transaction was processed with full EMV chip authentication. The terminal log confirms a successful chip read with PIN verification. No authorization reversals were requested, and the card was present at the point of sale during the transaction.',
  'Our investigation reveals that the cardholder received a full refund on {refundDate} via the original payment method. The refund reference number is {refRef}, and the credit should appear within 5-10 business days of the processing date.',
];

function generateRebuttalDraft(
  caseIndex: number,
  status: CaseStatus,
  evidence: Evidence[],
  _rand: () => number
): RebuttalDraft | undefined {
  const hasRebuttal = ['ai_drafting', 'pending_review', 'approved', 'submitted', 'escalated'].includes(status);
  if (!hasRebuttal) return undefined;

  const templateIdx = caseIndex % REBUTTAL_TEMPLATES.length;
  const text = REBUTTAL_TEMPLATES[templateIdx];

  const citations: Citation[] = evidence.slice(0, Math.min(3, evidence.length)).map(ev => ({
    evidenceId: ev.evidenceId,
    excerpt: `Evidence from ${ev.sourceSystem} (${ev.type}) retrieved ${dateOnly(ev.retrievedAt)} confirms transaction details.`,
  }));

  return { text, citations };
}

function buildCaseDescription(merchantName: string, reasonCodeLabel: string, transactionAmount: number, cardholderName: string): string {
  return `${cardholderName} submitted a dispute for $${transactionAmount.toFixed(2)} with ${merchantName}, citing ${reasonCodeLabel.toLowerCase()}.`;
}

// ── Main generators ───────────────────────────────────────────────────────────

export function generateMockCases(): CaseSummary[] {
  const rand = seededRandom(42);
  const configs = buildStatusDistribution();
  const cases: CaseSummary[] = [];

  for (let i = 0; i < 50; i++) {
    const { status } = configs[i];
    const caseId = makeCaseId(i);

    // Assign reason code (cycle through to get network variety)
    const reasonCodeConfig = REASON_CODES[i % REASON_CODES.length];

    // Amounts & risk
    const transactionAmount = generateAmount(rand, i);
    const riskLevel = determineRiskLevel(transactionAmount, status, rand);
    const winProbability = generateWinProbability(status, riskLevel, rand);

    // Dates
    const createdAt = randomDate(rand);
    const updatedAt = addDays(createdAt, 1 + Math.floor(rand() * 7));

    // Deadline
    const daysRemaining = generateDeadlineDays(i, status, rand);
    const dueDate = new Date(TODAY);
    dueDate.setDate(dueDate.getDate() + daysRemaining);
    const dueDateStr = dateOnly(dueDate.toISOString());

    // Analyst assignment (intake cases are unassigned)
    let assignedAnalystId: string | undefined;
    let assignedAnalystName: string | undefined;
    if (status !== 'intake') {
      const analyst = ANALYSTS[i % ANALYSTS.length];
      assignedAnalystId = analyst.id;
      assignedAnalystName = analyst.name;
    }

    cases.push({
      caseId,
      status,
      reasonCode: reasonCodeConfig.code,
      reasonCodeLabel: reasonCodeConfig.label,
      cardNetwork: reasonCodeConfig.network,
      merchantName: MERCHANT_NAMES[i],
      caseDescription: buildCaseDescription(MERCHANT_NAMES[i], reasonCodeConfig.label, transactionAmount, CARDHOLDER_NAMES[i % CARDHOLDER_NAMES.length]),
      transactionAmount,
      winProbability,
      riskLevel,
      assignedAnalystId,
      assignedAnalystName,
      deadline: { dueDate: dueDateStr, daysRemaining },
      createdAt,
      updatedAt,
    });
  }

  return cases;
}

export function generateMockDetailCases(): Record<string, Case> {
  const rand = seededRandom(42);
  const configs = buildStatusDistribution();
  const result: Record<string, Case> = {};

  for (let i = 0; i < 50; i++) {
    const { status } = configs[i];
    const caseId = makeCaseId(i);

    // Assign reason code
    const reasonCodeConfig = REASON_CODES[i % REASON_CODES.length];

    // Amounts & risk
    const transactionAmount = generateAmount(rand, i);
    const riskLevel = determineRiskLevel(transactionAmount, status, rand);
    const winProbability = generateWinProbability(status, riskLevel, rand);

    // Dates
    const createdAt = randomDate(rand);
    const updatedAt = addDays(createdAt, 1 + Math.floor(rand() * 7));
    const transactionDate = addDays(createdAt, -(Math.floor(rand() * 14) + 1)); // 1-14 days before case created

    // Deadline
    const daysRemaining = generateDeadlineDays(i, status, rand);
    const dueDate = new Date(TODAY);
    dueDate.setDate(dueDate.getDate() + daysRemaining);
    const dueDateStr = dateOnly(dueDate.toISOString());

    // Analyst assignment
    let assignedAnalystId: string | undefined;
    let assignedAnalystName: string | undefined;
    if (status !== 'intake') {
      const analyst = ANALYSTS[i % ANALYSTS.length];
      assignedAnalystId = analyst.id;
      assignedAnalystName = analyst.name;
    }

    // Cardholder
    const cardholderName = CARDHOLDER_NAMES[i % CARDHOLDER_NAMES.length];

    // Dispute reference
    const networkPrefix = reasonCodeConfig.network.toUpperCase();
    const refNum = (10100 + i).toString();
    const disputeRef = `${networkPrefix}-2026-${refNum}`;

    // Detail rand (use separate seed for detail-specific fields so summary fields stay in sync)
    const detailRand = seededRandom(1000 + i);

    // Checklist
    const reasonCodeChecklist = generateChecklist(reasonCodeConfig, status, detailRand);

    // Evidence
    const evidence = generateEvidence(i, status, createdAt, detailRand);

    // Evidence gaps
    const evidenceGaps = generateEvidenceGaps(status, winProbability, detailRand);

    // Rebuttal
    const rebuttalDraft = generateRebuttalDraft(i, status, evidence, detailRand);

    const fullCase: Case = {
      caseId,
      status,
      reasonCode: reasonCodeConfig.code,
      reasonCodeLabel: reasonCodeConfig.label,
      cardNetwork: reasonCodeConfig.network,
      merchantName: MERCHANT_NAMES[i],
      transactionAmount,
      winProbability,
      riskLevel,
      assignedAnalystId,
      assignedAnalystName,
      deadline: {
        network: reasonCodeConfig.network,
        dueDate: dueDateStr,
        daysRemaining,
      },
      createdAt,
      updatedAt,
      orchestrationId: caseId,
      disputeRef,
      cardholderName,
      caseDescription: buildCaseDescription(MERCHANT_NAMES[i], reasonCodeConfig.label, transactionAmount, cardholderName),
      transactionDate: dateOnly(transactionDate),
      reasonCodeChecklist,
      evidence,
      evidenceGaps,
      rebuttalDraft,
    };

    result[caseId] = fullCase;
  }

  return result;
}
