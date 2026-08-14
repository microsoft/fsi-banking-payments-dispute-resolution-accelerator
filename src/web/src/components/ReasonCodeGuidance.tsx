import { Text, tokens } from '@fluentui/react-components';
import type { CardNetwork } from '../types/case';

interface ReasonCodeGuidanceProps {
  reasonCode: string;
  reasonCodeLabel?: string;
  cardNetwork?: CardNetwork;
  daysRemaining?: number;
}

interface GuidanceRule {
  network: string;
  timeLimit: string;
  timeLimitDays: number;
  winRate: number;
  requiredEvidence: string[];
  tips: string[];
  commonPitfalls: string[];
  rebuttalTemplate: string;
}

const guidanceDatabase: Record<string, GuidanceRule> = {
  // Visa reason codes
  '13.1': {
    network: 'Visa',
    timeLimit: '30 calendar days from dispute notification',
    timeLimitDays: 30,
    winRate: 72,
    requiredEvidence: [
      'Proof of delivery (signed or GPS-confirmed)',
      'Tracking number with carrier confirmation',
      'Transaction receipt showing order details',
      'Communication with cardholder about delivery',
    ],
    tips: [
      'Signed delivery confirmation is the strongest defense',
      'GPS/photo proof of delivery (e.g., FedEx/UPS photo) is accepted',
      'If digital goods: provide download logs, IP addresses, or access timestamps',
      'Include the ARN (Acquirer Reference Number) in your response',
    ],
    commonPitfalls: [
      'Tracking showing "delivered" without a signature may be insufficient for high-value items',
      'Delivery to a different address than billing = weak defense',
      'Providing shipping confirmation (label created) instead of delivery confirmation',
    ],
    rebuttalTemplate: 'We respectfully dispute this chargeback under Visa Reason Code 13.1 (Merchandise/Services Not Received). Our records confirm that the item was shipped on [DATE] via [CARRIER] (tracking: [TRACKING_NUMBER]). Delivery was confirmed on [DELIVERY_DATE] at the cardholder\'s billing address, as evidenced by [signed delivery receipt / GPS-confirmed photo proof]. The cardholder did not contact us prior to filing this dispute to report non-receipt or request a replacement.',
  },
  '10.4': {
    network: 'Visa',
    timeLimit: '30 calendar days from dispute notification',
    timeLimitDays: 30,
    winRate: 45,
    requiredEvidence: [
      'AVS (Address Verification) match result',
      'CVV2/CVC2 match confirmation',
      '3D Secure authentication proof (if enrolled)',
      'Device fingerprint / IP geolocation data',
      'Prior transaction history with same card',
    ],
    tips: [
      '3D Secure liability shift applies — check if transaction was authenticated',
      'Multiple successful transactions from same device/IP strengthen your case',
      'Velocity checks and fraud scoring results can support legitimacy',
      'If recurring: show original authorization with CVV + subsequent charges',
    ],
    commonPitfalls: [
      'Missing 3D Secure enrollment means no liability shift',
      'AVS partial match (zip only) is weaker than full match',
      'Failing to include the authentication response code',
    ],
    rebuttalTemplate: 'We dispute this fraud claim under Visa Reason Code 10.4 (Other Fraud — Card Absent Environment). The transaction was authenticated with [AVS full match / CVV2 match / 3D Secure]. Our fraud detection system scored this transaction at [SCORE], below our threshold for review. The device fingerprint matches [NUMBER] previous successful transactions from this cardholder. IP geolocation confirms the transaction originated from [LOCATION], consistent with the cardholder\'s known activity pattern.',
  },
  '13.3': {
    network: 'Visa',
    timeLimit: '30 calendar days from dispute notification',
    timeLimitDays: 30,
    winRate: 58,
    requiredEvidence: [
      'Product/service description matching what was advertised',
      'Proof item matched listing (photos, specs)',
      'Return/refund policy acknowledged at purchase',
      'Communication showing merchant offered resolution',
    ],
    tips: [
      'Show the cardholder was informed of specifications before purchase',
      'If return was offered and declined, document that clearly',
      'Include original product listing/advertisement screenshots',
    ],
    commonPitfalls: [
      'Subjective quality complaints are hard to defend without clear specs',
      'Missing return policy disclosure weakens position significantly',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Visa Reason Code 13.3 (Not as Described or Defective). The product/service was accurately described in our listing as [DESCRIPTION]. The cardholder acknowledged our return policy at time of purchase. We offered [resolution attempt] on [DATE], which the cardholder [declined/did not respond to]. Attached documentation shows the item delivered matches the advertised specifications.',
  },
  // Mastercard reason codes
  '4837': {
    network: 'Mastercard',
    timeLimit: '45 calendar days from dispute notification',
    timeLimitDays: 45,
    winRate: 68,
    requiredEvidence: [
      'EMV chip transaction proof (TC cryptogram)',
      'PIN verification confirmation',
      'Video surveillance (if in-person)',
      'Signed receipt or terminal printout',
    ],
    tips: [
      'Chip-read transactions with PIN have strongest defense',
      'If contactless: show terminal enforced cardholder verification for high amounts',
      'Include the full authorization response with cryptogram',
      'Mastercard allows 45 days — use the extra time to gather complete evidence',
    ],
    commonPitfalls: [
      'Magnetic stripe fallback voids chip liability protection',
      'Missing PIN verification on high-value debit transactions',
      'Not including the DE55 (ICC data) in the representment',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Mastercard Reason Code 4837 (No Cardholder Authorization). The transaction was processed using EMV chip technology with [PIN verification / cardholder verification]. The TC cryptogram confirms the physical card was present and authenticated. Terminal records show the transaction completed successfully at [LOCATION] on [DATE]. We have attached the full authorization response including DE55 ICC data.',
  },
  '4853': {
    network: 'Mastercard',
    timeLimit: '45 calendar days from dispute notification',
    timeLimitDays: 45,
    winRate: 52,
    requiredEvidence: [
      'Product description as presented to cardholder',
      'Delivery confirmation with item condition',
      'Return policy shown at time of purchase',
      'Communication trail showing resolution attempts',
    ],
    tips: [
      'Document that goods matched the description at time of sale',
      'Show you offered repair, replacement, or refund per your policy',
      'If digital: provide access logs showing product delivered as described',
    ],
    commonPitfalls: [
      'Not proving the cardholder saw and agreed to the product description',
      'Lack of documented resolution attempt before chargeback',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Mastercard Reason Code 4853 (Cardholder Dispute — Not as Described). The product/service was accurately represented as [DESCRIPTION] and the cardholder acknowledged our product listing before purchase on [DATE]. We offered [resolution] on [DATE], which was [declined/not responded to]. Our return policy, clearly displayed at checkout, provides [POLICY_DETAILS]. Attached documentation confirms the item delivered matches the advertised specifications.',
  },
  '4855': {
    network: 'Mastercard',
    timeLimit: '45 calendar days from dispute notification',
    timeLimitDays: 45,
    winRate: 65,
    requiredEvidence: [
      'Proof of delivery (signed confirmation)',
      'Proof services were rendered (date/time/location)',
      'Booking confirmation acknowledged by cardholder',
      'Communication confirming service completion',
    ],
    tips: [
      'For services: appointment confirmation + completion records',
      'For goods: carrier tracking with delivery confirmation',
      'Include cardholder acknowledgment of receipt if available',
    ],
    commonPitfalls: [
      'Service-based disputes without time-stamped completion proof',
      'Relying solely on booking confirmation without delivery evidence',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Mastercard Reason Code 4855 (Goods or Services Not Provided). [For goods]: The item was shipped via [CARRIER] (tracking: [TRACKING]) and delivery was confirmed on [DATE] at the cardholder address. [For services]: The service was rendered on [DATE] at [LOCATION] as confirmed by [completion records / signed acknowledgment]. The cardholder confirmed receipt/completion on [DATE].',
  },
  // Amex reason codes
  'C28': {
    network: 'Amex',
    timeLimit: '20 calendar days from dispute notification',
    timeLimitDays: 20,
    winRate: 38,
    requiredEvidence: [
      'Original authorization agreement showing recurring terms',
      'Proof cardholder was notified before charge',
      'Cancellation policy presented at signup',
      'Proof no valid cancellation was received',
    ],
    tips: [
      'Amex has only 20 days — prioritize this immediately',
      'Show the cardholder agreed to recurring billing terms',
      'Provide evidence that cancellation instructions were clear and accessible',
      'If cancelled late: show the billing cycle cutoff was already passed',
    ],
    commonPitfalls: [
      'Not having explicit opt-in for recurring charges on file',
      'Amex is cardholder-friendly — incomplete evidence often results in loss',
      'Missing notification of upcoming charge (required for some subscription types)',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Amex Reason Code C28 (Canceled Recurring Billing). The cardholder enrolled in our recurring billing program on [DATE] and explicitly agreed to the terms including [billing frequency and amount]. Our records show no valid cancellation request was received prior to the disputed charge. The cardholder was notified of the upcoming charge on [NOTIFICATION_DATE] per our policy. Our cancellation process is clearly documented at [LOCATION] and was presented during enrollment.',
  },
  'FR2': {
    network: 'Amex',
    timeLimit: '20 calendar days from dispute notification',
    timeLimitDays: 20,
    winRate: 28,
    requiredEvidence: [
      'Full transaction authentication details',
      'Device identification / IP analysis',
      'Order history with same payment method',
      'Fraud detection system score at time of auth',
    ],
    tips: [
      'Amex fraud disputes are very aggressive — 20-day window is tight',
      'Strong velocity/device data can demonstrate legitimate cardholder activity',
      'If 3D Secure or SafeKey was used, cite the liability shift',
    ],
    commonPitfalls: [
      'Amex Full Recourse means issuer places all liability on merchant by default',
      'Without SafeKey authentication, win rates are very low',
      'Not including comprehensive device/behavioral analytics',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Amex Reason Code FR2 (Fraud — Full Recourse). The transaction was authenticated using [SafeKey/3D Secure] with a successful verification on [DATE]. Device fingerprint analysis shows the purchase originated from a device consistent with [NUMBER] prior legitimate transactions. Our fraud detection system scored this at [SCORE]/100, well below our review threshold. IP geolocation data confirms activity from [LOCATION], matching the cardholder profile.',
  },
  // Discover reason codes
  'UA01': {
    network: 'Discover',
    timeLimit: '30 calendar days from dispute notification',
    timeLimitDays: 30,
    winRate: 62,
    requiredEvidence: [
      'EMV/chip read confirmation',
      'PIN or signature verification',
      'Terminal transaction log',
      'Video or receipt matching timestamp',
    ],
    tips: [
      'EMV chip-read with PIN is the gold standard for card-present fraud',
      'Include terminal ID and full transaction reference',
      'Discover follows Visa-like timelines (30 days)',
    ],
    commonPitfalls: [
      'Card-present fraud without chip read is very difficult to win',
      'Missing terminal log data weakens the defense significantly',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Discover Reason Code UA01 (Fraud — Card Present). The transaction was processed with EMV chip technology and [PIN/signature] verification at terminal [TERMINAL_ID] on [DATE]. The TC cryptogram confirms the physical card was present and properly authenticated. Terminal logs confirm the transaction completed at [TIME] without error. [If available]: Surveillance footage from [LOCATION] confirms the cardholder was present.',
  },
  'UA02': {
    network: 'Discover',
    timeLimit: '30 calendar days from dispute notification',
    timeLimitDays: 30,
    winRate: 41,
    requiredEvidence: [
      'AVS full match result',
      'CVV2 match confirmation',
      'IP geolocation data',
      '3D Secure / ProtectBuy authentication',
      'Device fingerprint analysis',
    ],
    tips: [
      'ProtectBuy (Discover 3DS) provides liability shift',
      'Show pattern of legitimate activity from same device',
      'Include all authentication data points available',
    ],
    commonPitfalls: [
      'CNP fraud without ProtectBuy has low win probability',
      'Partial AVS match alone is insufficient',
    ],
    rebuttalTemplate: 'We dispute this chargeback under Discover Reason Code UA02 (Fraud — Card Not Present). The transaction was authenticated with [AVS full match / CVV2 match / ProtectBuy 3D Secure]. Device fingerprint analysis identifies this device as having completed [NUMBER] prior successful transactions. IP geolocation shows the request originated from [LOCATION], consistent with the cardholder profile. Our fraud screening system scored this transaction at [SCORE]/100.',
  },
};

export function ReasonCodeGuidance({ reasonCode, reasonCodeLabel, cardNetwork, daysRemaining }: ReasonCodeGuidanceProps) {
  // Lookup by raw code first, then try stripping network prefix (e.g. "Visa 13.1" -> "13.1")
  const codeKey = reasonCode.includes(' ') ? reasonCode.split(' ').slice(1).join(' ') : reasonCode;
  const guidance = guidanceDatabase[reasonCode] ?? guidanceDatabase[codeKey];

  if (!guidance) {
    return (
      <div>
        <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: '8px' }}>
          Reason Code Guidance
        </Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          No specific guidance available for reason code {reasonCode}. Refer to {cardNetwork?.toUpperCase() ?? 'network'} dispute resolution manual.
        </Text>
      </div>
    );
  }

  const winRateColor =
    guidance.winRate >= 65 ? tokens.colorPaletteGreenForeground1 :
    guidance.winRate >= 45 ? tokens.colorPaletteYellowForeground1 :
    tokens.colorPaletteRedForeground1;

  const urgencyColor =
    (daysRemaining ?? 99) <= 5 ? tokens.colorPaletteRedForeground1 :
    (daysRemaining ?? 99) <= 14 ? tokens.colorPaletteYellowForeground1 :
    tokens.colorNeutralForeground3;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <Text weight="semibold" size={400}>
          Reason Code Guidance
        </Text>
        <span
          style={{
            background: tokens.colorPaletteBlueBorderActive,
            color: 'white',
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 600,
          }}
        >
          {guidance.network} · {guidance.timeLimit}
        </span>
      </div>

      {reasonCodeLabel && (
        <Text size={200} style={{ display: 'block', color: tokens.colorNeutralForeground3, marginBottom: '12px' }}>
          {reasonCode}: {reasonCodeLabel}
        </Text>
      )}

      {/* Win Rate + Deadline Urgency */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '14px' }}>
        <div style={{ flex: 1, padding: '8px 12px', borderRadius: '6px', border: `1px solid ${tokens.colorNeutralStroke2}` }}>
          <Text size={200} style={{ display: 'block', color: tokens.colorNeutralForeground3, marginBottom: '4px' }}>
            Historical Win Rate
          </Text>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text weight="bold" size={500} style={{ color: winRateColor }}>
              {guidance.winRate}%
            </Text>
            <div style={{ flex: 1, height: '6px', borderRadius: '3px', background: tokens.colorNeutralStroke2, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${guidance.winRate}%`, background: winRateColor, borderRadius: '3px' }} />
            </div>
          </div>
        </div>
        {daysRemaining !== undefined && (
          <div style={{ padding: '8px 12px', borderRadius: '6px', border: `1px solid ${urgencyColor}`, minWidth: '100px', textAlign: 'center' }}>
            <Text size={200} style={{ display: 'block', color: tokens.colorNeutralForeground3, marginBottom: '4px' }}>
              Deadline
            </Text>
            <Text weight="bold" size={500} style={{ color: urgencyColor }}>
              {daysRemaining}d
            </Text>
          </div>
        )}
      </div>

      {/* Required Evidence */}
      <div style={{ marginBottom: '14px' }}>
        <Text weight="semibold" size={200} style={{ display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px', color: tokens.colorNeutralForeground3 }}>
          Required Evidence
        </Text>
        <ul style={{ margin: 0, paddingLeft: '16px', listStyleType: 'disc' }}>
          {guidance.requiredEvidence.map((item, i) => (
            <li key={i} style={{ marginBottom: '3px' }}>
              <Text size={200}>{item}</Text>
            </li>
          ))}
        </ul>
      </div>

      {/* Tips */}
      <div style={{ marginBottom: '14px' }}>
        <Text weight="semibold" size={200} style={{ display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px', color: tokens.colorPaletteGreenForeground1 }}>
          💡 Tips
        </Text>
        <ul style={{ margin: 0, paddingLeft: '16px', listStyleType: 'none' }}>
          {guidance.tips.map((tip, i) => (
            <li key={i} style={{ marginBottom: '3px' }}>
              <Text size={200}>• {tip}</Text>
            </li>
          ))}
        </ul>
      </div>

      {/* Common Pitfalls */}
      <div style={{ marginBottom: '14px' }}>
        <Text weight="semibold" size={200} style={{ display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px', color: tokens.colorPaletteRedForeground1 }}>
          ⚠️ Common Pitfalls
        </Text>
        <ul style={{ margin: 0, paddingLeft: '16px', listStyleType: 'none' }}>
          {guidance.commonPitfalls.map((pitfall, i) => (
            <li key={i} style={{ marginBottom: '3px' }}>
              <Text size={200}>• {pitfall}</Text>
            </li>
          ))}
        </ul>
      </div>

      {/* Rebuttal Template */}
      <div>
        <Text weight="semibold" size={200} style={{ display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px', color: tokens.colorPaletteBlueBorderActive }}>
          📝 Rebuttal Template
        </Text>
        <div
          style={{
            padding: '10px 14px',
            borderRadius: '6px',
            border: `1px solid ${tokens.colorNeutralStroke2}`,
            background: tokens.colorNeutralBackground3,
            fontFamily: 'monospace',
            fontSize: '11px',
            lineHeight: '1.6',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {guidance.rebuttalTemplate}
        </div>
      </div>
    </div>
  );
}
