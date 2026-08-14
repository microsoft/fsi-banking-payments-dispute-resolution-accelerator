import {
  Button,
  Dropdown,
  Option,
  Tab,
  TabList,
  Text,
  Textarea,
  Title2,
  tokens,
} from '@fluentui/react-components';
import { useMemo, useState } from 'react';
import { postNote } from '../api/cases';
import type { TimelineEvent } from '../types/case';
import { useNotifications } from './NotificationProvider';

export interface NoteEntry {
  id: string;
  text: string;
  author: string;
  timestamp: string;
  tags?: string[];
}

interface CollaborationWorkspaceProps {
  caseId: string;
  currentAnalystId?: string;
  currentAnalystName?: string;
  onAssign?: (analystId: string, analystName: string) => void;
  timelineEvents?: TimelineEvent[];
  onTimelineRefresh?: () => void;
}

// Mock data
const ANALYSTS = [
  { id: 'analyst-001', name: 'Sarah Chen' },
  { id: 'analyst-002', name: 'Marcus Rivera' },
  { id: 'analyst-003', name: 'Priya Patel' },
  { id: 'analyst-004', name: 'David Kim' },
  { id: 'analyst-005', name: 'Elena Rodriguez' },
];

const TEAMS = [
  { id: 'fraud', name: 'Fraud Team', icon: '🚨' },
  { id: 'compliance', name: 'Compliance', icon: '📋' },
  { id: 'legal', name: 'Legal', icon: '⚖️' },
  { id: 'management', name: 'Management', icon: '👔' },
];

type WorkspaceTab = 'assign' | 'notes' | 'tasks' | 'audit';

interface TaskEntry {
  id: string;
  title: string;
  assignee: string;
  status: 'open' | 'in_progress' | 'done';
  dueDate?: string;
}

const MOCK_TASKS: TaskEntry[] = [
  { id: 't1', title: 'Obtain signed delivery photo from merchant', assignee: 'Sarah Chen', status: 'done' },
  { id: 't2', title: 'Review compliance requirements for Reg E submission', assignee: 'Compliance', status: 'in_progress', dueDate: '2026-07-10' },
  { id: 't3', title: 'Manager approval for high-value representment', assignee: 'David Kim', status: 'open', dueDate: '2026-07-11' },
];

const AUDIT_FOCUS_EVENT_TYPES = new Set([
  'case_created',
  'status_change',
  'status_changed',
  'score_generated',
  'ai_draft_generated',
  'orchestration',
  'document_uploaded',
  'analyst_note',
  'comment_added',
  'customer_response',
  'customer_response_requested',
  'customer_response_received',
  'analyst_action',
  'case_closed_artifact_created',
  'evidence_retrieved',
  'evidence_gap_detected',
]);

function normalizeAuditToken(value: string): string {
  return (value || '').trim().toLowerCase();
}

function toAuditTitle(eventType: string): string {
  switch (normalizeAuditToken(eventType)) {
    case 'case_created':
      return 'Dispute Submitted';
    case 'score_generated':
      return 'AI Analysis Completed';
    case 'ai_draft_generated':
      return 'AI Draft Generated';
    case 'document_uploaded':
      return 'Evidence Added';
    case 'analyst_note':
    case 'comment_added':
      return 'Analyst Note Added';
    case 'customer_response':
      return 'Customer Note Added';
    case 'customer_response_requested':
      return 'Customer Response Requested';
    case 'customer_response_received':
      return 'Customer Response Received';
    case 'status_change':
    case 'status_changed':
      return 'Case Status Updated';
    case 'case_closed_artifact_created':
      return 'Decision Artifact Created';
    case 'orchestration':
      return 'Dispute Agent Orchestration';
    default:
      return eventType.replace(/_/g, ' ');
  }
}

function isNoiseEvent(eventType: string, actor: string, detail: string): boolean {
  const type = normalizeAuditToken(eventType);
  const who = normalizeAuditToken(actor);
  const desc = normalizeAuditToken(detail);

  // Suppress periodic stale reminders emitted by background refresh jobs.
  if (type === 'system_alert' && (desc.includes('no update for') || desc.includes('dispute stale'))) return true;
  if (who.includes('pipeline/master_refresh') && (type === 'system_alert' || desc.includes('no update for'))) return true;

  if (desc.includes('heartbeat') || desc.includes('periodic refresh')) return true;
  return false;
}

function isFocusedAuditEvent(eventType: string, actor: string, detail: string): boolean {
  if (isNoiseEvent(eventType, actor, detail)) return false;
  const normalizedType = normalizeAuditToken(eventType);
  if (AUDIT_FOCUS_EVENT_TYPES.has(normalizedType)) return true;

  const desc = normalizeAuditToken(detail);
  if (desc.includes('uploaded') || desc.includes('note') || desc.includes('comment')) return true;
  if (desc.includes('analysis') || desc.includes('score') || desc.includes('reprocessed')) return true;

  return false;
}

export function CollaborationWorkspace({
  caseId,
  currentAnalystId,
  currentAnalystName,
  onAssign,
  timelineEvents = [],
  onTimelineRefresh,
}: CollaborationWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('notes');
  const [selectedAnalystId, setSelectedAnalystId] = useState<string | undefined>(currentAnalystId);
  const { notifySuccess, notifyError } = useNotifications();
  const [newNote, setNewNote] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tasks] = useState<TaskEntry[]>(MOCK_TASKS);
  const [saving, setSaving] = useState(false);

  const normalizedTimeline = useMemo(() => {
    return [...timelineEvents]
      .map((ev) => {
        const withCompat = ev as TimelineEvent & {
          occurredAt?: string;
          detail?: string;
          data?: Record<string, unknown>;
          id?: string;
        };
        return {
          id: withCompat.eventId || withCompat.id || String(Math.random()),
          type: withCompat.eventType,
          actor: withCompat.actor || 'system',
          timestamp: withCompat.timestamp || withCompat.occurredAt || new Date().toISOString(),
          detail: withCompat.description || withCompat.detail || '',
          metadata: withCompat.metadata || withCompat.data || {},
        };
      })
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [timelineEvents]);

  const focusedAuditTimeline = useMemo(() => {
    return normalizedTimeline.filter((entry) =>
      isFocusedAuditEvent(entry.type, entry.actor, entry.detail)
    );
  }, [normalizedTimeline]);

  const nonNoiseAuditTimeline = useMemo(() => {
    return normalizedTimeline.filter((entry) =>
      !isNoiseEvent(entry.type, entry.actor, entry.detail)
    );
  }, [normalizedTimeline]);

  const visibleAuditTimeline = focusedAuditTimeline.length > 0
    ? focusedAuditTimeline
    : nonNoiseAuditTimeline;

  const notes = useMemo<NoteEntry[]>(() => {
    return normalizedTimeline
      .filter((ev) => ev.type === 'analyst_note' || ev.type === 'customer_response')
      .map((ev) => ({
        id: ev.id,
        text: ev.detail,
        author: ev.actor,
        timestamp: ev.timestamp,
        tags: ev.type === 'customer_response' ? ['customer'] : undefined,
      }));
  }, [normalizedTimeline]);

  const handleAssign = () => {
    if (!selectedAnalystId) return;
    const analyst = ANALYSTS.find((a) => a.id === selectedAnalystId);
    if (!analyst) return;
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      onAssign?.(analyst.id, analyst.name);
    }, 400);
  };

  const handleAddNote = async () => {
    if (!newNote.trim()) return;
    const noteText = newNote.trim();
    setNewNote('');
    setSelectedTags([]);

    try {
      await postNote(caseId, {
        analystId: currentAnalystId ?? 'demo-analyst',
        comment: noteText,
      });
      notifySuccess('Note saved', 'Note added to case timeline.');
      onTimelineRefresh?.();
    } catch {
      notifyError('Note failed', 'Note was not persisted to server.');
    }
  };

  return (
    <div>
      <Title2 style={{ marginBottom: '12px' }}>Collaboration</Title2>

      <TabList
        selectedValue={activeTab}
        onTabSelect={(_, data) => setActiveTab(data.value as WorkspaceTab)}
        size="small"
        style={{ marginBottom: '12px' }}
      >
        <Tab value="notes">💬 Notes</Tab>
        <Tab value="tasks">📋 Tasks</Tab>
        <Tab value="assign">👤 Assign</Tab>
        <Tab value="audit">📜 Audit Log</Tab>
      </TabList>

      {/* ── Notes Tab ── */}
      {activeTab === 'notes' && (
        <div>
          <Textarea
            placeholder="Add a note... @mention teams with tags below"
            value={newNote}
            onChange={(_, data) => setNewNote(data.value)}
            style={{ width: '100%', marginBottom: '8px' }}
            rows={2}
          />
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '8px' }}>
            {TEAMS.map((team) => (
              <button
                key={team.id}
                onClick={() => setSelectedTags(
                  selectedTags.includes(team.id)
                    ? selectedTags.filter((t) => t !== team.id)
                    : [...selectedTags, team.id]
                )}
                style={{
                  fontSize: '11px',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  border: `1px solid ${selectedTags.includes(team.id) ? tokens.colorBrandStroke1 : tokens.colorNeutralStroke2}`,
                  background: selectedTags.includes(team.id) ? tokens.colorBrandBackground2 : 'transparent',
                  cursor: 'pointer',
                  color: 'inherit',
                }}
              >
                {team.icon} {team.name}
              </button>
            ))}
          </div>
          <Button appearance="primary" size="small" disabled={!newNote.trim()} onClick={() => void handleAddNote()}>
            Add Note
          </Button>

          <div style={{ marginTop: '12px' }}>
            {notes.map((note) => (
              <div key={note.id} style={{ padding: '8px 10px', borderRadius: '6px', border: `1px solid ${tokens.colorNeutralStroke2}`, marginBottom: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <Text size={200} weight="semibold">{note.author}</Text>
                  <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                    {new Date(note.timestamp).toLocaleString()}
                  </Text>
                </div>
                <Text size={200} style={{ display: 'block' }}>{note.text}</Text>
                {note.tags && note.tags.length > 0 && (
                  <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                    {note.tags.map((tag) => {
                      const team = TEAMS.find((t) => t.id === tag);
                      return (
                        <span key={tag} style={{ fontSize: '10px', background: tokens.colorNeutralBackground3, padding: '1px 6px', borderRadius: '10px' }}>
                          {team?.icon} {team?.name ?? tag}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Tasks Tab ── */}
      {activeTab === 'tasks' && (
        <div>
          {tasks.map((task) => (
            <div key={task.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', borderRadius: '6px', border: `1px solid ${tokens.colorNeutralStroke2}`, marginBottom: '6px' }}>
              <span style={{ fontSize: '14px' }}>
                {task.status === 'done' ? '✅' : task.status === 'in_progress' ? '🔄' : '⬜'}
              </span>
              <div style={{ flex: 1 }}>
                <Text size={200} weight="semibold" style={{ textDecoration: task.status === 'done' ? 'line-through' : 'none' }}>
                  {task.title}
                </Text>
                <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>
                  {task.assignee}{task.dueDate ? ` · Due: ${task.dueDate}` : ''}
                </Text>
              </div>
              <span style={{
                fontSize: '10px',
                padding: '2px 6px',
                borderRadius: '3px',
                background: task.status === 'done' ? tokens.colorPaletteGreenBackground2
                  : task.status === 'in_progress' ? tokens.colorPaletteYellowBackground2
                    : tokens.colorNeutralBackground3,
                color: task.status === 'done' ? tokens.colorPaletteGreenForeground1
                  : task.status === 'in_progress' ? tokens.colorPaletteYellowForeground1
                    : tokens.colorNeutralForeground3,
              }}>
                {task.status === 'done' ? 'Done' : task.status === 'in_progress' ? 'In Progress' : 'Open'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Assign Tab ── */}
      {activeTab === 'assign' && (
        <div>
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
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
            <Dropdown
              placeholder="Select analyst..."
              value={ANALYSTS.find((a) => a.id === selectedAnalystId)?.name ?? ''}
              onOptionSelect={(_, data) => setSelectedAnalystId(data.optionValue)}
              style={{ minWidth: '180px' }}
            >
              {ANALYSTS.map((a) => (
                <Option key={a.id} value={a.id}>{a.name}</Option>
              ))}
            </Dropdown>
            <Button
              appearance="primary"
              size="small"
              disabled={!selectedAnalystId || selectedAnalystId === currentAnalystId || saving}
              onClick={handleAssign}
            >
              {saving ? 'Saving…' : currentAnalystId ? 'Reassign' : 'Assign'}
            </Button>
          </div>

          <Text size={200} weight="semibold" style={{ display: 'block', marginBottom: '6px' }}>
            Escalate to Team:
          </Text>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {TEAMS.map((team) => (
              <Button key={team.id} size="small" appearance="outline">
                {team.icon} {team.name}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* ── Audit Log Tab ── */}
      {activeTab === 'audit' && (
        <div>
          {visibleAuditTimeline.map((entry) => (
            <div key={entry.id} style={{ padding: '6px 0', borderBottom: `1px solid ${tokens.colorNeutralStroke2}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text size={200} weight="semibold">{toAuditTitle(entry.type)}</Text>
                <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                  {new Date(entry.timestamp).toLocaleString()}
                </Text>
              </div>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                {entry.actor}{entry.detail ? ` — ${entry.detail}` : ''}
              </Text>
            </div>
          ))}
          {visibleAuditTimeline.length === 0 && (
            <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
              No audit entries yet.
            </Text>
          )}
        </div>
      )}
    </div>
  );
}
