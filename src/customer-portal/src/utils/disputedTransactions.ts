import type { DemoTransaction } from '../types/dispute.ts';

const STORAGE_KEY = 'disputed-transactions';

function getDisputedIds(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
  } catch {
    return new Set();
  }
}

export function markTransactionDisputed(tx: DemoTransaction): void {
  const ids = getDisputedIds();
  ids.add(tx.id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}

export function isTransactionDisputed(txId: string): boolean {
  return getDisputedIds().has(txId);
}

const KEYS_STORAGE_KEY = 'disputed-transaction-keys';

export function buildTransactionKey(tx: DemoTransaction): string {
  return `${tx.id}_${tx.date}_${tx.amount}`;
}

export function getDisputedKeys(): Set<string> {
  try {
    const raw = localStorage.getItem(KEYS_STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
  } catch {
    return new Set();
  }
}

export function markTransactionKeyDisputed(tx: DemoTransaction): void {
  const keys = getDisputedKeys();
  keys.add(buildTransactionKey(tx));
  localStorage.setItem(KEYS_STORAGE_KEY, JSON.stringify([...keys]));
}
