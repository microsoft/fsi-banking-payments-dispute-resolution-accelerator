const CUSTOMER_ID_KEY = 'customer-portal-user-id';
const CUSTOMER_NAME_KEY = 'customer-portal-cardholder-name';

function newCustomerId(): string {
  const random = Math.random().toString(36).slice(2, 10);
  return `customer-${random}`;
}

export function getCustomerId(): string {
  const existing = localStorage.getItem(CUSTOMER_ID_KEY);
  if (existing) {
    return existing;
  }

  const created = newCustomerId();
  localStorage.setItem(CUSTOMER_ID_KEY, created);
  return created;
}

export function getPreferredCardholderName(defaultName: string): string {
  return localStorage.getItem(CUSTOMER_NAME_KEY) || defaultName;
}

export function setPreferredCardholderName(name: string): void {
  const trimmed = name.trim();
  if (!trimmed) return;
  localStorage.setItem(CUSTOMER_NAME_KEY, trimmed);
}
