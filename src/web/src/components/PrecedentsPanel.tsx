import {
  Badge,
  Divider,
  Link,
  MessageBar,
  MessageBarBody,
  Spinner,
  Text,
  Title3,
  tokens,
} from '@fluentui/react-components';
import type { BadgeProps } from '@fluentui/react-components';
import { useEffect, useState } from 'react';
import { retrievePrecedents } from '../api/cases';
import type { PrecedentResult, PrecedentResultItem } from '../api/cases';

interface PrecedentsPanelProps {
  caseId: string;
  network?: string;
  reasonCode: string;
}

type BadgeColor = BadgeProps['color'];

const SOURCE_TYPE_META: Record<string, { label: string; icon: string; color: BadgeColor }> = {
  network_rule: { label: 'Rule', icon: '📓', color: 'brand' },
  evidence_requirement: { label: 'Evidence Req', icon: '📋', color: 'informative' },
  precedent: { label: 'Precedent', icon: '⚖️', color: 'success' },
};

function relevance(item: PrecedentResultItem): string | null {
  const s = item.rerankerScore ?? item.score;
  return typeof s === 'number' ? s.toFixed(2) : null;
}

function ResultCard({ item }: { item: PrecedentResultItem }) {
  const meta = SOURCE_TYPE_META[item.sourceType] ?? {
    label: item.sourceType,
    icon: '📄',
    color: 'informative' as BadgeColor,
  };
  const rel = relevance(item);
  return (
    <div
      style={{
        border: `1px solid ${tokens.colorNeutralStroke2}`,
        borderRadius: '6px',
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <Badge appearance="tint" color={meta.color}>
          {meta.icon} {meta.label}
        </Badge>
        <Text weight="semibold" size={300}>
          {item.title}
        </Text>
        {rel && (
          <span style={{ marginLeft: 'auto' }}>
            <Badge appearance="outline" color="informative">
              relevance {rel}
            </Badge>
          </span>
        )}
      </div>
      <Text size={200} style={{ color: tokens.colorNeutralForeground2 }}>
        {item.snippet}
      </Text>
      {item.citationLabel && (
        <Link href={item.sourceUrl} target="_blank" rel="noreferrer" style={{ fontSize: '12px' }}>
          {item.citationLabel}
        </Link>
      )}
    </div>
  );
}

function SourceBadge({ source }: { source: string }) {
  if (source === 'search' || source === 'agent') {
    return (
      <Badge appearance="tint" color="success">
        🔍 Live · AI Search
      </Badge>
    );
  }
  if (source === 'mock') {
    return (
      <Badge appearance="tint" color="warning">
        Sample data
      </Badge>
    );
  }
  return (
    <Badge appearance="tint" color="subtle">
      No live index
    </Badge>
  );
}

export function PrecedentsPanel({ caseId, network, reasonCode }: PrecedentsPanelProps) {
  const [data, setData] = useState<PrecedentResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    retrievePrecedents(caseId, network, reasonCode)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, network, reasonCode]);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <Title3>Precedents &amp; Network Rules</Title3>
        {data && <SourceBadge source={data.source} />}
        {data && data.results.length > 0 && data.usedVector && (
          <Badge appearance="tint" color="success">
            ⚡ Hybrid (vector)
          </Badge>
        )}
        {data && data.results.length > 0 && (
          <Badge appearance="outline" color="informative">
            match: {data.matchMode}
          </Badge>
        )}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
          <Spinner size="tiny" label="Retrieving precedents…" />
        </div>
      ) : !data || data.results.length === 0 ? (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          No matching rules or precedents found for this reason code.
        </Text>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {data.rationale && (
            <MessageBar intent="info">
              <MessageBarBody>{data.rationale}</MessageBarBody>
            </MessageBar>
          )}
          {data.results.map((item) => (
            <ResultCard key={item.id} item={item} />
          ))}
          {data.citations.length > 0 && (
            <>
              <Divider />
              <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                {data.citations.length} source citation{data.citations.length === 1 ? '' : 's'} · retrieved{' '}
                {new Date(data.retrievedAt).toLocaleString()}
              </Text>
            </>
          )}
        </div>
      )}
    </div>
  );
}
