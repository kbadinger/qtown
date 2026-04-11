<script setup lang="ts">
import type { WorldState, Building, NpcSummary } from '~/composables/useTownState'

// PixiJS imports — client-only
import { Application } from '@pixi/core'
import { Container } from '@pixi/display'
import { Graphics } from '@pixi/graphics'
import { Text } from '@pixi/text'

const props = withDefaults(
  defineProps<{
    worldState: WorldState
    width?: number
    height?: number
  }>(),
  {
    width: 800,
    height: 600,
  }
)

// ─── Constants ────────────────────────────────────────────────────────────────

const TILE_W = 32
const TILE_H = 16
const GRID_SIZE = 50
const COLORS = {
  grass: 0x2d6a4f,
  grassAlt: 0x245a42,
  road: 0x4a4e69,
  building: 0x16213e,
  buildingTop: 0x1f2f50,
  buildingAccent: 0xe94560,
  gold: 0xf5a623,
  npcDot: 0xf5a623,
  npcActive: 0x40916c,
  npcSleeping: 0x4a4e69,
  water: 0x1a5276,
  selection: 0xe94560,
}

// ─── Isometric helpers ─────────────────────────────────────────────────────────

function isoToScreen(gx: number, gy: number): { x: number; y: number } {
  return {
    x: (gx - gy) * (TILE_W / 2),
    y: (gx + gy) * (TILE_H / 2),
  }
}

// ─── Refs ─────────────────────────────────────────────────────────────────────

const canvasEl = ref<HTMLCanvasElement | null>(null)
let app: Application | null = null
let worldContainer: Container | null = null

// Pan/zoom state
const zoom = ref(1.0)
const panX = ref(0)
const panY = ref(0)
let isPanning = false
let panStartX = 0
let panStartY = 0
let panOriginX = 0
let panOriginY = 0

// ─── Rendering ────────────────────────────────────────────────────────────────

function drawTile(g: Graphics, gx: number, gy: number, color: number) {
  const { x, y } = isoToScreen(gx, gy)
  g.beginFill(color)
  g.drawPolygon([
    x, y - TILE_H / 2,
    x + TILE_W / 2, y,
    x, y + TILE_H / 2,
    x - TILE_W / 2, y,
  ])
  g.endFill()
  // Edge lines
  g.lineStyle(0.5, 0x000000, 0.15)
  g.drawPolygon([
    x, y - TILE_H / 2,
    x + TILE_W / 2, y,
    x, y + TILE_H / 2,
    x - TILE_W / 2, y,
  ])
  g.lineStyle(0)
}

function drawBuilding(g: Graphics, building: Building) {
  const { x, y } = isoToScreen(building.x, building.y)
  const bh = 12 + (building.level - 1) * 6

  // Building face (front)
  g.beginFill(COLORS.building)
  g.drawPolygon([
    x - TILE_W / 2, y,
    x, y + TILE_H / 2,
    x, y + TILE_H / 2 + bh,
    x - TILE_W / 2, y + bh,
  ])
  g.endFill()

  // Building face (right)
  g.beginFill(COLORS.buildingTop)
  g.drawPolygon([
    x, y + TILE_H / 2,
    x + TILE_W / 2, y,
    x + TILE_W / 2, y + bh,
    x, y + TILE_H / 2 + bh,
  ])
  g.endFill()

  // Rooftop
  g.beginFill(COLORS.buildingAccent, 0.7)
  g.drawPolygon([
    x, y - TILE_H / 2 + bh,
    x + TILE_W / 2, y + bh,
    x, y + TILE_H / 2 + bh,
    x - TILE_W / 2, y + bh,
  ])
  g.endFill()
}

function drawNpc(g: Graphics, npc: NpcSummary) {
  const { x, y } = isoToScreen(npc.x, npc.y)
  const color =
    npc.status === 'active'
      ? COLORS.npcActive
      : npc.status === 'sleeping'
      ? COLORS.npcSleeping
      : COLORS.npcDot

  g.beginFill(color)
  g.drawCircle(x, y, 3)
  g.endFill()

  // Outline
  g.lineStyle(0.8, 0x000000, 0.5)
  g.drawCircle(x, y, 3)
  g.lineStyle(0)
}

function renderWorld() {
  if (!app || !worldContainer) return

  worldContainer.removeChildren()

  const tilesGfx = new Graphics()
  const buildingsGfx = new Graphics()
  const npcsGfx = new Graphics()

  // Draw ground tiles
  for (let gy = 0; gy < GRID_SIZE; gy++) {
    for (let gx = 0; gx < GRID_SIZE; gx++) {
      const isRoad = gx % 10 === 0 || gy % 10 === 0
      const isAlt = (gx + gy) % 2 === 0
      const color = isRoad ? COLORS.road : isAlt ? COLORS.grass : COLORS.grassAlt
      drawTile(tilesGfx, gx, gy, color)
    }
  }

  // Draw buildings
  const state = props.worldState
  for (const building of state.buildings) {
    drawBuilding(buildingsGfx, building)
  }

  // Draw NPC dots
  for (const npc of state.npcs) {
    drawNpc(npcsGfx, npc)
  }

  worldContainer.addChild(tilesGfx)
  worldContainer.addChild(buildingsGfx)
  worldContainer.addChild(npcsGfx)

  // Center offset
  worldContainer.x = app.renderer.width / 2 + panX.value
  worldContainer.y = TILE_H * 2 + panY.value
  worldContainer.scale.set(zoom.value)
}

// ─── Init ─────────────────────────────────────────────────────────────────────

onMounted(async () => {
  if (!canvasEl.value) return

  app = new Application({
    view: canvasEl.value,
    width: props.width,
    height: props.height,
    backgroundColor: 0x0d0d1a,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  })

  worldContainer = new Container()
  app.stage.addChild(worldContainer)

  // Add day/night overlay container
  const overlay = new Graphics()
  overlay.name = 'dayNightOverlay'
  app.stage.addChild(overlay)

  renderWorld()

  // Ticker for day/night animation
  app.ticker.add(() => {
    const overlay2 = app?.stage.getChildByName('dayNightOverlay') as Graphics | undefined
    if (overlay2 && app) {
      const isNight = props.worldState.isNight
      const alpha = isNight ? 0.35 : 0
      overlay2.clear()
      if (alpha > 0) {
        overlay2.beginFill(0x000033, alpha)
        overlay2.drawRect(0, 0, app.renderer.width, app.renderer.height)
        overlay2.endFill()
      }
    }
  })
})

onUnmounted(() => {
  app?.destroy(false, { children: true, texture: true, baseTexture: true })
  app = null
  worldContainer = null
})

// Re-render when world state changes
watch(
  () => props.worldState,
  () => {
    renderWorld()
  },
  { deep: true }
)

// ─── Pan/Zoom controls ────────────────────────────────────────────────────────

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  zoom.value = Math.min(4, Math.max(0.2, zoom.value * delta))
  renderWorld()
}

function onMouseDown(e: MouseEvent) {
  isPanning = true
  panStartX = e.clientX
  panStartY = e.clientY
  panOriginX = panX.value
  panOriginY = panY.value
}

function onMouseMove(e: MouseEvent) {
  if (!isPanning) return
  panX.value = panOriginX + (e.clientX - panStartX)
  panY.value = panOriginY + (e.clientY - panStartY)
  renderWorld()
}

function onMouseUp() {
  isPanning = false
}

function resetView() {
  zoom.value = 1.0
  panX.value = 0
  panY.value = 0
  renderWorld()
}

function zoomIn() {
  zoom.value = Math.min(4, zoom.value * 1.2)
  renderWorld()
}

function zoomOut() {
  zoom.value = Math.max(0.2, zoom.value / 1.2)
  renderWorld()
}
</script>

<template>
  <div class="relative select-none">
    <!-- Canvas -->
    <canvas
      ref="canvasEl"
      :width="width"
      :height="height"
      class="block rounded-lg cursor-grab active:cursor-grabbing"
      style="max-width: 100%; height: auto;"
      @wheel.prevent="onWheel"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    />

    <!-- Zoom controls -->
    <div class="absolute bottom-3 right-3 flex flex-col gap-1">
      <button
        class="w-8 h-8 bg-qtown-card border border-qtown-border rounded text-qtown-text-secondary hover:text-qtown-text-primary hover:bg-qtown-border transition-colors flex items-center justify-center font-mono text-lg"
        @click="zoomIn"
        aria-label="Zoom in"
      >+</button>
      <button
        class="w-8 h-8 bg-qtown-card border border-qtown-border rounded text-qtown-text-secondary hover:text-qtown-text-primary hover:bg-qtown-border transition-colors flex items-center justify-center font-mono text-lg"
        @click="zoomOut"
        aria-label="Zoom out"
      >−</button>
      <button
        class="w-8 h-8 bg-qtown-card border border-qtown-border rounded text-qtown-text-secondary hover:text-qtown-text-primary hover:bg-qtown-border transition-colors flex items-center justify-center"
        @click="resetView"
        aria-label="Reset view"
        title="Reset view"
      >
        <svg viewBox="0 0 16 16" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M1 8a7 7 0 1014 0A7 7 0 001 8z" />
          <path d="M8 5v3l2 2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    </div>

    <!-- Zoom indicator -->
    <div class="absolute bottom-3 left-3 text-qtown-text-dim text-xs font-mono bg-qtown-card/80 px-2 py-1 rounded">
      {{ Math.round(zoom * 100) }}%
    </div>
  </div>
</template>
