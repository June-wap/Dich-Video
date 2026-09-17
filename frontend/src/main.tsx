import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { getLocalToken } from './services/localToken'

const root = createRoot(document.getElementById('root')!)

// Security P0 (checklist-bao-mat-truoc-dong-goi-17-09.md item 1): every
// backend call needs the local session token, only known once
// GET /api/auth/token answers (see ./services/localToken.ts) - hold the
// very first render here so AppSettingsProvider/TTSPage's own first API
// calls never race that bootstrap fetch.
root.render(
  <p style={{ padding: 24, fontFamily: 'sans-serif' }}>Đang kết nối tới backend cục bộ...</p>,
)

getLocalToken()
  .then(() => {
    root.render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  })
  .catch((err: unknown) => {
    const message = err instanceof Error ? err.message : 'Không thể kết nối tới backend cục bộ.'
    root.render(
      <p style={{ padding: 24, fontFamily: 'sans-serif', color: '#b91c1c' }} role="alert">
        {message}
      </p>,
    )
  })
