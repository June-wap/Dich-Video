import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components';
import { AppSettingsProvider } from './context/AppSettingsContext';
import {
  DashboardPage,
  TTSPage,
  VoiceCloningPage,
  VoicesPage,
  HistoryPage,
  SettingsPage,
} from './pages';

export function App() {
  return (
    <AppSettingsProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppShell />}>
            {/* Main Navigation Routes */}
            <Route index element={<DashboardPage />} />
            <Route path="tts" element={<TTSPage />} />
            <Route path="clone" element={<VoiceCloningPage />} />
            <Route path="voices" element={<VoicesPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="settings" element={<SettingsPage />} />
            {/* /showcase (internal design-system demo), /long-form,
                /projects, /projects/:id (dead since the Short-only scope
                decision - see pages/index.ts), and /diagnostics (17/09 -
                reveals which TTS model/GPU is running underneath, which the
                business does not want a customer to see) were removed here:
                none of them had a Sidebar entry any more, so a customer
                landing on one only by guessing the URL saw an
                internal/unfinished page with no way back except the
                browser's own Back button. */}

            {/* Catch-all fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppSettingsProvider>
  );
}

export default App;
