<script setup lang="ts">
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import type {
  ChartData,
  ChartOptions,
  ChartType,
} from 'chart.js'
import { Line, Bar, Pie, Doughnut } from 'vue-chartjs'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = withDefaults(
  defineProps<{
    type: 'line' | 'bar' | 'pie' | 'doughnut'
    data: ChartData
    options?: ChartOptions
    height?: number
    loading?: boolean
  }>(),
  {
    options: () => ({}),
    height: 300,
    loading: false,
  }
)

const defaultOptions: ChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: '#94a3b8',
        font: { family: 'monospace', size: 11 },
        padding: 16,
      },
    },
    tooltip: {
      backgroundColor: '#16213e',
      borderColor: '#2a2a4a',
      borderWidth: 1,
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
      padding: 10,
    },
  },
  scales:
    props.type === 'line' || props.type === 'bar'
      ? {
          x: {
            ticks: { color: '#475569', font: { size: 10 } },
            grid: { color: '#2a2a4a' },
          },
          y: {
            ticks: { color: '#475569', font: { size: 10 } },
            grid: { color: '#2a2a4a' },
          },
        }
      : {},
}

const mergedOptions = computed<ChartOptions>(() => {
  return mergeDeep(defaultOptions, props.options ?? {}) as ChartOptions
})

function mergeDeep(target: Record<string, unknown>, source: Record<string, unknown>): Record<string, unknown> {
  const output = { ...target }
  for (const key of Object.keys(source)) {
    const sourceVal = source[key]
    const targetVal = target[key]
    if (
      sourceVal !== null &&
      typeof sourceVal === 'object' &&
      !Array.isArray(sourceVal) &&
      targetVal !== null &&
      typeof targetVal === 'object' &&
      !Array.isArray(targetVal)
    ) {
      output[key] = mergeDeep(
        targetVal as Record<string, unknown>,
        sourceVal as Record<string, unknown>
      )
    } else {
      output[key] = sourceVal
    }
  }
  return output
}

const chartStyle = computed(() => ({
  height: `${props.height}px`,
  position: 'relative' as const,
}))
</script>

<template>
  <div :style="chartStyle" class="relative">
    <!-- Loading overlay -->
    <div
      v-if="loading"
      class="absolute inset-0 flex items-center justify-center bg-qtown-card/80 rounded z-10"
    >
      <div class="flex gap-1">
        <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 0ms" />
        <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 150ms" />
        <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 300ms" />
      </div>
    </div>

    <Line
      v-if="type === 'line'"
      :data="(data as ChartData<'line'>)"
      :options="(mergedOptions as ChartOptions<'line'>)"
    />
    <Bar
      v-else-if="type === 'bar'"
      :data="(data as ChartData<'bar'>)"
      :options="(mergedOptions as ChartOptions<'bar'>)"
    />
    <Pie
      v-else-if="type === 'pie'"
      :data="(data as ChartData<'pie'>)"
      :options="(mergedOptions as ChartOptions<'pie'>)"
    />
    <Doughnut
      v-else-if="type === 'doughnut'"
      :data="(data as ChartData<'doughnut'>)"
      :options="(mergedOptions as ChartOptions<'doughnut'>)"
    />
  </div>
</template>
