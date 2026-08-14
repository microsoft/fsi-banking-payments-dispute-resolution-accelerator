/**
 * Mock analyst profile data.
 *
 * TODO: Ask team whether this should come from the API (likely yes for production).
 * For demo purposes this is hardcoded. In production, the analyst profile would
 * be fetched from an auth/identity endpoint after login.
 */

export interface AnalystProfile {
  analystId: string;
  name: string;
  email: string;
  team: string;
  role: string;
  accounts: string[];  // Card networks / accounts this analyst handles
  avatarUrl?: string;
}

export const mockAnalyst: AnalystProfile = {
  analystId: 'analyst-001',
  name: 'Sarah Chen',
  email: 'sarah.chen@contosobank.com',
  team: 'Fraud & Disputes — Team Alpha',
  role: 'Senior Dispute Analyst',
  accounts: ['Visa', 'Mastercard', 'Amex', 'Discover'],
};
