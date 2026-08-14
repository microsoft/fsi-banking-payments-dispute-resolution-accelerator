import {
  Avatar,
  Badge,
  Button,
  Text,
  Title3,
  tokens,
} from '@fluentui/react-components';
import { useThemeMode } from '../ThemeContext';
import type { AnalystProfile } from '../mocks/analyst';

interface AnalystHeaderProps {
  analyst: AnalystProfile;
  activeNetwork: string | null;
  onNetworkFilter: (network: string | null) => void;
}

export function AnalystHeader({ analyst, activeNetwork, onNetworkFilter }: AnalystHeaderProps) {
  const { mode, toggle } = useThemeMode();

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        padding: '16px 24px',
        background: tokens.colorNeutralBackground1,
        borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
      }}
    >
      <Avatar
        name={analyst.name}
        size={48}
        color="brand"
        image={analyst.avatarUrl ? { src: analyst.avatarUrl } : undefined}
      />
      <div style={{ flex: 1 }}>
        <Title3 style={{ margin: 0 }}>{analyst.name}</Title3>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>
          {analyst.role} · {analyst.team}
        </Text>
      </div>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
        {analyst.accounts.map((acct) => {
          const isActive = activeNetwork?.toLowerCase() === acct.toLowerCase();
          return (
            <button
              key={acct}
              onClick={() => onNetworkFilter(isActive ? null : acct)}
              style={{
                all: 'unset',
                cursor: 'pointer',
              }}
            >
              <Badge
                appearance={isActive ? 'filled' : 'outline'}
                color={isActive ? 'brand' : 'informative'}
                style={{ pointerEvents: 'none' }}
              >
                {acct}
              </Badge>
            </button>
          );
        })}
        <Button
          appearance="subtle"
          icon={<span style={{ fontSize: '18px' }}>{mode === 'light' ? '🌙' : '☀️'}</span>}
          onClick={toggle}
          title={`Switch to ${mode === 'light' ? 'dark' : 'light'} mode`}
        />
      </div>
    </div>
  );
}
