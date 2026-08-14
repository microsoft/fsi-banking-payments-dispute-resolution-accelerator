import { Button, Dropdown, Option, Text, Title2, tokens } from '@fluentui/react-components';
import { useState } from 'react';

interface AssignRoutePanelProps {
  caseId: string;
  currentAnalystId?: string;
  currentAnalystName?: string;
  onAssign?: (analystId: string, analystName: string) => void;
}

// Mock list of analysts for routing/rerouting
const ANALYSTS = [
  { id: 'analyst-001', name: 'Sarah Chen' },
  { id: 'analyst-002', name: 'Marcus Rivera' },
  { id: 'analyst-003', name: 'Priya Patel' },
  { id: 'analyst-004', name: 'David Kim' },
  { id: 'analyst-005', name: 'Elena Rodriguez' },
];

export function AssignRoutePanel({
  caseId,
  currentAnalystId,
  currentAnalystName,
  onAssign,
}: AssignRoutePanelProps) {
  const [selectedId, setSelectedId] = useState<string | undefined>(currentAnalystId);
  const [saving, setSaving] = useState(false);

  const handleAssign = () => {
    if (!selectedId) return;
    const analyst = ANALYSTS.find((a) => a.id === selectedId);
    if (!analyst) return;

    setSaving(true);
    // TODO: In production, PATCH /api/cases/{caseId}/assign
    setTimeout(() => {
      setSaving(false);
      onAssign?.(analyst.id, analyst.name);
      console.info(`[AssignRoute] Case ${caseId} assigned to ${analyst.name}`);
    }, 400);
  };

  return (
    <div>
      <Title2 style={{ marginBottom: '12px' }}>Route / Assign</Title2>

      {currentAnalystName && (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '8px' }}>
          Currently assigned to: <strong>{currentAnalystName}</strong>
        </Text>
      )}

      {!currentAnalystName && (
        <Text size={200} style={{ color: tokens.colorPaletteYellowForeground1, display: 'block', marginBottom: '8px' }}>
          ⚠️ Unassigned — select an analyst to claim this case.
        </Text>
      )}

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Dropdown
          placeholder="Select analyst..."
          value={ANALYSTS.find((a) => a.id === selectedId)?.name ?? ''}
          onOptionSelect={(_, data) => setSelectedId(data.optionValue)}
          style={{ minWidth: '200px' }}
        >
          {ANALYSTS.map((a) => (
            <Option key={a.id} value={a.id}>
              {a.name}
            </Option>
          ))}
        </Dropdown>
        <Button
          appearance="primary"
          disabled={!selectedId || selectedId === currentAnalystId || saving}
          onClick={handleAssign}
        >
          {saving ? 'Saving…' : currentAnalystId ? 'Reassign' : 'Assign'}
        </Button>
      </div>
    </div>
  );
}
