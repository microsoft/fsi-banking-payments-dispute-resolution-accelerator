import { FluentProvider, webDarkTheme, webLightTheme } from '@fluentui/react-components';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { NavBar } from './components/NavBar';
import { NotificationProvider } from './components/NotificationProvider';
import { CaseDetailPage } from './pages/CaseDetailPage';
import { DashboardPage } from './pages/DashboardPage';
import { ExecutiveMetricsPage } from './pages/ExecutiveMetricsPage';
import { QueuePage } from './pages/QueuePage';
import { ThemeProvider, useThemeMode } from './ThemeContext';

function AppShell() {
  const { mode } = useThemeMode();
  const theme = mode === 'dark' ? webDarkTheme : webLightTheme;

  return (
    <FluentProvider theme={theme} style={{ minHeight: '100vh', background: mode === 'dark' ? '#1a1a2e' : '#f5f6fa' }}>
      <NotificationProvider>
        <BrowserRouter>
          <NavBar />
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/queue" element={<QueuePage />} />
            <Route path="/cases" element={<QueuePage />} />
            <Route path="/metrics" element={<ExecutiveMetricsPage />} />
            <Route path="/cases/:caseId" element={<CaseDetailPage />} />
          </Routes>
        </BrowserRouter>
      </NotificationProvider>
    </FluentProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppShell />
    </ThemeProvider>
  );
}
