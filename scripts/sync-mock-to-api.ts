/**
 * Syncs the frontend mock data → src/data/synthetic/cases.json
 * so the Flask dev server serves the same cases as the client-side fallback.
 *
 * Usage: npx tsx scripts/sync-mock-to-api.ts
 */
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mockCases } from '../src/web/src/mocks/cases.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const cases = Object.values(mockCases);
const outPath = resolve(__dirname, '..', 'src', 'data', 'synthetic', 'cases.json');

writeFileSync(outPath, JSON.stringify(cases, null, 2), 'utf-8');
console.log(`Wrote ${cases.length} cases to ${outPath}`);
