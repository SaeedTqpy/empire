import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
  {
    // shadcn/ui primitives intentionally co-locate component helpers and
    // generated variants. Keep the rest of ESLint active, but disable the two
    // React rules that conflict with the generated source shape.
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
      'react-hooks/purity': 'off',
    },
  },
  {
    // ViewerEngine extends Three.js prototypes and bridges addon types that do
    // not expose all runtime members. Preserve the upstream engine in phase 1
    // without weakening no-explicit-any for product/domain code.
    files: ['src/three/engine.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
])
