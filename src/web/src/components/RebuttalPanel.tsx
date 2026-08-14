import { Text, Title3, tokens } from '@fluentui/react-components';
import type { RebuttalDraft } from '../types/case';

interface RebuttalPanelProps {
  rebuttal: RebuttalDraft;
}

export function RebuttalPanel({ rebuttal }: RebuttalPanelProps) {
  return (
    <div>
      <Title3 style={{ marginBottom: '12px' }}>AI-Drafted Rebuttal</Title3>
      <div
        style={{
          padding: '16px',
          background: tokens.colorNeutralBackground2,
          borderRadius: '6px',
          marginBottom: '16px',
          lineHeight: 1.6,
        }}
      >
        <Text>{rebuttal.text}</Text>
      </div>

      {rebuttal.citations.length > 0 && (
        <div>
          <Text weight="semibold" size={300} style={{ marginBottom: '8px', display: 'block' }}>
            Source Citations
          </Text>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {rebuttal.citations.map((c, idx) => (
              <div
                key={idx}
                style={{
                  padding: '8px 12px',
                  background: tokens.colorNeutralBackground3,
                  borderRadius: '4px',
                  borderLeft: `3px solid ${tokens.colorBrandBackground}`,
                }}
              >
                <Text size={200} style={{ fontFamily: 'monospace', display: 'block', color: '#666' }}>
                  [{c.evidenceId}]
                </Text>
                <Text size={300}>{c.excerpt}</Text>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
