# ─── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install

# Copy source
COPY . .

# Build Nuxt app
ENV NODE_ENV=production
RUN npm run build

# ─── Stage 2: Production ──────────────────────────────────────────────────────
FROM node:22-alpine AS production

WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nuxtjs

# Copy built output
COPY --from=builder --chown=nuxtjs:nodejs /app/.output ./.output

USER nuxtjs

# Runtime env vars (overrideable at deploy)
ENV HOST=0.0.0.0
ENV PORT=3000
ENV NODE_ENV=production

# API URLs (override at runtime)
ENV TOWN_CORE_URL=http://town-core:8000
ENV ACADEMY_URL=http://academy:8001
ENV CARTOGRAPHER_URL=http://cartographer:4000
ENV TAVERN_WS_URL=ws://tavern:3001

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
