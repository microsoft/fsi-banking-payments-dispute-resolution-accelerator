import { tokens } from '@fluentui/react-components';
import type { CSSProperties } from 'react';

/** Reusable card style for all dashboard tiles */
export function cardStyle(overrides?: CSSProperties): CSSProperties {
  return {
    background: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: '12px',
    padding: '20px 24px',
    transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
    ...overrides,
  };
}

/** KPI accent colors for the top row */
export const kpiAccents = {
  blue: { bg: '#e8f4fd', border: '#0078d4', text: '#0078d4' },
  green: { bg: '#e6f9ed', border: '#107c41', text: '#107c41' },
  orange: { bg: '#fff4e5', border: '#ca5010', text: '#ca5010' },
  red: { bg: '#fde7e9', border: '#d13438', text: '#d13438' },
  purple: { bg: '#f3e8fd', border: '#8764b8', text: '#8764b8' },
  teal: { bg: '#e1f5f5', border: '#038387', text: '#038387' },
} as const;

/** Chart color palette — consistent across all visualizations */
export const chartColors = {
  primary: '#0078d4',
  secondary: '#038387',
  tertiary: '#8764b8',
  success: '#107c41',
  warning: '#ca5010',
  danger: '#d13438',
  muted: '#a0a0a0',
  visa: '#1a1f71',
  mastercard: '#eb001b',
  amex: '#006fcf',
  discover: '#ff6000',
};
