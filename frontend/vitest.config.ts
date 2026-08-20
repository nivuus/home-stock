import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/**/*.test.ts'],
    // Le fuseau de la maison (Europe/Paris — voir dlc.ts) : les tests
    // autour de minuit (raccourcisDlc) ne doivent pas dépendre du fuseau de
    // la machine qui les lance. Sans ce pin, la suite passe ici par hasard
    // (cet hôte est déjà à Paris) et échouerait sous TZ=UTC.
    env: { TZ: 'Europe/Paris' },
  },
});
