import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components';
import {
  DashboardPage,
  TTSPage,
  LongFormPage,
  ProjectDetailPage,
  VoiceCloningPage,
  VoicesPage,
  ProjectsPage,
  HistoryPage,
  SettingsPage,
  DiagnosticsPage,
  ShowcasePage,
} from './pages';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          {/* Main Navigation Routes */}
          <Route index element={<DashboardPage />} />
          <Route path="tts" element={<TTSPage />} />
          <Route path="long-form" element={<LongFormPage />} />
          <Route path="long-form/:id" element={<ProjectDetailPage />} />
          <Route path="clone" element={<VoiceCloningPage />} />
          <Route path="voices" element={<VoicesPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="diagnostics" element={<DiagnosticsPage />} />
          <Route path="showcase" element={<ShowcasePage />} />

          {/* Catch-all fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
