import type { PrecedentResult, PrecedentResultItem } from '../api/cases';

/**
 * Mock fallback for the Evidence Retrieval Agent (#12) precedent/rules search.
 *
 * Used when the app runs in mock mode (VITE_USE_MOCK=true) or when the live
 * /retrieve-precedents API is unreachable in local dev. Mirrors the shape of the
 * real Azure AI Search response so the PrecedentsPanel renders identically.
 */
export function mockPrecedentsFor(
  network: string | undefined,
  reasonCode: string,
  topK: number,
): PrecedentResult {
  const net = (network ?? 'visa').toLowerCase();
  const code = reasonCode.replace(/^(visa|mastercard|amex|discover)\s*/i, '').trim() || reasonCode;
  const label = net.toUpperCase();

  const items: PrecedentResultItem[] = [
    {
      id: `${net}-${code}-rule`,
      sourceType: 'network_rule',
      title: `${label} ${code} Rule Summary`,
      snippet:
        'Demo sample only. Focus the response package on authorization signals, authentication results, customer identity linkage, and fulfillment or usage evidence.',
      score: 3.1,
      rerankerScore: 2.61,
      citationLabel: `Demo ${label} ${code} Rule Summary`,
      sourceUrl: 'https://example.com/demo/rule',
      cardNetwork: net,
      reasonCode: code,
      tags: ['rule', 'demo'],
    },
    {
      id: `${net}-${code}-evidence`,
      sourceType: 'evidence_requirement',
      title: `${label} ${code} Evidence Requirements`,
      snippet:
        'Demo sample only. Useful evidence may include delivery confirmation, shipment tracking, signed proof of delivery, customer communications, and evidence the delivery address matched the order.',
      score: 4.0,
      rerankerScore: 2.81,
      citationLabel: `Demo ${label} ${code} Evidence Requirements`,
      sourceUrl: 'https://example.com/demo/evidence',
      cardNetwork: net,
      reasonCode: code,
      tags: ['evidence', 'demo'],
    },
    {
      id: `${net}-${code}-precedent`,
      sourceType: 'precedent',
      title: `Precedent - ${label} ${code} Carrier Delivery`,
      snippet:
        'Demo sample only. A merchant prevailed by providing carrier tracking that showed delivery to the verified address, a delivery timestamp before the dispute date, and customer support messages acknowledging the shipment.',
      score: 3.42,
      rerankerScore: 2.55,
      citationLabel: `Demo Precedent - ${label} ${code}`,
      sourceUrl: 'https://example.com/demo/precedent',
      cardNetwork: net,
      reasonCode: code,
      tags: ['precedent', 'demo'],
    },
  ].slice(0, topK);

  return {
    disputeId: '',
    network: net,
    reasonCode: code,
    results: items,
    rules: items.filter((i) => i.sourceType === 'network_rule'),
    evidenceRequirements: items.filter((i) => i.sourceType === 'evidence_requirement'),
    precedents: items.filter((i) => i.sourceType === 'precedent'),
    citations: items.map((i) => ({ label: i.citationLabel, url: i.sourceUrl })),
    topK,
    matchMode: 'exact',
    retrievedAt: new Date().toISOString(),
    source: 'mock',
    retrievalMode: 'keyword_semantic',
    usedVector: false,
  };
}
