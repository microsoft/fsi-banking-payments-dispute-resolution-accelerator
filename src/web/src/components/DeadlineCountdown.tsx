import { Text } from '@fluentui/react-components';

interface DeadlineCountdownProps {
  daysRemaining: number;
  dueDate: string;
  closed?: boolean;
}

const colorMap = {
  danger: { background: '#fde7e9', color: '#c4314b', border: '#f3d6d8' },
  warning: { background: '#fff4ce', color: '#8a6914', border: '#ffe7a0' },
  success: { background: '#dff6dd', color: '#107c10', border: '#c8e6c9' },
};

export function DeadlineCountdown({ daysRemaining, dueDate, closed }: DeadlineCountdownProps) {
  if (closed) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: 600,
            lineHeight: '20px',
            whiteSpace: 'nowrap',
            background: colorMap.success.background,
            color: colorMap.success.color,
            border: `1px solid ${colorMap.success.border}`,
          }}
        >
          CLOSED
        </span>
        <Text size={200} style={{ color: '#666' }}>closed {dueDate}</Text>
      </span>
    );
  }

  let severity: 'danger' | 'warning' | 'success' = 'success';
  if (daysRemaining <= 0) severity = 'danger';
  else if (daysRemaining <= 3) severity = 'danger';
  else if (daysRemaining <= 7) severity = 'warning';

  const label = daysRemaining <= 0 ? 'OVERDUE' : `${daysRemaining}d left`;
  const colors = colorMap[severity];

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
      <span
        style={{
          display: 'inline-block',
          padding: '2px 10px',
          borderRadius: '12px',
          fontSize: '12px',
          fontWeight: 600,
          lineHeight: '20px',
          whiteSpace: 'nowrap',
          background: colors.background,
          color: colors.color,
          border: `1px solid ${colors.border}`,
        }}
      >
        {label}
      </span>
      <Text size={200} style={{ color: '#666' }}>due {dueDate}</Text>
    </span>
  );
}
