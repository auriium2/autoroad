import React from 'react'
import ReactDOM from 'react-dom/client'
import { Providers } from './components/Providers'
import Dashboard from './dashboard'
import './globals.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Providers>
      <Dashboard />
    </Providers>
  </React.StrictMode>,
)
