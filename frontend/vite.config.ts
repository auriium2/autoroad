import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { compression } from 'vite-plugin-compression2'
import path from 'path'
import { fileURLToPath } from 'url'
import { execSync } from 'child_process'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function getGitVersion(): string {
  try {
    const describe = execSync('git describe --tags --always', { encoding: 'utf-8' }).trim()
    if (describe.includes('-')) {
      // v0.1.0-15-gabcdef -> v0.1.0+15
      return describe.replace(/-(\d+)-g.*/, '+$1')
    }
    return describe.startsWith('v') ? describe : `v0.0.0+${describe}`
  } catch {
    // Fallback for Cloudflare Pages (shallow clone) - use commit hash from env
    const cfCommit = process.env.CF_PAGES_COMMIT_SHA?.slice(0, 7)
    if (cfCommit) return `v0.0.0+${cfCommit}`
    return 'v0.0.0+dev'
  }
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(getGitVersion()),
  },
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler', {}]],
      },
    }),
    tailwindcss(),
    compression({ algorithm: 'gzip' }),
    compression({ algorithm: 'brotliCompress' }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'ui-vendor': ['@radix-ui/react-dialog', '@radix-ui/react-popover', '@radix-ui/react-tooltip', '@radix-ui/react-dropdown-menu', '@radix-ui/react-select'],
          'reactflow': ['reactflow'],
          'tanstack': ['@tanstack/react-query', '@tanstack/react-virtual'],
          'sentry': ['@sentry/react'],
        },
      },
    },
  },
})
