import { FluentProvider, webLightTheme, webDarkTheme } from '@fluentui/react-components';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { DemoTransaction, DisputeFormData, DocumentMeta, DisputeCreatedResponse, CardNetwork } from './types/dispute.ts';
import { SelectTransactionPage } from './pages/SelectTransactionPage.tsx';
import { DisputeFormPage } from './pages/DisputeFormPage.tsx';
import { DocumentUploadPage } from './pages/DocumentUploadPage.tsx';
import { ReviewPage } from './pages/ReviewPage.tsx';
import { ConfirmationPage } from './pages/ConfirmationPage.tsx';
import { DisputeStatusPage } from './pages/DisputeStatusPage.tsx';
import { MyDisputesPage } from './pages/MyDisputesPage.tsx';

// ── Theme context ─────────────────────────────────────────────────────────────

interface ThemeContextValue {
  isDark: boolean;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({ isDark: false, toggleTheme: () => {} });

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}

// ── Account context (simulates single-bank portal) ────────────────────────────

export interface AccountInfo {
  network: CardNetwork;
  label: string;
  lastFour: string;
}

export const ACCOUNTS: AccountInfo[] = [
  { network: 'amex', label: 'American Express', lastFour: '3782' },
  { network: 'visa', label: 'Visa', lastFour: '4921' },
  { network: 'mastercard', label: 'Mastercard', lastFour: '5412' },
  { network: 'discover', label: 'Discover', lastFour: '6011' },
];

interface AccountContextValue {
  account: AccountInfo;
  setAccount: (a: AccountInfo) => void;
}

const AccountContext = createContext<AccountContextValue>({
  account: ACCOUNTS[0],
  setAccount: () => {},
});

export function useAccount(): AccountContextValue {
  return useContext(AccountContext);
}

// ── Wizard state ──────────────────────────────────────────────────────────────

export interface WizardState {
  transaction: DemoTransaction | null;
  formData: DisputeFormData | null;
  documents: DocumentMeta[];
  rawFiles: File[];
  submittedCase: DisputeCreatedResponse | null;
}

interface WizardContextValue extends WizardState {
  setTransaction: (t: DemoTransaction) => void;
  setFormData: (f: DisputeFormData) => void;
  setDocuments: (d: DocumentMeta[]) => void;
  setRawFiles: (f: File[]) => void;
  setSubmittedCase: (c: DisputeCreatedResponse) => void;
  reset: () => void;
}

const initialState: WizardState = {
  transaction: null,
  formData: null,
  documents: [],
  rawFiles: [],
  submittedCase: null,
};

const WizardContext = createContext<WizardContextValue | null>(null);

export function useWizard(): WizardContextValue {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error('useWizard must be used inside WizardProvider');
  return ctx;
}

function WizardProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WizardState>(initialState);

  const setTransaction = (transaction: DemoTransaction) =>
    // Selecting a charge starts a brand-new dispute flow.
    // This prevents stale form fields/documents from prior submissions
    // from carrying into a new entry.
    setState({
      ...initialState,
      transaction,
    });
  const setFormData = (formData: DisputeFormData) =>
    setState(s => ({ ...s, formData }));
  const setDocuments = (documents: DocumentMeta[]) =>
    setState(s => ({ ...s, documents }));
  const setRawFiles = (rawFiles: File[]) =>
    setState(s => ({ ...s, rawFiles }));
  const setSubmittedCase = (submittedCase: DisputeCreatedResponse) =>
    setState(s => ({ ...s, submittedCase }));
  const reset = () => setState(initialState);

  return (
    <WizardContext.Provider value={{ ...state, setTransaction, setFormData, setDocuments, setRawFiles, setSubmittedCase, reset }}>
      {children}
    </WizardContext.Provider>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [isDark, setIsDark] = useState(false);
  const toggleTheme = useCallback(() => setIsDark(d => !d), []);
  const [account, setAccount] = useState<AccountInfo>(ACCOUNTS[0]);

  return (
    <ThemeContext.Provider value={{ isDark, toggleTheme }}>
      <AccountContext.Provider value={{ account, setAccount }}>
        <FluentProvider theme={isDark ? webDarkTheme : webLightTheme}>
          <WizardProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<SelectTransactionPage />} />
                <Route path="/dispute" element={<DisputeFormPage />} />
                <Route path="/upload" element={<DocumentUploadPage />} />
                <Route path="/review" element={<ReviewPage />} />
                <Route path="/confirmation" element={<ConfirmationPage />} />
                <Route path="/status" element={<DisputeStatusPage />} />
                <Route path="/my-disputes" element={<MyDisputesPage />} />
            </Routes>
          </BrowserRouter>
        </WizardProvider>
      </FluentProvider>
      </AccountContext.Provider>
    </ThemeContext.Provider>
  );
}
