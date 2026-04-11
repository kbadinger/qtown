// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  ssr: true,

  modules: [
    '@nuxtjs/tailwindcss',
    '@pinia/nuxt',
    '@nuxt/image',
  ],

  typescript: {
    strict: true,
    typeCheck: false, // set true to enable full type checking in build
  },

  runtimeConfig: {
    // Server-side only
    townCoreUrl: process.env.TOWN_CORE_URL ?? 'http://localhost:8000',
    academyUrl: process.env.ACADEMY_URL ?? 'http://localhost:8001',
    cartographerUrl: process.env.CARTOGRAPHER_URL ?? 'http://localhost:4000',
    tavernWsUrl: process.env.TAVERN_WS_URL ?? 'ws://localhost:3001',

    // Public (exposed to client)
    public: {
      townCoreUrl: process.env.NUXT_PUBLIC_TOWN_CORE_URL ?? 'http://localhost:8000',
      academyUrl: process.env.NUXT_PUBLIC_ACADEMY_URL ?? 'http://localhost:8001',
      cartographerUrl: process.env.NUXT_PUBLIC_CARTOGRAPHER_URL ?? 'http://localhost:4000',
      tavernWsUrl: process.env.NUXT_PUBLIC_TAVERN_WS_URL ?? 'ws://localhost:3001',
      graphqlUrl: process.env.NUXT_PUBLIC_GRAPHQL_URL ?? 'http://localhost:4000/graphql',
    },
  },

  nitro: {
    experimental: {
      websocket: true,
    },
  },

  app: {
    head: {
      title: 'Qtown Dashboard',
      meta: [
        { name: 'description', content: 'Qtown v2 — Medieval AI Town Dashboard' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      link: [
        { rel: 'icon', href: '/favicon.ico' },
      ],
    },
  },

  css: ['~/assets/css/main.css'],

  vite: {
    optimizeDeps: {
      include: ['chart.js', 'vue-chartjs'],
    },
  },
})
