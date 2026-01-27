import React from 'react'
import ReactDOM from 'react-dom/client'
import * as Sentry from '@sentry/react'
import { Providers } from './components/Providers'
import Dashboard from './dashboard'
import './globals.css'

function getOrCreateUserId(): string {
  const STORAGE_KEY = 'autoroad_user_id';
  let userId = localStorage.getItem(STORAGE_KEY);
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, userId);
  }
  return userId;
}

if (import.meta.env.VITE_SENTRY_DSN) {
  const apiUrl = import.meta.env.VITE_API_URL || ''
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    tunnel: `${apiUrl}/api/sentry-tunnel`,
    environment: import.meta.env.VITE_ENVIRONMENT || 'development',
    release: import.meta.env.VITE_RELEASE_VERSION,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: false,
        blockAllMedia: false,
      }),
    ],
    tracesSampleRate: 1.0,
    replaysSessionSampleRate: 1.0,
    replaysOnErrorSampleRate: 1.0,
  })
  
  Sentry.setUser({ id: getOrCreateUserId() });
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Providers>
      <Dashboard />
    </Providers>
  </React.StrictMode>,
)
