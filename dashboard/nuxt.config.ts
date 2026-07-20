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
    // market-district's HTTP read-model (order book + recent trades as JSON);
    // the /api/market/proof BFF route reads this. gRPC stays service-to-service.
    marketHttpUrl: process.env.MARKET_HTTP_URL ?? 'http://localhost:6060',
    tavernWsUrl: process.env.TAVERN_WS_URL ?? 'ws://localhost:3001',
    // tavern's HTTP read-model (recent content + gateway metrics); the
    // /api/tavern/content BFF reads this. Live delivery still rides the WS.
    tavernHttpUrl: process.env.TAVERN_HTTP_URL ?? 'http://localhost:3001',

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
