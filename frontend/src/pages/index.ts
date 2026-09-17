export * from './DashboardPage';
export * from './TTSPage';
export * from './VoiceCloningPage';
export * from './VoicesPage';
export * from './HistoryPage';
export * from './SettingsPage';
export * from './DiagnosticsPage';
// LongFormPage, ProjectDetailPage, ProjectsPage and ShowcasePage are no
// longer exported here: none of them has a route in App.tsx or a Sidebar
// entry (Short TTS + Voice Cloning scope decision). Their .tsx files still
// exist under this folder - this session's device bridge could not delete
// files (see the project's engineering notes), so removing them from disk is
// a follow-up manual step: LongFormPage.tsx, ProjectDetailPage.tsx and
// ProjectsPage.tsx, ShowcasePage.tsx.
