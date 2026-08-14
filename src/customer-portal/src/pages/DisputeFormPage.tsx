import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Text,
  Title2,
  Body1,
  tokens,
  Button,
  Label,
  Input,
  Textarea,
  Dropdown,
  Option,
  MessageBar,
  MessageBarBody,
  Divider,
  Badge,
} from '@fluentui/react-components';
import { AppShell } from '../components/AppShell.tsx';
import { useWizard } from '../App.tsx';
import { reasonCodesByNetwork, DEMO_CARDHOLDER_NAME } from '../mocks/transactions.ts';
import { getPreferredCardholderName } from '../utils/customerProfile.ts';
import type { DisputeFormData } from '../types/dispute.ts';

export function DisputeFormPage() {
  const navigate = useNavigate();
  const { transaction, formData, setFormData } = useWizard();

  const [reasonCode, setReasonCode] = useState(formData?.reasonCode ?? '');
  const [cardholderName, setCardholderName] = useState(
    formData?.cardholderName ?? getPreferredCardholderName(DEMO_CARDHOLDER_NAME)
  );
  const [description, setDescription] = useState(formData?.description ?? '');
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Guard: redirect if no transaction selected
  useEffect(() => {
    if (!transaction) navigate('/');
  }, [transaction, navigate]);

  if (!transaction) return null;

  const reasonOptions = reasonCodesByNetwork[transaction.cardNetwork] ?? [];

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!reasonCode) errs.reasonCode = 'Please select a reason for the dispute.';
    if (!cardholderName.trim()) errs.cardholderName = 'Cardholder name is required.';
    if (!description.trim()) errs.description = 'Please describe the issue in a few words.';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function handleNext() {
    if (!validate()) return;
    const data: DisputeFormData = { reasonCode, cardholderName: cardholderName.trim(), description: description.trim() };
    setFormData(data);
    navigate('/upload');
  }

  return (
    <AppShell step={2}>
      <Button appearance="subtle" onClick={() => navigate('/')} style={{ marginBottom: tokens.spacingVerticalM }}>
        ← Back to transactions
      </Button>

      <Title2 style={{ marginBottom: tokens.spacingVerticalXS }}>Tell us about the dispute</Title2>
      <Body1 style={{ color: tokens.colorNeutralForeground2, marginBottom: tokens.spacingVerticalL, display: 'block' }}>
        Provide the details so we can process your chargeback request.
      </Body1>

      {/* Transaction summary */}
      <div
        style={{
          backgroundColor: tokens.colorNeutralBackground3,
          border: `1px solid ${tokens.colorNeutralStroke2}`,
          borderRadius: tokens.borderRadiusMedium,
          padding: tokens.spacingVerticalM,
          marginBottom: tokens.spacingVerticalXL,
          display: 'flex',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: tokens.spacingHorizontalM,
        }}
      >
        <div>
          <Text weight="semibold" size={400}>{transaction.merchantName}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>{transaction.description}</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
            {new Date(transaction.date + 'T00:00:00').toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
            {' · '}Card ending ···· {transaction.cardLastFour}
          </Text>
        </div>
        <div style={{ textAlign: 'right' }}>
          <Text weight="bold" size={500}>{new Intl.NumberFormat('en-US', { style: 'currency', currency: transaction.currency }).format(transaction.amount)}</Text>
          <Badge appearance="tint" color="informative" style={{ display: 'block', marginTop: tokens.spacingVerticalXS }}>
            {transaction.cardNetwork.charAt(0).toUpperCase() + transaction.cardNetwork.slice(1)}
          </Badge>
        </div>
      </div>

      <Divider style={{ marginBottom: tokens.spacingVerticalL }} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL }}>
        {/* Reason code */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS }}>
          <Label required htmlFor="reasonCode" weight="semibold">Reason for dispute</Label>
          <Dropdown
            id="reasonCode"
            placeholder="Select reason…"
            value={reasonOptions.find(r => r.code === reasonCode)?.label ?? ''}
            selectedOptions={reasonCode ? [reasonCode] : []}
            onOptionSelect={(_e, data) => setReasonCode(data.optionValue ?? '')}
            style={{ maxWidth: '480px' }}
          >
            {reasonOptions.map(opt => (
              <Option key={opt.code} value={opt.code} text={opt.label}>
                <Text size={300}><strong>{opt.code}</strong> — {opt.label}</Text>
              </Option>
            ))}
          </Dropdown>
          {errors.reasonCode && <Text size={200} style={{ color: tokens.colorStatusDangerForeground1 }}>{errors.reasonCode}</Text>}
        </div>

        {/* Cardholder name */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS }}>
          <Label required htmlFor="cardholderName" weight="semibold">Cardholder name</Label>
          <Input
            id="cardholderName"
            value={cardholderName}
            onChange={(_e, d) => setCardholderName(d.value)}
            style={{ maxWidth: '360px' }}
          />
          {errors.cardholderName && <Text size={200} style={{ color: tokens.colorStatusDangerForeground1 }}>{errors.cardholderName}</Text>}
        </div>

        {/* Description */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS }}>
          <Label required htmlFor="description" weight="semibold">Describe the issue</Label>
          <Textarea
            id="description"
            placeholder="e.g. I never received the item I ordered on June 15th…"
            value={description}
            onChange={(_e, d) => setDescription(d.value)}
            rows={4}
            style={{ maxWidth: '600px' }}
          />
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
            Be as specific as possible — this helps expedite your case.
          </Text>
          {errors.description && <Text size={200} style={{ color: tokens.colorStatusDangerForeground1 }}>{errors.description}</Text>}
        </div>
      </div>

      {Object.keys(errors).length > 0 && (
        <MessageBar intent="error" style={{ marginTop: tokens.spacingVerticalL }}>
          <MessageBarBody>Please fix the errors above before continuing.</MessageBarBody>
        </MessageBar>
      )}

      <div style={{ marginTop: tokens.spacingVerticalXXL, display: 'flex', gap: tokens.spacingHorizontalM }}>
        <Button appearance="secondary" onClick={() => navigate('/')}>Back</Button>
        <Button appearance="primary" onClick={handleNext}>Next: Upload Documents</Button>
      </div>
    </AppShell>
  );
}
