import {
  Button,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  Text,
  Textarea,
  Title3,
  tokens,
} from '@fluentui/react-components';
import { useState } from 'react';
import { postAction, postNote } from '../api/cases';
import type { CaseStatus } from '../types/case';
import type { NoteEntry } from './CollaborationWorkspace';
import { useNotifications } from './NotificationProvider';

interface ActionBarProps {
  caseId: string;
  currentStatus: CaseStatus;
  onActionComplete: (newStatus: CaseStatus) => void;
  onNoteAdded?: (note: NoteEntry) => void;
}

const TERMINAL_STATUSES: CaseStatus[] = ['approved', 'denied', 'escalated', 'submitted', 'expired'];

const STATUS_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  approved: { label: 'Approved', icon: '✓', color: '#107C10' },
  denied: { label: 'Denied', icon: '✗', color: '#C50F1F' },
  escalated: { label: 'Escalated', icon: '↑', color: '#5B5FC7' },
  submitted: { label: 'Submitted', icon: '📤', color: '#0078D4' },
  expired: { label: 'Expired', icon: '⏰', color: '#8A8886' },
};

export function ActionBar({ caseId, currentStatus, onActionComplete, onNoteAdded }: ActionBarProps) {
  const [analystId, setAnalystId] = useState('demo-analyst');
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { notifySuccess, notifyError } = useNotifications();

  const isTerminal = TERMINAL_STATUSES.includes(currentStatus);

  const handleAction = async (action: 'approve' | 'deny' | 'escalate' | 'reroute' | 'reopen') => {
    if (!analystId.trim()) {
      setError('Analyst ID is required.');
      return;
    }
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await postAction(caseId, action, {
        analystId: analystId.trim(),
        comment: comment.trim(),
      });
      setResult(res.status);
      onActionComplete(res.status as CaseStatus);
      setComment('');
      notifySuccess(
        `Case ${action}${action.endsWith('e') ? 'd' : 'ed'}`,
        `Case ${caseId.slice(0, 8)}… status updated to ${res.status.replace(/_/g, ' ')}.`
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Action failed. Please try again.';
      setError(msg);
      notifyError('Action failed', msg);
    } finally {
      setLoading(false);
    }
  };

  const handleAddNote = async () => {
    if (!analystId.trim()) {
      setError('Analyst ID is required.');
      return;
    }
    if (!comment.trim()) {
      setError('A comment is required to add a note.');
      return;
    }
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      await postNote(caseId, {
        analystId: analystId.trim(),
        comment: comment.trim(),
      });
      setResult('note_added');
      const noteEntry: NoteEntry = {
        id: `n-${Date.now()}`,
        text: comment.trim(),
        author: analystId.trim(),
        timestamp: new Date().toISOString(),
      };
      setComment('');
      onNoteAdded?.(noteEntry);
      notifySuccess('Note added', `Note saved to case ${caseId.slice(0, 8)}… timeline.`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add note. Please try again.';
      setError(msg);
      notifyError('Note failed', msg);
    } finally {
      setLoading(false);
    }
  };

  // Terminal status: show current decision + undo/reroute options
  if (isTerminal) {
    const statusInfo = STATUS_LABELS[currentStatus] ?? { label: currentStatus, icon: '•', color: '#555' };
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <Title3>Decision Recorded</Title3>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 16px',
            borderRadius: '8px',
            background: `${statusInfo.color}11`,
            border: `1px solid ${statusInfo.color}44`,
          }}
        >
          <span style={{ fontSize: '24px' }}>{statusInfo.icon}</span>
          <div style={{ flex: 1 }}>
            <Text weight="semibold" size={400} style={{ color: statusInfo.color }}>
              {statusInfo.label}
            </Text>
            <Text size={200} style={{ display: 'block', color: tokens.colorNeutralForeground3 }}>
              This case has been {currentStatus}. You can cancel this decision or reroute to another analyst.
            </Text>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <Field label="Comment (required for undo/reroute)" style={{ flex: '1 1 300px' }}>
            <Textarea
              value={comment}
              onChange={(_ev, data) => setComment(data.value)}
              placeholder="Reason for cancellation or reroute…"
              resize="vertical"
              rows={2}
              disabled={loading}
            />
          </Field>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            appearance="secondary"
            onClick={() => void handleAction('reopen')}
            disabled={loading || !comment.trim()}
            style={{ color: '#D83B01', borderColor: '#D83B01' }}
          >
            ↩ Cancel Decision
          </Button>
          <Button
            appearance="secondary"
            onClick={() => void handleAction('reroute')}
            disabled={loading || !comment.trim()}
            style={{ color: '#0078D4', borderColor: '#0078D4' }}
          >
            🔀 Reroute Case
          </Button>
          {loading && <Spinner size="tiny" label="Processing…" />}
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
            A comment is required to cancel or reroute.
          </Text>
        </div>

        {result && (
          <MessageBar intent="success">
            <MessageBarBody>
              <MessageBarTitle>Updated</MessageBarTitle>
              Case status changed to <strong>{result.replace(/_/g, ' ')}</strong>.
            </MessageBarBody>
          </MessageBar>
        )}

        {error && (
          <MessageBar intent="error">
            <MessageBarBody>
              <MessageBarTitle>Error</MessageBarTitle>
              {error}
            </MessageBarBody>
          </MessageBar>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Title3>Analyst Decision</Title3>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <Field label="Analyst ID" style={{ flex: '1 1 200px' }}>
          <Input
            value={analystId}
            onChange={(_ev, data) => setAnalystId(data.value)}
            placeholder="Your analyst ID"
            disabled={loading}
          />
        </Field>

        <Field label="Comment" style={{ flex: '2 1 300px' }}>
          <Textarea
            value={comment}
            onChange={(_ev, data) => setComment(data.value)}
            placeholder="Add a note or justification…"
            resize="vertical"
            rows={3}
            disabled={loading}
          />
        </Field>
      </div>

      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        <Button
          appearance="primary"
          onClick={() => void handleAction('approve')}
          disabled={loading}
          style={{ background: '#107C10', borderColor: '#107C10' }}
        >
          ✓ Approve
        </Button>
        <Button
          appearance="secondary"
          onClick={() => void handleAction('deny')}
          disabled={loading}
          style={{ color: '#C50F1F', borderColor: '#C50F1F' }}
        >
          ✗ Deny
        </Button>
        <Button
          appearance="subtle"
          onClick={() => void handleAction('escalate')}
          disabled={loading}
        >
          ↑ Escalate
        </Button>
        <Button
          appearance="secondary"
          onClick={() => void handleAddNote()}
          disabled={loading}
          style={{ color: '#0078D4', borderColor: '#0078D4' }}
        >
          📝 Update
        </Button>
        {loading && <Spinner size="tiny" label="Submitting…" />}
      </div>

      {result && (
        <MessageBar intent="success">
          <MessageBarBody>
            <MessageBarTitle>{result === 'note_added' ? 'Note added' : 'Decision recorded'}</MessageBarTitle>
            {result === 'note_added'
              ? <>Note saved to case timeline.</>
              : <>Case status updated to <strong>{result.replace(/_/g, ' ')}</strong>.</>
            }
          </MessageBarBody>
        </MessageBar>
      )}

      {error && (
        <MessageBar intent="error">
          <MessageBarBody>
            <MessageBarTitle>Error</MessageBarTitle>
            {error}
          </MessageBarBody>
        </MessageBar>
      )}
    </div>
  );
}
