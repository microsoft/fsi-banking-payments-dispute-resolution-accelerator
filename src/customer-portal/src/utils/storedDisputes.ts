import type { DisputeCreatedResponse } from '../types/dispute.ts';

const STORAGE_KEY = 'customer-filed-disputes';

export interface StoredDispute extends DisputeCreatedResponse {
  reasonLabel?: string;
  description?: string;
  analystComments?: AnalystComment[];
}

export interface AnalystComment {
  id: string;
  author: string;
  role: 'analyst' | 'system';
  message: string;
  timestamp: string;
  requiresAction?: boolean;
}

/**
 * Get all disputes stored in localStorage.
 */
export function getStoredDisputes(): StoredDispute[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredDispute[]) : [];
  } catch {
    return [];
  }
}

/**
 * Replace all stored disputes (used by API sync/polling updates).
 */
export function setStoredDisputes(disputes: StoredDispute[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(disputes));
}

/**
 * Save a newly filed dispute to localStorage.
 */
export function storeDispute(dispute: DisputeCreatedResponse, reasonLabel?: string, description?: string): void {
  const existing = getStoredDisputes();
  // Don't duplicate
  if (existing.some(d => d.disputeId === dispute.disputeId)) return;

  const stored: StoredDispute = {
    ...dispute,
    reasonLabel,
    description,
    analystComments: [],
  };
  existing.unshift(stored); // newest first
  setStoredDisputes(existing);
}

/**
 * Clear all stored disputes (for testing).
 */
export function clearStoredDisputes(): void {
  localStorage.removeItem(STORAGE_KEY);
}
