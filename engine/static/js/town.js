/**
 * Qwen Town — Isometric PixiJS Renderer
 *
 * Renders a 50x50 isometric tile grid with buildings and NPCs.
 * Polls /api/world every 2 seconds for live state updates.
 * Supports camera pan (drag) and zoom (scroll).
 */

(function () {
  "use strict";

  // -------------------------------------------------------------------------
  // Constants
  // -------------------------------------------------------------------------

  const GRID_SIZE   = 50;
  const TILE_W      = 64;
  const TILE_H      = 32;
  const POLL_MS     = 2000;
  const API_WORLD   = "/api/world";

  // Color palette
  const C = {
    bg:          0x0A0E17,
    gridLine:    0x1A3A2A,
    grass:       0x1B5E20,
    grassLight:  0x2E7D32,
    water:       0x0D47A1,
    sand:        0xBCAAA4,
    stone:       0x616161,
    forest:      0x1B3A1B,
    dirt:        0x5D4037,
    building:    0xFFB300,
    buildGlow:   0xFFD54F,
    npc:         0xE53935,
    npcGlow:     0xFF8A80,
  };

  const TERRAIN_COLORS = {
    grass:  [0x1E6B23, 0x237A28],  // Subtle variation — close shades
    water:  [C.water, 0x1565C0],
    sand:   [C.sand,  0xD7CCC8],
    stone:  [C.stone, 0x757575],
    forest: [C.forest, 0x2E4A2E],
    dirt:   [C.dirt,  0x6D4C41],
  };

  // Building color map for fallback shapes
  const BUILDING_COLORS = {
    civic:       0x5C6BC0,
    residential: 0x66BB6A,
    commercial:  0xFFA726,
    market:      0xFFCA28,
    tavern:      0xAB47BC,
    smithy:      0xEF5350,
    temple:      0x29B6F6,
    farm:        0x8D6E63,
    barracks:    0x78909C,
    library:     0x26A69A,
  };

  // -------------------------------------------------------------------------
  // Isometric projection helpers
  // -------------------------------------------------------------------------

  function toScreen(tileX, tileY) {
    return {
      x: (tileX - tileY) * (TILE_W / 2),
      y: (tileX + tileY) * (TILE_H / 2),
    };
  }

  function toTile(screenX, screenY) {
    const tx = (screenX / (TILE_W / 2) + screenY / (TILE_H / 2)) / 2;
    const ty = (screenY / (TILE_H / 2) - screenX / (TILE_W / 2)) / 2;
    return { x: Math.floor(tx), y: Math.floor(ty) };
  }

  // -------------------------------------------------------------------------
  // App initialization
  // -------------------------------------------------------------------------

  const canvas = document.getElementById("game-canvas");
  const app = new PIXI.Application({
    view: canvas,
    width: window.innerWidth,
    height: window.innerHeight,
    backgroundColor: C.bg,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });

  // Camera container (everything is a child of this)
  const camera = new PIXI.Container();
  app.stage.addChild(camera);

  // Layers (render order)
  const groundLayer    = new PIXI.Container();
  const buildingLayer  = new PIXI.Container();
  const npcLayer       = new PIXI.Container();
  camera.addChild(groundLayer, buildingLayer, npcLayer);

  // Center the grid initially
  camera.x = window.innerWidth / 2;
  camera.y = TILE_H * 4;

  // -------------------------------------------------------------------------
  // Sprite texture cache
  // -------------------------------------------------------------------------

  const textureCache = {};
  const failedTextures = {};    // url → timestamp of last failure
  const loadingTextures = new Set();
  const ASSET_VERSION = "v20";  // Cache-buster for CDN/Cloudflare
  const RETRY_INTERVAL = 10000; // Retry failed textures every 10s

  function tryLoadTexture(url) {
    if (textureCache[url]) return textureCache[url];
    if (loadingTextures.has(url)) return null;

    // Retry failed textures after RETRY_INTERVAL
    if (failedTextures[url]) {
      if (Date.now() - failedTextures[url] < RETRY_INTERVAL) return null;
      delete failedTextures[url];  // Time to retry
    }

    // Start async load with cache-buster (add timestamp on retries to bypass CDN cache)
    const bustUrl = url + "?" + ASSET_VERSION + "_" + Date.now();
    loadingTextures.add(url);

    // Use Image directly for reliable load/error events
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = function() {
      textureCache[url] = PIXI.Texture.from(img);
      loadingTextures.delete(url);
      needsRerender = true;
    };
    img.onerror = function() {
      failedTextures[url] = Date.now();
      loadingTextures.delete(url);
    };
    img.src = bustUrl;

    return null;  // Use fallback until texture is confirmed loaded
  }

  let needsRerender = false;

  // -------------------------------------------------------------------------
  // Drawing: ground tiles
  // -------------------------------------------------------------------------

  function drawGroundTiles(tiles) {
    groundLayer.removeChildren();

    // Build a lookup from tile data
    const tileLookup = {};
    if (tiles && tiles.length) {
      for (const t of tiles) {
        tileLookup[`${t.x},${t.y}`] = t.terrain || "grass";
      }
    }

    for (let ty = 0; ty < GRID_SIZE; ty++) {
      for (let tx = 0; tx < GRID_SIZE; tx++) {
        const terrain = tileLookup[`${tx},${ty}`] || "grass";
        const colors = TERRAIN_COLORS[terrain] || TERRAIN_COLORS.grass;
        // Subtle checkerboard — barely visible variation
        const fillColor = (tx + ty) % 2 === 0 ? colors[0] : colors[1];
        const alpha = (tx + ty) % 2 === 0 ? 0.90 : 0.85;

        const pos = toScreen(tx, ty);
        const g = new PIXI.Graphics();

        // Draw isometric diamond — subtle fill, very faint grid edge
        g.beginFill(fillColor, alpha);
        g.lineStyle(1, C.gridLine, 0.08);
        g.moveTo(pos.x,              pos.y - TILE_H / 2);
        g.lineTo(pos.x + TILE_W / 2, pos.y);
        g.lineTo(pos.x,              pos.y + TILE_H / 2);
        g.lineTo(pos.x - TILE_W / 2, pos.y);
        g.closePath();
        g.endFill();

        groundLayer.addChild(g);
      }
    }
  }

  // -------------------------------------------------------------------------
  // Drawing: buildings
  // -------------------------------------------------------------------------

  function drawBuildings(buildings) {
    buildingLayer.removeChildren();
    if (!buildings || !buildings.length) return;

    for (const b of buildings) {
      const pos = toScreen(b.x, b.y);
      const bType = (b.building_type || b.type || "civic").toLowerCase();
      const name = b.name || bType;
      const spriteUrl = `/static/assets/buildings/${bType}.png`;

      let sprite = null;
      const tex = tryLoadTexture(spriteUrl);
      if (tex && !failedTextures[spriteUrl]) {
        sprite = new PIXI.Sprite(tex);
        sprite.anchor.set(0.5, 1.0);
        // Building at (x,y) occupies 2x2 block: position at center of that block
        var center2x2 = toScreen(b.x + 1, b.y + 1);
        sprite.x = center2x2.x;
        sprite.y = center2x2.y + TILE_H / 2;
        sprite.width = TILE_W * 2.0;
        sprite.height = TILE_W * 2.0;
      }

      if (!sprite || failedTextures[spriteUrl]) {
        // Fallback: colored isometric box
        const color = BUILDING_COLORS[bType] || C.building;
        sprite = drawFallbackBuilding(pos.x, pos.y, color);
      }

      sprite.eventMode = "static";
      sprite.cursor = "pointer";

      // Tooltip data
      sprite._tooltipData = {
        title: name,
        type: bType,
        extra: b,
      };
      sprite.on("pointerover", onSpriteOver);
      sprite.on("pointerout",  onSpriteOut);
      sprite.on("pointermove", onSpriteMove);

      buildingLayer.addChild(sprite);
    }
  }

  function drawFallbackBuilding(x, y, color) {
    const g = new PIXI.Graphics();
    const w = TILE_W * 0.5;
    const h = TILE_H * 0.8;
    const height3d = TILE_H * 1.2;

    // Top face
    g.beginFill(color, 0.95);
    g.moveTo(x,         y - height3d);
    g.lineTo(x + w / 2, y - height3d + h / 2);
    g.lineTo(x,         y - height3d + h);
    g.lineTo(x - w / 2, y - height3d + h / 2);
    g.closePath();
    g.endFill();

    // Right face (darker)
    g.beginFill(color, 0.7);
    g.moveTo(x + w / 2, y - height3d + h / 2);
    g.lineTo(x + w / 2, y - h / 2 + h / 2);
    g.lineTo(x,         y);
    g.lineTo(x,         y - height3d + h);
    g.closePath();
    g.endFill();

    // Left face (darkest)
    g.beginFill(color, 0.55);
    g.moveTo(x - w / 2, y - height3d + h / 2);
    g.lineTo(x,         y - height3d + h);
    g.lineTo(x,         y);
    g.lineTo(x - w / 2, y - h / 2 + h / 2);
    g.closePath();
    g.endFill();

    // Glow outline on top
    g.lineStyle(1, 0xFFFFFF, 0.15);
    g.moveTo(x,         y - height3d);
    g.lineTo(x + w / 2, y - height3d + h / 2);
    g.lineTo(x,         y - height3d + h);
    g.lineTo(x - w / 2, y - height3d + h / 2);
    g.closePath();

    return g;
  }

  // -------------------------------------------------------------------------
  // Drawing: NPCs
  // -------------------------------------------------------------------------

  function drawNPCs(npcs) {
    npcLayer.removeChildren();
    if (!npcs || !npcs.length) return;

    for (const npc of npcs) {
      const pos = toScreen(npc.x, npc.y);
      const role = (npc.role || "villager").toLowerCase();
      const name = npc.name || role;
      const spriteUrl = `/static/assets/npcs/${role}.png`;

      let sprite = null;
      const tex = tryLoadTexture(spriteUrl);
      if (tex && !failedTextures[spriteUrl]) {
        sprite = new PIXI.Sprite(tex);
        sprite.anchor.set(0.5, 1.0);
        sprite.x = pos.x;
        sprite.y = pos.y + TILE_H * 0.25;
        sprite.width = TILE_W * 0.6;
        sprite.height = TILE_W * 0.6;
      }

      if (!sprite || failedTextures[spriteUrl]) {
        // Fallback: colored circle with glow
        sprite = drawFallbackNPC(pos.x, pos.y);
      }

      sprite.eventMode = "static";
      sprite.cursor = "pointer";

      sprite._tooltipData = {
        title: name,
        type: role,
        extra: npc,
      };
      sprite.on("pointerover", onSpriteOver);
      sprite.on("pointerout",  onSpriteOut);
      sprite.on("pointermove", onSpriteMove);

      npcLayer.addChild(sprite);
    }
  }

  function drawFallbackNPC(x, y) {
    const g = new PIXI.Graphics();

    // Soft glow
    g.beginFill(C.npcGlow, 0.2);
    g.drawCircle(x, y - 8, 10);
    g.endFill();

    // Body
    g.beginFill(C.npc, 0.9);
    g.drawCircle(x, y - 8, 5);
    g.endFill();

    // Head highlight
    g.beginFill(0xFFCDD2, 0.8);
    g.drawCircle(x, y - 10, 2.5);
    g.endFill();

    return g;
  }

  // -------------------------------------------------------------------------
  // Tooltip handling
  // -------------------------------------------------------------------------

  const tooltipEl  = document.getElementById("tooltip");
  const tooltipDiv = document.getElementById("tooltip-content");

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
  }

  // Track latest world data for building worker lookups
  let latestWorldData = null;

  function onSpriteOver(e) {
    const data = e.currentTarget._tooltipData;
    if (!data) return;

    let html = `<div class="font-semibold text-amber-300">${esc(data.title)}</div>`;
    html += `<div class="text-gray-400 text-xs uppercase tracking-wide">${esc(data.type)}</div>`;

    const ex = data.extra;

    if (ex.hunger !== undefined) {
      // NPC tooltip — rich format
      html += `<div class="text-xs mt-1">`;
      html += `<span title="Happiness">\u2665 ${esc(ex.happiness != null ? ex.happiness : '?')}</span>`;
      html += `  <span title="Energy">\u26A1 ${esc(ex.energy)}</span>`;
      html += `  <span title="Hunger">\uD83C\uDF56 ${esc(ex.hunger)}</span>`;
      html += `</div>`;
      html += `<div class="text-xs">\uD83D\uDCB0 ${esc(ex.gold)}g \u00B7 Age ${esc(ex.age != null ? ex.age : '?')}</div>`;
      // Show workplace if known
      if (ex.work_building_id && latestWorldData) {
        const wb = (latestWorldData.buildings || []).find(b => b.id === ex.work_building_id);
        if (wb) html += `<div class="text-xs text-gray-400">\u2192 ${esc(wb.name)}</div>`;
      }
    } else if (ex.building_type !== undefined) {
      // Building tooltip — show level, capacity, workers
      html += `<div class="text-xs mt-1">Level ${esc(ex.level || 1)} \u00B7 Cap: ${esc(ex.capacity || '?')}</div>`;
      if (latestWorldData) {
        const workers = (latestWorldData.npcs || []).filter(n => n.work_building_id === ex.id);
        if (workers.length) {
          html += `<div class="text-xs text-gray-400">Workers: ${workers.map(w => esc(w.name)).join(', ')}</div>`;
        }
      }
    } else {
      // Fallback
      if (ex.gold !== undefined) html += `<div class="text-xs mt-1">Gold: <span class="text-amber-200">${esc(ex.gold)}</span></div>`;
      if (ex.hp !== undefined) html += `<div class="text-xs">HP: ${esc(ex.hp)}</div>`;
      if (ex.level !== undefined) html += `<div class="text-xs">Level: ${esc(ex.level)}</div>`;
    }

    tooltipDiv.innerHTML = html;
    tooltipEl.classList.remove("hidden");
  }

  function onSpriteOut() {
    tooltipEl.classList.add("hidden");
  }

  function onSpriteMove(e) {
    // Position tooltip near the mouse cursor
    const global = e.data ? e.data.global : e.global;
    if (!global) return;
    tooltipEl.style.left = (global.x + 16) + "px";
    tooltipEl.style.top  = (global.y - 8) + "px";
  }

  // -------------------------------------------------------------------------
  // Camera: pan (drag) and zoom (scroll)
  // -------------------------------------------------------------------------

  let dragging = false;
  let dragStart = { x: 0, y: 0 };
  let cameraStart = { x: 0, y: 0 };

  canvas.addEventListener("pointerdown", (e) => {
    dragging = true;
    dragStart.x = e.clientX;
    dragStart.y = e.clientY;
    cameraStart.x = camera.x;
    cameraStart.y = camera.y;
    canvas.style.cursor = "grabbing";
  });

  window.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    camera.x = cameraStart.x + (e.clientX - dragStart.x);
    camera.y = cameraStart.y + (e.clientY - dragStart.y);
  });

  window.addEventListener("pointerup", () => {
    dragging = false;
    canvas.style.cursor = "grab";
  });

  canvas.style.cursor = "grab";

  // Zoom with mouse wheel
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const direction = e.deltaY < 0 ? 1 : -1;
    const factor = 1 + direction * 0.1;
    const newScale = Math.max(0.2, Math.min(3.0, camera.scale.x * factor));

    // Zoom toward cursor position
    const mouseX = e.clientX;
    const mouseY = e.clientY;
    const worldX = (mouseX - camera.x) / camera.scale.x;
    const worldY = (mouseY - camera.y) / camera.scale.y;

    camera.scale.set(newScale);
    camera.x = mouseX - worldX * newScale;
    camera.y = mouseY - worldY * newScale;
  }, { passive: false });

  // -------------------------------------------------------------------------
  // HUD update
  // -------------------------------------------------------------------------

  function updateHUD(world) {
    const tick = world.tick || world.world_tick || 0;
    const day  = world.day || Math.floor(tick / 24) + 1;
    const npcs = world.npcs || [];
    const pop  = npcs.length;
    let gold   = world.total_gold || 0;

    if (!gold && npcs.length) {
      gold = npcs.reduce((sum, n) => sum + (n.gold || 0), 0);
    }

    document.getElementById("hud-tick").textContent  = tick;
    document.getElementById("hud-day").textContent   = day;
    document.getElementById("hud-pop").textContent   = pop;
    document.getElementById("hud-gold").textContent  = gold;
  }

  // -------------------------------------------------------------------------
  // World state polling
  // -------------------------------------------------------------------------

  let lastWorldJSON = "";
  let loadingMessageShown = false;

  function showLoadingMessage() {
    if (loadingMessageShown) return;
    loadingMessageShown = true;

    // Fetch story count from dashboard API for the message
    let storyText = "0/215 stories complete";
    fetch("/api/dashboard-data")
      .then(r => r.json())
      .then(d => {
        const s = d.stories || {};
        storyText = `${s.done || 0}/${s.total || 215} stories complete`;
        updateLoadingText(storyText);
      })
      .catch(() => {});

    updateLoadingText(storyText);
  }

  function updateLoadingText(text) {
    // Remove old message if present
    const old = camera.getChildByName("loadingMsg");
    if (old) camera.removeChild(old);

    const msg = new PIXI.Text("Qwen is building this town...\n" + text, {
      fontFamily: "Inter, system-ui, sans-serif",
      fontSize: 24,
      fill: 0xFFB300,
      align: "center",
      dropShadow: true,
      dropShadowColor: 0x000000,
      dropShadowDistance: 2,
    });
    msg.name = "loadingMsg";
    msg.anchor.set(0.5);
    // Position at center of the grid
    const center = toScreen(GRID_SIZE / 2, GRID_SIZE / 2);
    msg.x = center.x;
    msg.y = center.y - 40;
    camera.addChild(msg);
  }

  async function fetchWorld() {
    try {
      const resp = await fetch(API_WORLD);
      if (!resp.ok) {
        showLoadingMessage();
        if (!lastWorldJSON) {
          render({ tiles: [], buildings: [], npcs: [], tick: 0 });
          lastWorldJSON = "{}";
        }
        return;
      }
      const world = await resp.json();
      const json = JSON.stringify(world);

      // Remove loading message once we have real data
      const old = camera.getChildByName("loadingMsg");
      if (old) camera.removeChild(old);

      // Re-render if state changed OR textures finished loading
      if (json !== lastWorldJSON || needsRerender) {
        lastWorldJSON = json;
        needsRerender = false;
        render(world);
      }
    } catch (err) {
      // API not available yet -- render empty grid with message
      showLoadingMessage();
      if (!lastWorldJSON) {
        render({ tiles: [], buildings: [], npcs: [], tick: 0 });
        lastWorldJSON = "{}";
      }
    }
  }

  function render(world) {
    latestWorldData = world;
    const tiles     = world.tiles || world.grid || [];
    const buildings = world.buildings || [];
    const npcs      = world.npcs || [];

    drawGroundTiles(tiles);
    drawBuildings(buildings);
    drawNPCs(npcs);
    updateHUD(world);
    updateStatsFromWorld(world);
  }

  // -------------------------------------------------------------------------
  // Stats panel — updated from /api/world data + periodic /api/stats fetch
  // -------------------------------------------------------------------------

  function updateStatsFromWorld(world) {
    var el;
    el = document.getElementById("stat-weather");
    if (el) el.textContent = world.weather || "clear";
    el = document.getElementById("stat-time");
    if (el) el.textContent = world.time_of_day || "morning";
    el = document.getElementById("stat-treasury");
    if (el) el.textContent = (world.treasury || 0) + "g";

    // Compute avg happiness from NPC data
    var npcs = world.npcs || [];
    if (npcs.length) {
      var avgH = Math.round(npcs.reduce(function(s,n){ return s + (n.happiness || 0); }, 0) / npcs.length);
      var avgA = Math.round(npcs.reduce(function(s,n){ return s + (n.age || 0); }, 0) / npcs.length);
      el = document.getElementById("stat-happiness");
      if (el) el.textContent = avgH;
      el = document.getElementById("stat-age");
      if (el) el.textContent = avgA;
    }
  }

  // Fetch enriched stats periodically (for economy, resources, tax)
  async function fetchStats() {
    try {
      var resp = await fetch("/api/stats/");
      if (!resp.ok) return;
      var data = await resp.json();

      var el;
      el = document.getElementById("stat-economy");
      if (el) el.textContent = data.economic_status || "normal";
      el = document.getElementById("stat-tax");
      if (el) el.textContent = Math.round((data.tax_rate || 0.10) * 100) + "%";
      el = document.getElementById("stat-treasury");
      if (el) el.textContent = (data.treasury_gold || 0) + "g";

      // Resources
      var resEl = document.getElementById("stat-resources");
      if (resEl && data.resources) {
        var keys = Object.keys(data.resources);
        if (keys.length) {
          resEl.innerHTML = keys.map(function(k) {
            return '<div class="flex justify-between"><span class="text-gray-500">' + esc(k) + '</span><span class="font-mono">' + esc(data.resources[k]) + '</span></div>';
          }).join('');
        } else {
          resEl.innerHTML = '<div class="text-gray-600">None yet</div>';
        }
      }
    } catch(e) { /* ignore */ }
  }

  // -------------------------------------------------------------------------
  // Activity feed — polls /api/activity every 3s
  // -------------------------------------------------------------------------

  var lastActivityJSON = "";

  async function fetchActivity() {
    try {
      var resp = await fetch("/api/activity/");
      if (!resp.ok) return;
      var items = await resp.json();
      var json = JSON.stringify(items);
      if (json === lastActivityJSON) return;
      lastActivityJSON = json;

      var listEl = document.getElementById("activity-list");
      if (!listEl) return;

      if (!items.length) {
        listEl.innerHTML = '<div class="text-gray-500 italic">No activity yet...</div>';
        return;
      }

      var html = "";
      var maxItems = 15;
      var shown = items.slice(0, maxItems);
      for (var i = 0; i < shown.length; i++) {
        var item = shown[i];
        var color = "text-gray-300";
        var dot = "\u25CF";
        if (item.type === "transaction") { color = "text-amber-300"; dot = "\uD83D\uDCB0"; }
        else if (item.severity === "critical" || item.severity === "high") { color = "text-red-400"; dot = "\u26A0"; }
        else if (item.severity === "warning") { color = "text-yellow-400"; dot = "\u26A0"; }
        else { color = "text-blue-300"; dot = "\u25CB"; }

        html += '<div class="' + color + ' truncate" title="' + esc(item.message) + '">';
        html += dot + ' ' + esc(item.message);
        html += '</div>';
      }
      listEl.innerHTML = html;
      listEl.scrollTop = listEl.scrollHeight;
    } catch(e) { /* ignore */ }
  }

  // -------------------------------------------------------------------------
  // Window resize
  // -------------------------------------------------------------------------

  window.addEventListener("resize", () => {
    app.renderer.resize(window.innerWidth, window.innerHeight);
  });

  // -------------------------------------------------------------------------
  // Boot
  // -------------------------------------------------------------------------

  // Status counter (bottom-right)
  (function() {
    var el = document.createElement("div");
    el.id = "status-counter";
    el.style.cssText = "position:fixed;bottom:10px;right:10px;z-index:99999;background:rgba(0,0,0,0.8);color:#0f0;padding:6px 10px;font:11px monospace;border-radius:4px;pointer-events:none;";
    el.textContent = "loading...";
    document.body.appendChild(el);

    var _base = fetchWorld;
    fetchWorld = async function() {
      try {
        await _base();
        el.textContent = "tiles:" + groundLayer.children.length + " buildings:" + buildingLayer.children.length + " npcs:" + npcLayer.children.length;
      } catch(e) {
        el.textContent = "error: " + e.message;
        el.style.color = "#f00";
      }
    };
  })();

  // Initial fetch, then poll
  fetchWorld();
  setInterval(fetchWorld, POLL_MS);

  // Stats + Activity polling (slower cadence to avoid overloading)
  fetchStats();
  fetchActivity();
  setInterval(fetchStats, 5000);
  setInterval(fetchActivity, 3000);
})();
