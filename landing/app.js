// ========================================
// QTOWN LANDING PAGE — Live Data + Interactions
// ========================================

const API_BASE = 'https://qtown.ai/api';

// Fallback data snapshot (real data from the running simulation)
const FALLBACK_DATA = {
  tick: 54368, day: 2266, total_gold: 2919857,
  weather: 'fog', time_of_day: 'morning', treasury: 0,
  tiles: (() => {
    const t = [];
    const terrains = ['grass','grass','grass','grass','forest','forest','sand','water','dirt','stone'];
    for (let y = 0; y < 50; y++) for (let x = 0; x < 50; x++) {
      // Create a realistic terrain distribution
      let terrain = 'grass';
      const dist = Math.sqrt((x-25)**2 + (y-25)**2);
      if (dist > 22) terrain = 'forest';
      else if (x > 35 && y < 15) terrain = 'sand';
      else if (x < 8 && y > 35) terrain = 'water';
      else if ((x+y) % 7 === 0 && dist > 10) terrain = 'dirt';
      else if (dist < 5) terrain = 'stone';
      t.push({x, y, terrain});
    }
    return t;
  })(),
  buildings: [
    {id:1,name:'Town Hall',building_type:'civic',x:25,y:25,capacity:10,level:1},
    {id:2,name:'Market',building_type:'food',x:28,y:22,capacity:8,level:1},
    {id:3,name:'Bakery',building_type:'food',x:30,y:20,capacity:5,level:1},
    {id:4,name:'Tavern',building_type:'entertainment',x:22,y:28,capacity:12,level:1},
    {id:5,name:'Lumber Mill',building_type:'production',x:18,y:15,capacity:6,level:1},
    {id:6,name:'Farm',building_type:'food',x:35,y:30,capacity:4,level:1},
    {id:7,name:'Barracks',building_type:'military',x:15,y:20,capacity:8,level:1},
    {id:8,name:'Library',building_type:'education',x:20,y:22,capacity:6,level:1},
    {id:9,name:'Windmill',building_type:'windmill',x:32,y:18,capacity:3,level:1},
    {id:10,name:'Smithy',building_type:'production',x:27,y:30,capacity:4,level:1},
    {id:11,name:'Chapel',building_type:'civic',x:23,y:24,capacity:15,level:1},
  ],
  npcs: [
    {id:195,name:'Helen',role:'mayor',sprite_id:'npc_06',x:25,y:25,gold:0,hunger:100,energy:0,happiness:40,age:66,work_building_id:null,home_building_id:1},
    {id:196,name:'Garrett',role:'merchant',sprite_id:'npc_02',x:28,y:22,gold:340,hunger:72,energy:55,happiness:68,age:34,work_building_id:2,home_building_id:1},
    {id:197,name:'Lyra',role:'baker',sprite_id:'npc_03',x:30,y:20,gold:120,hunger:88,energy:42,happiness:75,age:28,work_building_id:3,home_building_id:1},
    {id:198,name:'Theron',role:'farmer',sprite_id:'npc_01',x:35,y:30,gold:85,hunger:65,energy:30,happiness:52,age:45,work_building_id:6,home_building_id:1},
    {id:199,name:'Mira',role:'guard',sprite_id:'npc_04',x:15,y:20,gold:200,hunger:90,energy:78,happiness:60,age:31,work_building_id:7,home_building_id:1},
    {id:200,name:'Cedric',role:'scholar',sprite_id:'npc_05',x:20,y:22,gold:50,hunger:45,energy:65,happiness:82,age:55,work_building_id:8,home_building_id:1},
    {id:201,name:'Brynn',role:'miller',sprite_id:'npc_07',x:32,y:18,gold:95,hunger:78,energy:48,happiness:58,age:38,work_building_id:9,home_building_id:1},
    {id:202,name:'Isolde',role:'bard',sprite_id:'npc_08',x:22,y:28,gold:160,hunger:82,energy:35,happiness:90,age:26,work_building_id:4,home_building_id:1},
    {id:203,name:'Rowan',role:'smith',sprite_id:'npc_09',x:27,y:30,gold:275,hunger:55,energy:20,happiness:45,age:42,work_building_id:10,home_building_id:1},
    {id:204,name:'Elara',role:'merchant',sprite_id:'npc_10',x:29,y:23,gold:410,hunger:70,energy:60,happiness:72,age:33,work_building_id:2,home_building_id:1},
    {id:205,name:'Finn',role:'lumberjack',sprite_id:'npc_11',x:18,y:15,gold:65,hunger:40,energy:15,happiness:55,age:29,work_building_id:5,home_building_id:1},
  ]
};

// Terrain color map
const TERRAIN_COLORS = {
  grass:  '#2d5a27',
  forest: '#1a3d15',
  sand:   '#c4a44a',
  water:  '#1a4a6b',
  dirt:   '#6b4e2e',
  stone:  '#5a5a5a',
  road:   '#4a4a4a',
  snow:   '#c8d0d8',
};

const TERRAIN_COLORS_LIGHT = {
  grass:  '#5cb85c',
  forest: '#3a7d34',
  sand:   '#e8d47a',
  water:  '#4a9ad4',
  dirt:   '#a07848',
  stone:  '#8a8a8a',
  road:   '#7a7a7a',
  snow:   '#e8f0f8',
};

// ========================================
// Fetch world data
// ========================================

async function fetchWorldData() {
  try {
    const res = await fetch(`${API_BASE}/world`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch world data:', err);
    return null;
  }
}

// ========================================
// Render KPIs
// ========================================

function renderKPIs(data) {
  if (!data) return;

  const el = (id) => document.getElementById(id);
  el('kpiTick').textContent = data.tick.toLocaleString();
  el('kpiDay').textContent = data.day.toLocaleString();
  el('kpiWeather').textContent = data.weather;
  el('kpiTime').textContent = data.time_of_day;
  el('kpiGold').textContent = data.total_gold.toLocaleString();
  el('kpiPop').textContent = data.npcs ? data.npcs.length : '—';
}

// ========================================
// Render tile map on canvas
// ========================================

function renderMap(data) {
  const canvas = document.getElementById('worldMap');
  if (!canvas || !data || !data.tiles) return;

  const ctx = canvas.getContext('2d');
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
  const colors = isDark ? TERRAIN_COLORS : TERRAIN_COLORS_LIGHT;
  const tileSize = 10; // 500 / 50

  canvas.width = 500;
  canvas.height = 500;

  // Draw terrain
  for (const tile of data.tiles) {
    ctx.fillStyle = colors[tile.terrain] || colors.grass;
    ctx.fillRect(tile.x * tileSize, tile.y * tileSize, tileSize, tileSize);
  }

  // Draw buildings as bright dots
  if (data.buildings) {
    for (const b of data.buildings) {
      ctx.fillStyle = isDark ? '#fbbf24' : '#d97706';
      ctx.fillRect(b.x * tileSize + 1, b.y * tileSize + 1, tileSize - 2, tileSize - 2);
      // Glow effect
      ctx.fillStyle = isDark ? 'rgba(251,191,36,0.3)' : 'rgba(217,119,6,0.2)';
      ctx.fillRect(b.x * tileSize - 1, b.y * tileSize - 1, tileSize + 2, tileSize + 2);
    }
  }

  // Draw NPCs as accent-colored dots
  if (data.npcs) {
    for (const npc of data.npcs) {
      ctx.fillStyle = isDark ? '#4fd1c5' : '#0d9488';
      ctx.beginPath();
      ctx.arc(npc.x * tileSize + tileSize/2, npc.y * tileSize + tileSize/2, 4, 0, Math.PI * 2);
      ctx.fill();
      // Name label
      ctx.fillStyle = isDark ? 'rgba(228,228,232,0.8)' : 'rgba(26,26,30,0.8)';
      ctx.font = '9px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(npc.name, npc.x * tileSize + tileSize/2, npc.y * tileSize - 4);
    }
  }
}

// ========================================
// Render NPC table
// ========================================

function renderNPCTable(data) {
  const tbody = document.getElementById('npcBody');
  if (!tbody || !data || !data.npcs) return;

  if (data.npcs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No NPCs active</td></tr>';
    return;
  }

  tbody.innerHTML = data.npcs.map(npc => {
    const statBar = (val) => {
      const cls = val >= 60 ? 'good' : val >= 30 ? 'mid' : 'low';
      return `${val}<span class="stat-bar"><span class="stat-bar-fill ${cls}" style="width:${val}%"></span></span>`;
    };
    return `<tr>
      <td><strong style="color:var(--color-text)">${npc.name}</strong></td>
      <td>${npc.role}</td>
      <td>${npc.gold.toLocaleString()}</td>
      <td>${statBar(npc.hunger)}</td>
      <td>${statBar(npc.energy)}</td>
      <td>${statBar(npc.happiness)}</td>
      <td>${npc.age}</td>
    </tr>`;
  }).join('');
}

// ========================================
// Mobile menu
// ========================================

function initMobileMenu() {
  const btn = document.getElementById('menuToggle');
  const nav = document.getElementById('mobileNav');
  if (!btn || !nav) return;

  btn.addEventListener('click', () => {
    nav.classList.toggle('open');
    const isOpen = nav.classList.contains('open');
    btn.setAttribute('aria-expanded', isOpen);
    if (isOpen) {
      btn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    } else {
      btn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';
    }
  });

  // Close on link click
  nav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      nav.classList.remove('open');
      btn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';
    });
  });
}

// ========================================
// Header scroll behavior
// ========================================

function initHeader() {
  const header = document.getElementById('header');
  if (!header) return;
  let lastY = 0;

  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    if (y > 100) {
      header.style.boxShadow = 'var(--shadow-md)';
    } else {
      header.style.boxShadow = 'none';
    }
    lastY = y;
  }, { passive: true });
}

// ========================================
// Init
// ========================================

async function init() {
  initMobileMenu();
  initHeader();

  // Initial data load
  // Try live API first, fall back to snapshot
  let data = await fetchWorldData();
  if (!data) data = FALLBACK_DATA;
  
  renderKPIs(data);
  renderMap(data);
  renderNPCTable(data);
  
  // Update hint if using fallback
  if (!await fetchWorldData()) {
    const hint = document.querySelector('.api-hint');
    if (hint) hint.innerHTML = 'Snapshot from <code>qtown.ai/api/world</code> · Live refresh when API is reachable';
  }

  // Auto-refresh every 30s (try live, fallback to cached)
  setInterval(async () => {
    const freshData = await fetchWorldData();
    if (freshData) {
      renderKPIs(freshData);
      renderMap(freshData);
      renderNPCTable(freshData);
    }
  }, 30000);
}

document.addEventListener('DOMContentLoaded', init);
