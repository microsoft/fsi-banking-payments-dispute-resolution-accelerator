import {
  Avatar,
  Text,
  tokens,
} from '@fluentui/react-components';
import { useLocation, useNavigate } from 'react-router-dom';

const NAV_LINKS = [
  { label: 'Dashboard', path: '/' },
  { label: 'Queue', path: '/queue' },
  { label: 'Metrics', path: '/metrics' },
];

export function NavBar() {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <nav
      style={{
        height: '48px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
        background: tokens.colorNeutralBackground1,
        position: 'sticky',
        top: 0,
        zIndex: 1000,
      }}
    >
      {/* Left: Logo + App Name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <Text
          weight="semibold"
          size={400}
          style={{ cursor: 'pointer', whiteSpace: 'nowrap' }}
          onClick={() => navigate('/')}
        >
          ⚖️ Dispute Resolution
        </Text>

        {/* Nav links */}
        <div style={{ display: 'flex', gap: '4px', marginLeft: '16px' }}>
          {NAV_LINKS.map((link) => (
            <button
              key={link.path}
              onClick={() => navigate(link.path)}
              style={{
                background: isActive(link.path) ? tokens.colorBrandBackground2 : 'transparent',
                border: 'none',
                borderRadius: '6px',
                padding: '6px 14px',
                cursor: 'pointer',
                color: isActive(link.path) ? tokens.colorBrandForeground1 : tokens.colorNeutralForeground2,
                fontWeight: isActive(link.path) ? 600 : 400,
                fontSize: '13px',
                fontFamily: 'var(--fontFamilyBase)',
                transition: 'background 0.15s, color 0.15s',
              }}
            >
              {link.label}
            </button>
          ))}
        </div>
      </div>

      {/* Right: Analyst */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          Sarah Chen
        </Text>
        <Avatar name="Sarah Chen" size={28} color="brand" />
      </div>
    </nav>
  );
}
