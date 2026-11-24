import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

const promptId = 'virtual:task-system-prompt'
const promptFile = fileURLToPath(new URL('../backend/app/prompts/task_parser.txt', import.meta.url))

export default defineConfig(({ mode }) => {
  const legacy = mode === 'legacy'
  const base = legacy ? '/' : process.env.PAGES_BASE_PATH || '/'
  return {
    base,
    plugins: [
      vue(), tailwindcss(),
      {
        name: 'task-system-prompt',
        resolveId(id) {
          if (id === promptId) return '\0' + promptId
        },
        load(id) {
          if (id === '\0' + promptId) {
            this.addWatchFile(promptFile)
            return 'export default ' + JSON.stringify(readFileSync(promptFile, 'utf8'))
          }
        },
      },
      !legacy && VitePWA({
        injectRegister: 'script-defer',
        manifest: {
          id: './', name: 'AI-Todo · 本地任务清单', short_name: 'AI-Todo',
          description: '记录、整理和管理保存在本机的个人任务',
          lang: 'zh-CN', display: 'standalone', start_url: './', scope: './',
          theme_color: '#405f4d', background_color: '#fafaf6',
          icons: [192, 512].map(size => ({
            src: 'icon-' + size + '.png', sizes: size + 'x' + size,
            type: 'image/png', purpose: 'any',
          })),
        },
        workbox: {
          // Every resource needed to read, edit and parse offline is in this build.
          globPatterns: ['**/*.{js,css,html,svg,png,webp}'],
          cleanupOutdatedCaches: true,
          navigateFallback: base + 'index.html',
        },
      }),
    ],
    build: { outDir: legacy ? 'dist' : 'dist-local' },
    server: {
      host: '127.0.0.1',
      proxy: legacy ? { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } } : undefined,
    },
  }
})
