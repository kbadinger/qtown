<script setup lang="ts">
definePageMeta({ layout: 'docs' })
useHead({ title: 'Introduction' })

interface TechRow {
  layer: string
  technology: string
  purpose: string
}

const techStack: TechRow[] = [
  { layer: 'Simulation Engine', technology: 'Python 3.12, asyncio', purpose: 'Tick loop, world state, NPC orchestration' },
  { layer: 'AI / LLM', technology: 'OpenAI GPT-4o, GPT-4o-mini', purpose: 'NPC decision-making, newspaper generation, quest creation' },
  { layer: 'Market', technology: 'Go 1.22, limit-order matching', purpose: 'High-throughput order book, price discovery, tournaments' },
  { layer: 'Validation', technology: 'Go 1.22, gRPC', purpose: 'Rule enforcement, audit log, event filtering' },
  { layer: 'GraphQL Gateway', technology: 'Node.js, Apollo Server 4', purpose: 'Unified API surface for the dashboard' },
  { layer: 'Real-time Bus', technology: 'Apache Kafka 3.7, Redpanda-compatible', purpose: 'Event streaming between all services' },
  { layer: 'Presence / Cache', technology: 'Redis 7, Pub/Sub', purpose: 'Live NPC positions, WebSocket fan-out' },
  { layer: 'Dashboard', technology: 'Nuxt 3, Vue 3, Tailwind CSS', purpose: 'Admin UI, docs, visitor mode, SLA monitoring' },
  { layer: 'Search', technology: 'Python, PostgreSQL full-text', purpose: 'NPC history, newspaper archive, event log' },
  { layer: 'Spatial', technology: 'Python, tile-based grid', purpose: 'Pathfinding, zone management, travel simulation' },
]

interface QuickLink {
  href: string
  title: string
  description: string
  icon: string
}

const quickLinks: QuickLink[] = [
  { href: '/docs/architecture', title: 'Architecture', description: 'Service topology, communication patterns, data flow', icon: '🏗️' },
  { href: '/docs/services', title: 'Services', description: 'Per-service reference: purpose, RPCs, Kafka topics', icon: '⚙️' },
  { href: '/docs/api', title: 'API Reference', description: 'GraphQL schema, REST endpoints, WebSocket protocol', icon: '🔌' },
  { href: '/docs/ralph', title: 'Ralph — AI Author', description: 'How an AI agent wrote this codebase', icon: '🤖' },
]
</script>

<template>
  <div class="animate-fade-in">
    <!-- Hero -->
    <div class="mb-12">
      <div class="flex items-center gap-2 mb-3">
        <span class="inline-block bg-qtown-gold/10 text-qtown-gold text-xs font-mono px-2 py-0.5 rounded border border-qtown-gold/20">v2.0</span>
        <span class="inline-block bg-qtown-forest/10 text-green-400 text-xs font-mono px-2 py-0.5 rounded border border-qtown-forest/30">Phase 5</span>
      </div>
      <h1 class="text-4xl font-bold text-qtown-text-primary mb-4">Qtown Documentation</h1>
      <p class="text-qtown-text-secondary text-lg leading-relaxed max-w-2xl">
        Qtown v2 is a fully autonomous medieval AI town — a living simulation where AI-powered NPCs
        work, trade, travel, fight, and form a society, all driven by a distributed microservices
        architecture running in real-time.
      </p>
    </div>

    <!-- How We Built This -->
    <section class="mb-12 bg-qtown-card border border-qtown-border rounded-lg p-6">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-3 flex items-center gap-2">
        <svg viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5 text-qtown-gold">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
        How We Built This
      </h2>
      <div class="text-qtown-text-secondary leading-relaxed space-y-3">
        <p>
          Qtown v2 was designed around one question: <em class="text-qtown-text-primary">what happens when you give a village full agency?</em>
          Each NPC has persistent memory, goals, and a decision loop powered by GPT-4o. They wake up,
          assess their needs (hunger, gold, happiness), pick a task, and act — buying food from the
          market, studying at the academy, or patrolling the fortress.
        </p>
        <p>
          The architecture is intentionally over-engineered for a "game". Every service communicates
          via typed gRPC contracts and publishes domain events to Kafka, so the system can scale
          horizontally and each service can be tested in isolation. The dashboard you're reading this in
          is a Nuxt 3 app that proxies GraphQL queries through a Cartographer gateway.
        </p>
        <p>
          Unusually, a large portion of this codebase was written by <NuxtLink to="/docs/ralph" class="text-qtown-accent hover:underline">Ralph</NuxtLink> — an
          AI coding agent operating in a read-spec → generate → test → commit loop. See the Ralph docs
          for the full story.
        </p>
      </div>
    </section>

    <!-- Quick links -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">Sections</h2>
      <div class="grid grid-cols-2 gap-4">
        <NuxtLink
          v-for="link in quickLinks"
          :key="link.href"
          :to="link.href"
          class="group bg-qtown-card border border-qtown-border rounded-lg p-5 hover:border-qtown-accent/40 hover:bg-qtown-accent/5 transition-all duration-200"
        >
          <div class="text-2xl mb-2">{{ link.icon }}</div>
          <h3 class="font-semibold text-qtown-text-primary group-hover:text-qtown-accent transition-colors mb-1">
            {{ link.title }}
          </h3>
          <p class="text-qtown-text-dim text-sm">{{ link.description }}</p>
        </NuxtLink>
      </div>
    </section>

    <!-- Architecture overview SVG -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">System Overview</h2>
      <div class="bg-qtown-card border border-qtown-border rounded-lg p-6 overflow-x-auto">
        <svg viewBox="0 0 760 340" class="w-full max-w-3xl mx-auto" style="min-width:600px" aria-label="Qtown service architecture overview">
          <!-- Background -->
          <rect width="760" height="340" fill="#1a1a2e" rx="8" />

          <!-- Title -->
          <text x="380" y="28" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">Qtown v2 — Service Architecture</text>

          <!-- Kafka bus (center horizontal band) -->
          <rect x="40" y="155" width="680" height="30" fill="#2a2a4a" rx="4" />
          <text x="380" y="174" text-anchor="middle" fill="#f5a623" font-size="11" font-family="monospace" font-weight="bold">Apache Kafka Event Bus</text>

          <!-- Top row services -->
          <!-- town-core -->
          <rect x="50" y="55" width="110" height="70" fill="#16213e" rx="6" stroke="#2d6a4f" stroke-width="1.5" />
          <text x="105" y="82" text-anchor="middle" fill="#40916c" font-size="10" font-family="monospace" font-weight="bold">town-core</text>
          <text x="105" y="95" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Python</text>
          <text x="105" y="108" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">FastAPI + asyncio</text>
          <!-- arrow down -->
          <line x1="105" y1="125" x2="105" y2="155" stroke="#2d6a4f" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- market-district -->
          <rect x="190" y="55" width="120" height="70" fill="#16213e" rx="6" stroke="#2a2a4a" stroke-width="1.5" />
          <text x="250" y="82" text-anchor="middle" fill="#a8b2c1" font-size="10" font-family="monospace" font-weight="bold">market-district</text>
          <text x="250" y="95" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Go</text>
          <text x="250" y="108" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">gRPC + order book</text>
          <line x1="250" y1="125" x2="250" y2="155" stroke="#2a2a4a" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- fortress -->
          <rect x="340" y="55" width="100" height="70" fill="#16213e" rx="6" stroke="#c1121f" stroke-width="1.5" />
          <text x="390" y="82" text-anchor="middle" fill="#e94560" font-size="10" font-family="monospace" font-weight="bold">fortress</text>
          <text x="390" y="95" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Go</text>
          <text x="390" y="108" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">gRPC validation</text>
          <line x1="390" y1="125" x2="390" y2="155" stroke="#c1121f" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- academy -->
          <rect x="465" y="55" width="100" height="70" fill="#16213e" rx="6" stroke="#4a4e69" stroke-width="1.5" />
          <text x="515" y="82" text-anchor="middle" fill="#9a8c98" font-size="10" font-family="monospace" font-weight="bold">academy</text>
          <text x="515" y="95" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Python</text>
          <text x="515" y="108" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">LLM gateway</text>
          <line x1="515" y1="125" x2="515" y2="155" stroke="#4a4e69" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- tavern -->
          <rect x="590" y="55" width="100" height="70" fill="#16213e" rx="6" stroke="#f5a623" stroke-width="1.5" />
          <text x="640" y="82" text-anchor="middle" fill="#f5a623" font-size="10" font-family="monospace" font-weight="bold">tavern</text>
          <text x="640" y="95" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Node.js</text>
          <text x="640" y="108" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">WebSocket hub</text>
          <line x1="640" y1="125" x2="640" y2="155" stroke="#f5a623" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- Bottom row services -->
          <!-- cartographer -->
          <rect x="50" y="215" width="120" height="70" fill="#16213e" rx="6" stroke="#2a2a4a" stroke-width="1.5" />
          <text x="110" y="242" text-anchor="middle" fill="#a8b2c1" font-size="10" font-family="monospace" font-weight="bold">cartographer</text>
          <text x="110" y="255" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Node.js</text>
          <text x="110" y="268" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">GraphQL gateway</text>
          <line x1="110" y1="185" x2="110" y2="215" stroke="#2a2a4a" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- library -->
          <rect x="200" y="215" width="100" height="70" fill="#16213e" rx="6" stroke="#2a2a4a" stroke-width="1.5" />
          <text x="250" y="242" text-anchor="middle" fill="#a8b2c1" font-size="10" font-family="monospace" font-weight="bold">library</text>
          <text x="250" y="255" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Python</text>
          <text x="250" y="268" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">search + archive</text>
          <line x1="250" y1="185" x2="250" y2="215" stroke="#2a2a4a" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- asset-pipeline -->
          <rect x="325" y="215" width="120" height="70" fill="#16213e" rx="6" stroke="#2a2a4a" stroke-width="1.5" />
          <text x="385" y="242" text-anchor="middle" fill="#a8b2c1" font-size="10" font-family="monospace" font-weight="bold">asset-pipeline</text>
          <text x="385" y="255" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Python</text>
          <text x="385" y="268" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">media generation</text>
          <line x1="385" y1="185" x2="385" y2="215" stroke="#2a2a4a" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- Redis -->
          <rect x="470" y="215" width="100" height="70" fill="#16213e" rx="6" stroke="#e94560" stroke-width="1.5" />
          <text x="520" y="242" text-anchor="middle" fill="#e94560" font-size="10" font-family="monospace" font-weight="bold">Redis</text>
          <text x="520" y="255" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">v7</text>
          <text x="520" y="268" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">cache + pub/sub</text>
          <line x1="520" y1="185" x2="520" y2="215" stroke="#e94560" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- dashboard -->
          <rect x="590" y="215" width="100" height="70" fill="#16213e" rx="6" stroke="#40916c" stroke-width="1.5" />
          <text x="640" y="242" text-anchor="middle" fill="#40916c" font-size="10" font-family="monospace" font-weight="bold">dashboard</text>
          <text x="640" y="255" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Nuxt 3</text>
          <text x="640" y="268" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Vue + Tailwind</text>
          <line x1="640" y1="185" x2="640" y2="215" stroke="#40916c" stroke-width="1.5" stroke-dasharray="4,2" />

          <!-- Legend -->
          <text x="50" y="318" fill="#475569" font-size="9" font-family="monospace">--- Kafka async</text>
          <line x1="130" y1="313" x2="160" y2="313" stroke="#40916c" stroke-width="1.5" />
          <text x="165" y="318" fill="#475569" font-size="9" font-family="monospace">gRPC sync</text>
          <line x1="220" y1="313" x2="250" y2="313" stroke="#e94560" stroke-width="1.5" />
          <text x="255" y="318" fill="#475569" font-size="9" font-family="monospace">Redis pub/sub</text>
        </svg>
      </div>
    </section>

    <!-- Tech stack table -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">Tech Stack</h2>
      <div class="overflow-x-auto rounded-lg border border-qtown-border">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-qtown-surface border-b border-qtown-border">
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase tracking-wider">Layer</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase tracking-wider">Technology</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase tracking-wider">Purpose</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in techStack"
              :key="row.layer"
              class="border-b border-qtown-border last:border-b-0 hover:bg-qtown-border/30 transition-colors"
              :class="i % 2 === 0 ? 'bg-qtown-card' : 'bg-qtown-bg/50'"
            >
              <td class="px-4 py-3 text-qtown-text-secondary font-medium">{{ row.layer }}</td>
              <td class="px-4 py-3 font-mono text-qtown-gold text-xs">{{ row.technology }}</td>
              <td class="px-4 py-3 text-qtown-text-dim">{{ row.purpose }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
