export const APP_CONFIG = {
  defaultVersion: '0.7.2',

  lanes: {
    available: ['L2a', 'L2b', 'L3a', 'L3b'],
    displayNames: {
      L2a: 'L2a',
      L2b: 'L2b',
      L3a: 'L3a',
      L3b: 'L3b',
    },
  },

  externalLinks: {
    jamConformance: 'https://github.com/davxy/jam-conformance',
    graypaperClients: 'https://graypaper.com/clients/',
    viblyNetwork: 'https://vibly.network/',
  },

  paths: {
    basePath: (process.env.NEXT_PUBLIC_BASE_PATH || '').replace(/\/$/, ''),
    backgroundImage: '/background.webp',
  },
};
