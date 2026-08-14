import { Text, Title3, tokens } from '@fluentui/react-components';
import type { ReasonCodeChecklistItem } from '../types/case';

interface ReasonCodeChecklistProps {
  reasonCode: string;
  reasonCodeLabel?: string;
  items: ReasonCodeChecklistItem[];
}

export function ReasonCodeChecklist({ reasonCode, reasonCodeLabel, items }: ReasonCodeChecklistProps) {
  const requiredUnsatisfied = items.filter((i) => i.required && !i.satisfied).length;
  const allRequired = items.filter((i) => i.required).length;
  const satisfiedRequired = allRequired - requiredUnsatisfied;

  return (
    <div>
      <Title3 style={{ marginBottom: '4px' }}>
        Reason Code Checklist — {reasonCode}
      </Title3>
      {reasonCodeLabel && (
        <Text size={300} style={{ color: '#666', display: 'block', marginBottom: '12px' }}>
          {reasonCodeLabel}
        </Text>
      )}
      <Text size={200} style={{ color: '#555', display: 'block', marginBottom: '12px' }}>
        Required items satisfied: {satisfiedRequired}/{allRequired}
      </Text>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {items.map((item, idx) => {
          const icon = item.satisfied ? '✅' : item.required ? '❌' : '⬜';
          const rowBg = !item.satisfied && item.required
            ? tokens.colorStatusDangerBackground1
            : item.satisfied
            ? tokens.colorStatusSuccessBackground1
            : undefined;

          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '8px 12px',
                borderRadius: '4px',
                background: rowBg,
              }}
            >
              <span style={{ fontSize: '16px' }}>{icon}</span>
              <Text style={{ flex: 1 }}>{item.item}</Text>
              {item.required && (
                <Text size={200} weight="semibold" style={{ color: '#666' }}>required</Text>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
