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
  },

  paths: {
    basePath: process.env.NODE_ENV === 'production' ? '/jam-conformance-dashboard' : '',
    backgroundImage: '/background.webp',
  },
};
