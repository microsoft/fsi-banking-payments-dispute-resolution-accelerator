import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Text,
  Title2,
  Body1,
  tokens,
  Badge,
  Button,
  Subtitle2,
} from '@fluentui/react-components';
import { AppShell } from '../components/AppShell.tsx';
import { useWizard, useAccount } from '../App.tsx';
import { generateDemoTransactions } from '../mocks/transactions.ts';
import { getDisputedKeys, buildTransactionKey } from '../utils/disputedTransactions.ts';
import type { DemoTransaction } from '../types/dispute.ts';

const TARGET_COUNT = 6;

const NETWORK_LABELS: Record<string, string> = {
  visa: 'Visa',
  mastercard: 'Mastercard',
  amex: 'American Express',
  discover: 'Discover',
};

function formatAmount(amount: number, currency: string) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}

function formatDate(date: string) {
  return new Date(date + 'T00:00:00').toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

export function SelectTransactionPage() {
  const navigate = useNavigate();
  const { setTransaction, reset } = useWizard();
  const { account } = useAccount();

  // Always start fresh when landing on transaction selection
  useEffect(() => { reset(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // Regenerate transactions when account changes, all with the selected network
  const [transactions, setTransactions] = useState<DemoTransaction[]>(() => buildTransactions(account.network, account.lastFour));

  useEffect(() => {
    setTransactions(buildTransactions(account.network, account.lastFour));
  }, [account]);

  function handleSelect(txn: DemoTransaction) {
    setTransaction(txn);
    navigate('/dispute');
  }

  return (
    <AppShell step={1}>
      <Title2 style={{ marginBottom: tokens.spacingVerticalS }}>Select the charge to dispute</Title2>
      <Body1 style={{ color: tokens.colorNeutralForeground2, marginBottom: tokens.spacingVerticalXL, display: 'block' }}>
        Review your recent {NETWORK_LABELS[account.network]} activity below and select the transaction you wish to dispute.
      </Body1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM }}>
        {transactions.map(txn => (
          <TransactionCard key={txn.id} transaction={txn} onSelect={handleSelect} />
        ))}
      </div>

      <div
        style={{
          marginTop: tokens.spacingVerticalXL,
          padding: tokens.spacingVerticalM,
          backgroundColor: tokens.colorNeutralBackground3,
          borderRadius: tokens.borderRadiusMedium,
          border: `1px solid ${tokens.colorNeutralStroke2}`,
        }}
      >
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          <strong>Demo mode:</strong> These are sample transactions for your {NETWORK_LABELS[account.network]} account. In production this list would come from your card account history.
        </Text>
      </div>
    </AppShell>
  );
}

/** Generate filtered transactions for a single card account. */
function buildTransactions(network: string, lastFour: string): DemoTransaction[] {
  const disputed = getDisputedKeys();
  const candidates = generateDemoTransactions(TARGET_COUNT + disputed.size + 6);
  // Override each transaction to use the selected network and card
  const stamped = candidates.map(txn => ({
    ...txn,
    cardNetwork: network as DemoTransaction['cardNetwork'],
    cardLastFour: lastFour,
  }));
  return stamped
    .filter(txn => !disputed.has(buildTransactionKey(txn)))
    .slice(0, TARGET_COUNT);
}

function TransactionCard({ transaction: txn, onSelect }: { transaction: DemoTransaction; onSelect: (t: DemoTransaction) => void }) {
  return (
    <button
      onClick={() => onSelect(txn)}
      style={{
        background: tokens.colorNeutralBackground1,
        border: `1px solid ${tokens.colorNeutralStroke1}`,
        borderRadius: tokens.borderRadiusMedium,
        padding: tokens.spacingVerticalM,
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'box-shadow 0.12s, border-color 0.12s',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: tokens.spacingHorizontalM,
        flexWrap: 'wrap',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLButtonElement).style.boxShadow = tokens.shadow8;
        (e.currentTarget as HTMLButtonElement).style.borderColor = tokens.colorBrandStroke1;
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLButtonElement).style.boxShadow = 'none';
        (e.currentTarget as HTMLButtonElement).style.borderColor = tokens.colorNeutralStroke1;
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' }}>
          <Subtitle2>{txn.merchantName}</Subtitle2>
          <Badge appearance="outline" color="subtle" size="small">
            ···· {txn.cardLastFour}
          </Badge>
        </div>
        <Text size={300} style={{ color: tokens.colorNeutralForeground2 }}>{txn.description}</Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          {txn.merchantCategory} · {formatDate(txn.date)}
        </Text>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: tokens.spacingVerticalXS }}>
        <Text weight="bold" size={500} style={{ color: tokens.colorNeutralForeground1 }}>
          {formatAmount(txn.amount, txn.currency)}
        </Text>
        <Button appearance="primary" size="small">Dispute this charge</Button>
      </div>
    </button>
  );
}
