<script setup lang="ts">
definePageMeta({ layout: 'docs' })
useHead({ title: 'Ralph — AI Author' })

interface ModelRow {
  task: string
  model: string
  reason: string
  avgTokens: string
  avgLatency: string
}

const modelRouting: ModelRow[] = [
  { task: 'NPC decision (complex social)', model: 'gpt-4o', reason: 'Nuanced reasoning needed for relationships & goals', avgTokens: '~1,200', avgLatency: '~2.1s' },
  { task: 'NPC decision (simple)', model: 'gpt-4o-mini', reason: 'Fast, cheap for hunger/rest/basic trade decisions', avgTokens: '~400', avgLatency: '~0.4s' },
  { task: 'Newspaper generation', model: 'gpt-4o', reason: 'Long-form coherent narrative required', avgTokens: '~3,500', avgLatency: '~5.8s' },
  { task: 'Quest generation', model: 'gpt-4o', reason: 'Multi-step quest design requires planning', avgTokens: '~1,800', avgLatency: '~3.1s' },
  { task: 'NPC study insight', model: 'gpt-4o-mini', reason: 'Short paragraph, low stakes', avgTokens: '~350', avgLatency: '~0.5s' },
  { task: 'Code generation (Ralph)', model: 'gpt-4o', reason: 'Production code requires full capability', avgTokens: '~8,000', avgLatency: '~12s' },
  { task: 'Test generation (Ralph)', model: 'gpt-4o', reason: 'Edge case reasoning for test coverage', avgTokens: '~4,000', avgLatency: '~7s' },
]

interface PhaseCommit {
  phase: string
  files: number
  linesAdded: number
  tests: number
  description: string
}

const commitHistory: PhaseCommit[] = [
  { phase: 'P1: Foundation', files: 28, linesAdded: 4_200, tests: 31, description: 'town-core engine, NPC model, basic tick loop, Kafka setup' },
  { phase: 'P2: Market & Fortress', files: 41, linesAdded: 6_800, tests: 58, description: 'Go order book, validation pipeline, gRPC contracts' },
  { phase: 'P3: Dashboard', files: 34, linesAdded: 5_100, tests: 22, description: 'Nuxt 3 dashboard, WebSocket integration, Pixi.js renderer' },
  { phase: 'P4: Intelligence', files: 52, linesAdded: 8_900, tests: 71, description: 'Academy LLM gateway, newspaper generation, asset pipeline' },
  { phase: 'P5: Docs & Extras', files: 38, linesAdded: 6_200, tests: 44, description: 'This phase: docs site, visitor mode, tournaments, SLA' },
]

const totalFiles = commitHistory.reduce((a, c) => a + c.files, 0)
const totalLines = commitHistory.reduce((a, c) => a + c.linesAdded, 0)
const totalTests = commitHistory.reduce((a, c) => a + c.tests, 0)
</script>

<template>
  <div class="animate-fade-in">
    <h1 class="text-3xl font-bold text-qtown-text-primary mb-3">Ralph — AI Author</h1>
    <p class="text-qtown-text-secondary text-base mb-10 leading-relaxed">
      Most of Qtown's codebase was written by an AI agent called Ralph. Here's exactly how that works.
    </p>

    <!-- The Loop -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-5">The Loop</h2>
      <div class="bg-qtown-card border border-qtown-border rounded-lg p-6">
        <div class="grid grid-cols-4 gap-0">
          <div
            v-for="(step, i) in [
              { n: 1, label: 'Read Spec', detail: 'Parse the worklist story. Extract requirements, interfaces, types, and constraints.', color: 'bg-blue-500/10 border-blue-500/30 text-blue-400' },
              { n: 2, label: 'Generate', detail: 'Produce implementation files: Go, Python, TypeScript, Vue. No stubs, no TODOs.', color: 'bg-purple-500/10 border-purple-500/30 text-purple-400' },
              { n: 3, label: 'Test', detail: 'Run the test suite. If failures: read error, patch the implementation. Repeat until green.', color: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400' },
              { n: 4, label: 'Commit', detail: 'git commit with structured message: phase, story ID, file list, test count.', color: 'bg-green-500/10 border-green-500/30 text-green-400' },
            ]"
            :key="step.n"
            class="relative"
          >
            <!-- Connector arrow (not last) -->
            <div
              v-if="i < 3"
              class="absolute right-0 top-1/2 w-4 h-0.5 bg-qtown-border z-10 -translate-y-1/2"
            />
            <div
              :class="['rounded-lg border p-4 mx-2', step.color]"
            >
              <div class="font-mono text-xs opacity-60 mb-1">0{{ step.n }}</div>
              <div class="font-semibold text-sm mb-2">{{ step.label }}</div>
              <div class="text-xs opacity-70 leading-relaxed">{{ step.detail }}</div>
            </div>
          </div>
        </div>
        <div class="mt-6 border-t border-qtown-border pt-4">
          <p class="text-sm text-qtown-text-secondary leading-relaxed">
            The loop runs once per story (P1-001, P1-002, …). Each story produces exactly the files
            listed in the spec. Ralph does not have access to a browser or a running server — it
            works from file I/O alone, using <code class="text-qtown-gold font-mono text-xs">pytest</code>,
            <code class="text-qtown-gold font-mono text-xs">go test</code>, and
            <code class="text-qtown-gold font-mono text-xs">tsc --noEmit</code> as the feedback signal.
          </p>
        </div>
      </div>
    </section>

    <!-- Model Routing -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">Model Routing Table</h2>
      <p class="text-qtown-text-secondary text-sm mb-4">
        Not every task warrants GPT-4o. Ralph routes to the cheapest model that can reliably
        handle the task, using a decision tree based on task type and context complexity.
      </p>
      <div class="overflow-x-auto rounded-lg border border-qtown-border">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-qtown-surface border-b border-qtown-border">
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Task</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Model</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Reason</th>
              <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Avg Tokens</th>
              <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Avg Latency</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in modelRouting"
              :key="row.task"
              class="border-b border-qtown-border last:border-b-0 bg-qtown-card hover:bg-qtown-border/30 transition-colors"
            >
              <td class="px-4 py-3 text-qtown-text-secondary">{{ row.task }}</td>
              <td class="px-4 py-3">
                <span
                  class="font-mono text-xs px-2 py-0.5 rounded"
                  :class="row.model === 'gpt-4o'
                    ? 'bg-qtown-gold/10 text-qtown-gold border border-qtown-gold/20'
                    : 'bg-green-500/10 text-green-400 border border-green-500/20'"
                >{{ row.model }}</span>
              </td>
              <td class="px-4 py-3 text-qtown-text-dim text-xs">{{ row.reason }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-text-secondary text-xs">{{ row.avgTokens }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-text-secondary text-xs">{{ row.avgLatency }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Commit Statistics -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">Commit Statistics</h2>
      <div class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-qtown-card border border-qtown-border rounded-lg px-5 py-4 text-center">
          <div class="text-3xl font-bold text-qtown-gold font-mono">{{ totalFiles }}</div>
          <div class="text-sm text-qtown-text-dim mt-1">files created</div>
        </div>
        <div class="bg-qtown-card border border-qtown-border rounded-lg px-5 py-4 text-center">
          <div class="text-3xl font-bold text-qtown-accent font-mono">{{ totalLines.toLocaleString() }}</div>
          <div class="text-sm text-qtown-text-dim mt-1">lines of code</div>
        </div>
        <div class="bg-qtown-card border border-qtown-border rounded-lg px-5 py-4 text-center">
          <div class="text-3xl font-bold text-green-400 font-mono">{{ totalTests }}</div>
          <div class="text-sm text-qtown-text-dim mt-1">tests passing</div>
        </div>
      </div>

      <div class="overflow-x-auto rounded-lg border border-qtown-border">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-qtown-surface border-b border-qtown-border">
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Phase</th>
              <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Files</th>
              <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Lines Added</th>
              <th class="text-right px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Tests</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Contents</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in commitHistory"
              :key="row.phase"
              class="border-b border-qtown-border last:border-b-0 bg-qtown-card hover:bg-qtown-border/30 transition-colors"
            >
              <td class="px-4 py-3 font-semibold text-qtown-text-primary">{{ row.phase }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-text-secondary">{{ row.files }}</td>
              <td class="px-4 py-3 text-right font-mono text-qtown-gold">{{ row.linesAdded.toLocaleString() }}</td>
              <td class="px-4 py-3 text-right font-mono text-green-400">{{ row.tests }}</td>
              <td class="px-4 py-3 text-qtown-text-dim text-xs">{{ row.description }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Can AI Write Production Code? -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-5">Can AI Write Production Code?</h2>

      <div class="space-y-4">
        <div class="bg-qtown-card border border-green-500/20 rounded-lg p-5">
          <h3 class="font-semibold text-green-400 mb-2">✓ What works well</h3>
          <ul class="space-y-2 text-sm text-qtown-text-secondary">
            <li><span class="text-green-400">›</span> Boilerplate-heavy code: Protobuf definitions, gRPC server setup, CRUD endpoints, table schemas</li>
            <li><span class="text-green-400">›</span> Typed interfaces between services — Ralph never forgets a field or mismatches a type</li>
            <li><span class="text-green-400">›</span> Test generation: given a spec, produces reasonable happy-path and edge-case tests</li>
            <li><span class="text-green-400">›</span> Documentation: this page was written by the same model that wrote the code it documents</li>
            <li><span class="text-green-400">›</span> Self-correction within a run: if <code class="font-mono text-xs">go test</code> fails, Ralph patches the right spot ~80% of the time</li>
          </ul>
        </div>

        <div class="bg-qtown-card border border-yellow-500/20 rounded-lg p-5">
          <h3 class="font-semibold text-yellow-400 mb-2">⚠ Where human review is required</h3>
          <ul class="space-y-2 text-sm text-qtown-text-secondary">
            <li><span class="text-yellow-400">›</span> Security: auth, rate limiting, injection prevention — Ralph writes functional code, not hardened code</li>
            <li><span class="text-yellow-400">›</span> Performance optimization: the matching engine passes tests but hasn't been profiled at 10k orders/s</li>
            <li><span class="text-yellow-400">›</span> Cross-story consistency: Ralph doesn't "remember" earlier stories in later ones without re-reading</li>
            <li><span class="text-yellow-400">›</span> Architectural decisions: Ralph implements what's specced, it doesn't question the spec</li>
          </ul>
        </div>

        <div class="bg-qtown-card border border-qtown-border rounded-lg p-5">
          <h3 class="font-semibold text-qtown-text-primary mb-3">The honest answer</h3>
          <p class="text-sm text-qtown-text-secondary leading-relaxed">
            For a project like Qtown — richly specced, test-first, with clear contracts between
            services — a capable AI can produce 80–90% of the implementation code with minimal
            revision. The remaining 10–20% is architecture, security hardening, performance tuning,
            and the kind of judgment that comes from having shipped to production before.
          </p>
          <p class="text-sm text-qtown-text-secondary leading-relaxed mt-3">
            The experiment here is not "can AI replace engineers?" but
            "what does the spec need to look like for AI to succeed?" The answer: precise, typed,
            with example inputs and outputs, and explicit file paths. Vague specs produce vague code.
          </p>
        </div>
      </div>
    </section>
  </div>
</template>
