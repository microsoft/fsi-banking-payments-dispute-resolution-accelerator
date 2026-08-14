import type { DemoTransaction, ReasonCodeOption, CardNetwork } from '../types/dispute.ts';

// ── Merchant pool ─────────────────────────────────────────────────────────────

interface MerchantEntry {
  name: string;
  category: string;
  minAmount: number;
  maxAmount: number;
  descriptionTemplates: string[];
}

const MERCHANT_POOL: MerchantEntry[] = [
  {
    name: 'Acme Electronics',
    category: 'Electronics',
    minAmount: 49,
    maxAmount: 899,
    descriptionTemplates: [
      'Online order – Wireless Headphones Pro',
      'Purchase – Smart Speaker (Order #ACE-{n})',
      'In-store purchase – Laptop Stand & Hub',
    ],
  },
  {
    name: 'Global Apparel Co.',
    category: 'Clothing & Accessories',
    minAmount: 29,
    maxAmount: 350,
    descriptionTemplates: [
      "Purchase – Men's Jacket (Order #GCA-{n})",
      "Purchase – Women's Dress (Order #GCA-{n})",
      'Online order – Casual Sneakers',
    ],
  },
  {
    name: 'TravelNow LLC',
    category: 'Travel & Lodging',
    minAmount: 199,
    maxAmount: 3500,
    descriptionTemplates: [
      'Hotel reservation – 3 nights (Booking #TN-{n})',
      'Flight booking – round trip (Ref #TN-{n})',
      'Car rental – 5 days (Booking #TN-{n})',
    ],
  },
  {
    name: 'StreamFlix Premium',
    category: 'Digital Subscription',
    minAmount: 9.99,
    maxAmount: 29.99,
    descriptionTemplates: [
      'Monthly subscription renewal',
      'Annual plan upgrade',
      'Family plan – monthly renewal',
    ],
  },
  {
    name: 'Sunrise Restaurant Group',
    category: 'Dining',
    minAmount: 25,
    maxAmount: 250,
    descriptionTemplates: [
      'Dining – table reservation charge',
      'Online order – delivery (Order #SR-{n})',
      'Event catering deposit',
    ],
  },
  {
    name: 'CloudSoft Solutions',
    category: 'Software & SaaS',
    minAmount: 49,
    maxAmount: 999,
    descriptionTemplates: [
      'Annual software licence – Project Management Suite',
      'Monthly subscription – Team Plan (Order #CS-{n})',
      'One-time purchase – Developer Tools',
    ],
  },
  {
    name: 'FitGear Pro',
    category: 'Sporting Goods',
    minAmount: 39,
    maxAmount: 550,
    descriptionTemplates: [
      'Purchase – Resistance Bands Set',
      'Online order – Running Shoes (Order #FG-{n})',
      'In-store – Yoga Mat & Accessories',
    ],
  },
  {
    name: 'HomeStyle Furnishings',
    category: 'Home & Garden',
    minAmount: 89,
    maxAmount: 1500,
    descriptionTemplates: [
      'Purchase – Accent Chair (Order #HS-{n})',
      'Online order – Standing Desk',
      'Delivery – Bookcase & Assembly (Order #HS-{n})',
    ],
  },
  {
    name: 'QuickFuel Station',
    category: 'Fuel & Convenience',
    minAmount: 30,
    maxAmount: 120,
    descriptionTemplates: [
      'Fuel purchase',
      'Pay-at-pump transaction',
      'In-store purchase + fuel',
    ],
  },
  {
    name: 'MediCare Pharmacy',
    category: 'Health & Pharmacy',
    minAmount: 15,
    maxAmount: 300,
    descriptionTemplates: [
      'Prescription pickup',
      'Over-the-counter purchase',
      'Health supplement order (Order #MC-{n})',
    ],
  },
  {
    name: 'PetPals Supplies',
    category: 'Pet Care',
    minAmount: 20,
    maxAmount: 200,
    descriptionTemplates: [
      'Pet food & supplies order',
      'Grooming appointment charge',
      'Online order – Pet Accessories (Order #PP-{n})',
    ],
  },
  {
    name: 'SkySafe Insurance',
    category: 'Insurance',
    minAmount: 99,
    maxAmount: 800,
    descriptionTemplates: [
      'Monthly premium payment',
      'Annual policy renewal',
      'Supplemental coverage charge',
    ],
  },
];

const CARD_NETWORKS: CardNetwork[] = ['visa', 'mastercard', 'amex', 'discover'];

// ── Random helpers ────────────────────────────────────────────────────────────

function randInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randElement<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randAmount(min: number, max: number): number {
  return Math.round((Math.random() * (max - min) + min) * 100) / 100;
}

function isoDateDaysAgo(daysAgo: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

// ── Generator ─────────────────────────────────────────────────────────────────

/**
 * Generate `count` randomised demo transactions.
 *
 * Each call produces a fresh set: merchant, amount, date (within the last
 * 30 days), card network, and last-four digits are all independently
 * randomised. The resulting collision probability with any existing dedupe
 * key is negligible (random last-four × random amount × random date).
 */
export function generateDemoTransactions(count: number): DemoTransaction[] {
  const transactions: DemoTransaction[] = [];
  for (let i = 0; i < count; i++) {
    const merchant = randElement(MERCHANT_POOL);
    const network = randElement(CARD_NETWORKS);
    const template = randElement(merchant.descriptionTemplates);
    const refNum = randInt(10000, 99999);
    const description = template.replace('{n}', String(refNum));
    const amount = randAmount(merchant.minAmount, merchant.maxAmount);
    const date = isoDateDaysAgo(randInt(1, 30));
    const lastFour = String(randInt(1000, 9999));
    const id = `txn-${Date.now()}-${i}-${randInt(1000, 9999)}`;

    transactions.push({
      id,
      merchantName: merchant.name,
      merchantCategory: merchant.category,
      amount,
      currency: 'USD',
      date,
      cardLastFour: lastFour,
      cardNetwork: network,
      description,
    });
  }
  return transactions;
}

// ── Reason codes by network ───────────────────────────────────────────────────

export const reasonCodesByNetwork: Record<CardNetwork, ReasonCodeOption[]> = {
  visa: [
    { code: 'Visa 13.1', label: 'Merchandise/Services Not Received', network: 'visa' },
    { code: 'Visa 13.2', label: 'Cancelled Recurring Transaction', network: 'visa' },
    { code: 'Visa 12.5', label: 'Incorrect Amount', network: 'visa' },
    { code: 'Visa 10.4', label: 'Other Fraud — Card Absent', network: 'visa' },
    { code: 'Visa 12.6', label: 'Duplicate Processing', network: 'visa' },
    { code: 'Other', label: 'Other / I\'m not sure', network: 'visa' },
  ],
  mastercard: [
    { code: 'MC 4853', label: 'Cardholder Dispute — Defective/Not as Described', network: 'mastercard' },
    { code: 'MC 4855', label: 'Goods or Services Not Provided', network: 'mastercard' },
    { code: 'MC 4834', label: 'Duplicate Processing', network: 'mastercard' },
    { code: 'MC 4863', label: 'No Cardholder Authorization', network: 'mastercard' },
    { code: 'MC 4808', label: 'Authorization-Related Chargeback', network: 'mastercard' },
    { code: 'Other', label: 'Other / I\'m not sure', network: 'mastercard' },
  ],
  amex: [
    { code: 'Amex C08', label: 'Goods/Services Not Received', network: 'amex' },
    { code: 'Amex C02', label: 'Refund Not Received', network: 'amex' },
    { code: 'Amex C14', label: 'Already Paid Another Way', network: 'amex' },
    { code: 'Amex F10', label: 'Unauthorized Use — Card Not Present', network: 'amex' },
    { code: 'Amex A08', label: 'Authorization Approval Expired', network: 'amex' },
    { code: 'Other', label: 'Other / I\'m not sure', network: 'amex' },
  ],
  discover: [
    { code: 'Disc UA02', label: 'Fraud — Card Not Present', network: 'discover' },
    { code: 'Disc RG',   label: 'Non-Receipt of Goods/Services', network: 'discover' },
    { code: 'Disc AA',   label: 'Does Not Recognise', network: 'discover' },
    { code: 'Disc CD',   label: 'Credit Posted as a Purchase', network: 'discover' },
    { code: 'Other', label: 'Other / I\'m not sure', network: 'discover' },
  ],
};

/** Default cardholder name for demo pre-population. */
export const DEMO_CARDHOLDER_NAME = 'Alex Cardholder';
