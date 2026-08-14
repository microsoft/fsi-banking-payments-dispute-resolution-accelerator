import {
  tokens,
  Text,
  Badge,
  Button,
  Select,
} from '@fluentui/react-components';
import { useNavigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useTheme, useAccount, ACCOUNTS } from '../App';

interface AppShellProps {
  children: ReactNode;
  step?: number;   // 1-4 for progress indicator; omit on confirmation
}

const STEPS = ['Select Transaction', 'Dispute Details', 'Documents', 'Review & Submit'];

export function AppShell({ children, step }: AppShellProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isDark, toggleTheme } = useTheme();
  const { account, setAccount } = useAccount();

  return (
    <div style={{ minHeight: '100vh', backgroundColor: tokens.colorNeutralBackground2, display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header
        style={{
          backgroundColor: tokens.colorBrandBackground,
          color: tokens.colorNeutralForegroundOnBrand,
          padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalXXL}`,
          display: 'flex',
          alignItems: 'center',
          gap: tokens.spacingHorizontalM,
          boxShadow: tokens.shadow4,
        }}
      >
        <span
          style={{ fontSize: '22px', cursor: 'pointer' }}
          onClick={() => navigate('/')}
          role="link"
          aria-label="Home"
        >🛡️</span>
        <div style={{ flex: 1 }}>
          <Text weight="bold" size={500} style={{ color: tokens.colorNeutralForegroundOnBrand }}>
            Dispute a Charge
          </Text>
          <Text size={200} style={{ color: tokens.colorNeutralForegroundOnBrand, opacity: 0.85, marginLeft: tokens.spacingHorizontalS }}>
            Secure Customer Portal
          </Text>
        </div>
        {/* Account selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS }}>
          <Text size={200} style={{ color: tokens.colorNeutralForegroundOnBrand, opacity: 0.8 }}>Account:</Text>
          <Select
            size="small"
            value={account.network}
            onChange={(_e, data) => {
              const selected = ACCOUNTS.find(a => a.network === data.value);
              if (selected) setAccount(selected);
            }}
            style={{ minWidth: '180px' }}
          >
            {ACCOUNTS.map(a => (
              <option key={a.network} value={a.network}>
                {a.label} ···· {a.lastFour}
              </option>
            ))}
          </Select>
        </div>
        <nav style={{ display: 'flex', gap: tokens.spacingHorizontalL, alignItems: 'center' }}>
          <Text
            size={300}
            weight={location.pathname === '/' ? 'bold' : 'regular'}
            style={{ color: tokens.colorNeutralForegroundOnBrand, cursor: 'pointer', opacity: location.pathname === '/' ? 1 : 0.85 }}
            onClick={() => navigate('/')}
            role="link"
          >
            Home
          </Text>
          <Text
            size={300}
            weight={location.pathname === '/my-disputes' ? 'bold' : 'regular'}
            style={{ color: tokens.colorNeutralForegroundOnBrand, cursor: 'pointer', opacity: location.pathname === '/my-disputes' ? 1 : 0.85 }}
            onClick={() => navigate('/my-disputes')}
            role="link"
          >
            My Disputes
          </Text>
          <Text
            size={300}
            weight={location.pathname === '/status' ? 'bold' : 'regular'}
            style={{ color: tokens.colorNeutralForegroundOnBrand, cursor: 'pointer', opacity: location.pathname === '/status' ? 1 : 0.85 }}
            onClick={() => navigate('/status')}
            role="link"
          >
            Check Status
          </Text>
          <Button
            appearance="subtle"
            size="small"
            onClick={toggleTheme}
            style={{ color: tokens.colorNeutralForegroundOnBrand, minWidth: 'auto' }}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? '☀️' : '🌙'}
          </Button>
        </nav>
      </header>

      {/* Step progress */}
      {step !== undefined && (
        <div
          style={{
            backgroundColor: tokens.colorNeutralBackground1,
            borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
            padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalXXL}`,
            display: 'flex',
            gap: tokens.spacingHorizontalL,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          {STEPS.map((label, i) => {
            const stepNum = i + 1;
            const isActive = stepNum === step;
            const isDone = stepNum < step;
            return (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalXS }}>
                <Badge
                  appearance={isActive ? 'filled' : isDone ? 'tint' : 'outline'}
                  color={isActive ? 'brand' : isDone ? 'success' : 'subtle'}
                  size="medium"
                >
                  {isDone ? '✓' : stepNum}
                </Badge>
                <Text
                  size={200}
                  weight={isActive ? 'semibold' : 'regular'}
                  style={{ color: isActive ? tokens.colorBrandForeground1 : isDone ? tokens.colorStatusSuccessForeground1 : tokens.colorNeutralForeground3 }}
                >
                  {label}
                </Text>
                {i < STEPS.length - 1 && (
                  <span style={{ color: tokens.colorNeutralStroke1, marginLeft: tokens.spacingHorizontalXS }}>›</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Main content */}
      <main
        style={{
          flex: 1,
          padding: `${tokens.spacingVerticalXXL} ${tokens.spacingHorizontalXXL}`,
          maxWidth: '860px',
          width: '100%',
          margin: '0 auto',
          boxSizing: 'border-box',
        }}
      >
        {children}
      </main>

      {/* Footer */}
      <footer
        style={{
          borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
          padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalXXL}`,
          textAlign: 'center',
        }}
      >
        <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
          This portal is secured and your data is protected. For urgent matters call 1-800-DISPUTES.
        </Text>
      </footer>
    </div>
  );
}
