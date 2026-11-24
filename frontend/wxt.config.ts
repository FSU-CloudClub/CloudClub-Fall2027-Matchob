import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Matchob',
    host_permissions: ['http://localhost/*', 'http://127.0.0.1/*'],
    description: 'AI-powered resume tailoring',
  },
});
