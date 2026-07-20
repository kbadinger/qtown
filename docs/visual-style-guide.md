# Qtown v2 — Visual Style Guide + Sprite Manifest

**Status:** Draft 1 · 2026-05-06
**Companions:** [`v2-spec.md`](./v2-spec.md) · [`v2-pipeline.md`](./v2-pipeline.md)

This is the source of truth for v2's visual identity and the exhaustive list of sprites the generation pipeline must produce. Phase 2 (asset generation) reads from § 6 (sprite manifest) and § 7 (prompt patterns) directly.

---

## 1 · Aesthetic doctrine — stylized steampunk / techno-medieval

v2's visual world is medieval at its base — stone, timber, thatch, parchment, oil-lit lanterns — with **subtle tech accents** that map to each neighborhood's underlying technology. The medieval frame keeps the world legible and warm; the tech accents make the architecture readable without breaking the fantasy.

**Three rules:**

1. **Medieval first.** No tile reads as "modern." Anyone glancing at a screenshot should think "fantasy town" before noticing the brass fittings, glowing tomes, or pneumatic tubes.
2. **Tech accents per neighborhood.** Each district has a small, characteristic set of "anachronistic" elements that hint at its underlying tech. Brass dominates Fortress; Tesla coils dot Academy rooftops; pneumatic tubes thread through Market District; Cartographer has a real-time-updating map table.
3. **Coherence across the set.** All ~230 sprites share the same lighting, line weight, sticker-cut silhouette style, and isometric projection. Per-district LoRAs handle architectural variety; IPAdapter + ControlNet keep the global feel consistent.

**Render style:**
- Isometric projection at 30° (matches v1)
- Cartoon/sticker silhouette with soft AO shadows
- Hand-painted texture feel (not photorealistic, not pixel art)
- White or transparent background (BiRefNet post-process)
- Single light source (warm, ~3pm afternoon sun)

---

## 2 · Palette catalog

Global base colors used across all neighborhoods:

| Role | Hex | Usage |
|---|---|---|
| Stone neutral | `#8E867A` | Foundations, walls (default) |
| Timber warm | `#A0735C` | Wooden frames, doors, beams |
| Thatch | `#C7A26F` | Roofs (rustic neighborhoods) |
| Slate | `#4A5568` | Roofs (formal neighborhoods) |
| Parchment | `#EDDCB4` | Banners, scrolls, notices |
| Lantern glow | `#FFC773` | Light sources, evening highlights |
| Shadow base | `#3F3A35` | Interior shadows, AO |

**Per-neighborhood accent palette** (overlaid on the base):

| Neighborhood | Accent 1 | Accent 2 | Accent 3 | Notes |
|---|---|---|---|---|
| Town Hall | `#E5DBC7` marble | `#7B6852` aged bronze | `#2D4A6B` deep blue | Civic, formal |
| Market District | `#B5651D` copper | `#D4A847` brass | `#7E2D2D` claret awning | Bustling, warm |
| The Fortress | `#5C5042` brass-bound | `#2A2A2A` forge | `#9B7B3E` torchlight | Heavy, defensive |
| The Academy | `#E5C547` glow gold | `#3F2D6B` deep violet | `#A8C8E0` aether-glass | Scholarly, mystical |
| The Tavern | `#8B4513` warm wood | `#C7A26F` thatch | `#D4A847` hearth glow | Cozy, welcoming |
| The Library | `#5C4A3A` dark wood | `#C7A26F` parchment | `#8B6F47` brass index | Hushed, dim |
| Cartographer's Guild | `#E8E0CC` polished marble | `#3F4D6B` ink-blue | `#C7A26F` parchment | Polished, precise |
| Artisan's Workshop | `#D2A878` sand | `#B5651D` kiln-orange | `#7E5D3D` work bench | Industrial, busy |
| Roads / countryside | `#6B5B47` cobble | `#4A5C3D` grass | `#B8A77C` dirt path | Connective tissue |

---

## 3 · Materials catalog

The "tech accent" vocabulary — recurring elements that signal which neighborhood you're in:

| Material | Visual | Where it appears |
|---|---|---|
| Brass fittings | Polished yellow-gold metal with rivet detail | Fortress gates, Academy thinking devices, Cartographer's table |
| Pneumatic tubes | Brass+glass tubes with capsules visible inside | Market District (between stalls) |
| Glowing tomes | Hide-bound books with edge-glow | Academy desks, Library shelves |
| Tesla coils | Filigreed copper coils with soft electric arc | Academy rooftop tower |
| Steam vents | Stone-rim vent emitting wisp | Fortress walls, Artisan's kilns |
| Cartograph table | Inset map with subtle moving ink | Cartographer's Guild (centerpiece) |
| Parchment scrolls | Rolled parchment with seal | Library shelves, in-flight on roads |
| Switching board | Brass-and-wood lit-lamp panel | Academy lecture hall (model router) |
| Order ledger board | Massive chalk-on-slate board with quill | Market District plaza |
| Validation arch | Stone-and-brass gateway with glowing keystone | Fortress main gate |
| Broadcast bell | Bronze bell with engraved knot pattern | Tavern roof (rings on broadcast) |

Sprites that need any of these as accents will reference them by name in the prompt patterns (§ 7).

---

## 4 · Per-neighborhood mood

Brief descriptive palettes — tone, lighting, sound (suggested ambience), reference touchstones. These guide both sprite generation and renderer overlays.

### 4.1 Town Hall
- **Tone:** civic, dignified, central. The heart of the town.
- **Light:** balanced afternoon sun; warm marble glow at evening
- **Sound (ambient):** distant church bell, slow tick of the great clock
- **Reference touchstones:** Florentine piazza · Roman forum · Salisbury market square

### 4.2 Market District
- **Tone:** bustling, warm, energetic. Slight chaos.
- **Light:** bright midday under awnings; copper highlights everywhere
- **Sound:** shouting traders, pneumatic-tube whoosh, cart wheels on cobble
- **Reference touchstones:** Marrakech souk · Camden Market · isometric tycoon games

### 4.3 The Fortress
- **Tone:** weighty, defensive, watchful. Solid.
- **Light:** harsh shadow + torchlight; brass catches sunset
- **Sound:** boot-heels on stone, creak of brass gate hinge
- **Reference touchstones:** Edinburgh Castle · isometric strategy game keep · steampunk citadel

### 4.4 The Academy
- **Tone:** scholarly, mystical, charged with potential.
- **Light:** dim interior with warm glow from tomes; arcs of soft electricity from Tesla coils on the tower at night
- **Sound:** scratching quills, low murmur of debate, occasional electric crackle
- **Reference touchstones:** Bodleian Library · Hogwarts dueling club without the wands · Tesla's lab

### 4.5 The Tavern
- **Tone:** warm, welcoming, alive with rumor.
- **Light:** firelight + lantern; long evening light through stained glass
- **Sound:** laughter, mug-clatter, gossip board flipping
- **Reference touchstones:** Prancing Pony · Goblet of Fire · Renaissance inn

### 4.6 The Library
- **Tone:** hushed, deep, concentrated.
- **Light:** dim with green-shaded reading lamps; dust motes in beams
- **Sound:** rustle of parchment, whispered query, brass index card clack
- **Reference touchstones:** Trinity College Long Room · Discworld L-Space · cathedral library

### 4.7 Cartographer's Guild
- **Tone:** polished, precise, alert.
- **Light:** clean midday with reflective marble; soft glow on the cartograph table
- **Sound:** ink dipping, dispatch bells, footsteps on marble
- **Reference touchstones:** Royal Cartographic Society · Venetian doge's palace map room

### 4.8 Artisan's Workshop
- **Tone:** industrious, sooty, productive.
- **Light:** kiln-glow + steam-cut shadow; sparks
- **Sound:** hammer + bellows + the whir of a sprite materializing
- **Reference touchstones:** medieval guild hall · Aardman Animations workshop · Caves of Steel

### 4.9 Roads + countryside
- **Tone:** connective, alive with traffic in proportion to topic throughput.
- **Light:** open sky; ground tinting changes as roads enter neighborhoods
- **Sound:** footsteps, wagon wheels, courier horns at intersections
- **Reference touchstones:** Roman road · pilgrim's way · scenic isometric world maps

---

## 5 · Asset specifications

| Property | Value |
|---|---|
| **Building canvas** | 1024×1024 (downsampled to 256×256 for renderer) |
| **NPC canvas** | 512×512 (downsampled to 128×128) |
| **Prop canvas** | 512×512 (downsampled to 128×128) |
| **Terrain tile** | 256×128 isometric (rendered at native size) |
| **Background** | white during generation, transparent after BiRefNet pass |
| **Anchor** | bottom-center for all building/NPC/prop sprites |
| **Naming** | `<neighborhood>-<type>-<id>-<variant>.png` (e.g., `market-building-stall-01.png`, `academy-npc-scholar-02.png`) |
| **Format** | PNG with alpha |
| **Asset version** | `ASSET_VERSION=v22` (cache-bust on script tag) |
| **Output path** | `dashboard/public/sprites/<neighborhood>/{buildings,npcs,props}/` |

---

## 6 · Sprite manifest

Counts and per-sprite enumeration. Use these IDs in `world-layout.json` (Phase 3) and the dashboard composables.

### 6.1 Town Hall (15 buildings · 7 NPCs · 4 props)

**Buildings** — `dashboard/public/sprites/town-hall/buildings/`
| ID | Description |
|---|---|
| `town-hall-main` | Main civic building, 3 stories, classical columns, central clock face |
| `town-hall-clock-tower` | Standalone bell tower with great clock face (animated) |
| `town-hall-tax-office` | Smaller civic building with ledger window |
| `town-hall-records-hall` | Archive-style building with tall narrow windows |
| `town-hall-residence-01` | Citizen dwelling, 2 stories, painted shutters |
| `town-hall-residence-02` | Citizen dwelling, modest, single story with garden |
| `town-hall-residence-03` | Townhouse, 2 stories, wrought-iron balcony |
| `town-hall-residence-04` | Cottage, thatched roof, low |
| `town-hall-residence-05` | Townhouse, 3 stories, narrow |
| `town-hall-notice-board-01` | Public notice board with parchment |
| `town-hall-notice-board-02` | Smaller notice post at intersection |
| `town-hall-fountain` | Civic fountain, central plaza |
| `town-hall-statue-founder` | Statue on a pedestal in the plaza |
| `town-hall-bench` | Stone bench with carved details |
| `town-hall-lamp-post` | Wrought-iron lamp post with glass lantern |

**NPCs** — `dashboard/public/sprites/town-hall/npcs/`
| ID | Description |
|---|---|
| `town-hall-npc-mayor` | Mayor in formal coat with chain of office |
| `town-hall-npc-tax-collector` | Tax collector with ledger and quill |
| `town-hall-npc-town-crier` | Town crier with bell and rolled parchment |
| `town-hall-npc-scribe` | Scribe with portable writing desk |
| `town-hall-npc-citizen-01` | Generic citizen, working dress |
| `town-hall-npc-citizen-02` | Generic citizen, market-day attire |
| `town-hall-npc-citizen-03` | Generic citizen, child |

**Props** — `dashboard/public/sprites/town-hall/props/`
| ID | Description |
|---|---|
| `town-hall-prop-clock-face` | Animated great-clock face overlay |
| `town-hall-prop-day-night-overlay` | Sky gradient overlay for day/night cycle |
| `town-hall-prop-ledger-stack` | Stack of tax ledgers |
| `town-hall-prop-civic-banner` | Hanging banner with town arms |

### 6.2 Market District (14 buildings · 6 NPCs · 6 props)

**Buildings** — `dashboard/public/sprites/market/buildings/`
| ID | Description |
|---|---|
| `market-orderbook-plaza` | Open plaza with the great chalk-on-slate ledger board |
| `market-stall-grain` | Trade stall with copper roof, grain sacks visible |
| `market-stall-cloth` | Trade stall with bolts of cloth on display |
| `market-stall-spice` | Trade stall with spice barrels and scales |
| `market-stall-iron` | Trade stall with iron ingots and tools |
| `market-stall-gem` | Trade stall with locked glass cases |
| `market-stall-wine` | Trade stall with wine casks |
| `market-stall-livestock` | Trade stall with livestock pen behind |
| `market-stall-fish` | Trade stall with fish on ice |
| `market-warehouse` | Two-story warehouse with loading doors |
| `market-pneumatic-hub` | Central pneumatic-tube hub building, brass-trimmed |
| `market-customs-house` | Customs house with weighing scale visible |
| `market-trader-lodgings` | Modest lodgings for transient traders |
| `market-cart-rest` | Cart parking area with hitching posts |

**NPCs** — `dashboard/public/sprites/market/npcs/`
| ID | Description |
|---|---|
| `market-npc-trader-01` | Trader in apron, sleeves rolled |
| `market-npc-broker` | Broker in well-cut coat with quill |
| `market-npc-runner` | Young runner with parcel and message tube |
| `market-npc-customs-officer` | Customs officer in stamped uniform |
| `market-npc-warehouse-hand` | Warehouse hand with crowbar and crate |
| `market-npc-cart-driver` | Driver with reins and wide-brim hat |

**Props** — `dashboard/public/sprites/market/props/`
| ID | Description |
|---|---|
| `market-prop-orderbook-board` | Animated chalk-on-slate ledger board (the headline prop) |
| `market-prop-pneumatic-tube` | Brass+glass pneumatic tube segment with capsule |
| `market-prop-trade-line-flag` | Colored pennant denoting an active trade line |
| `market-prop-grain-sack` | Sack of grain (commodity icon) |
| `market-prop-iron-ingot` | Iron ingot stack (commodity icon) |
| `market-prop-coin-pile` | Coin pile (settlement marker) |

### 6.3 The Fortress (12 buildings · 5 NPCs · 6 props)

**Buildings** — `dashboard/public/sprites/fortress/buildings/`
| ID | Description |
|---|---|
| `fortress-main-gate` | Main entrance with brass-bound gate and validation arch |
| `fortress-keep` | Central keep, stone, 3 stories |
| `fortress-wasm-chamber` | Brass chamber visible through fortress windows; the WASM sandbox |
| `fortress-guard-tower-corner` | Corner tower with crenellations |
| `fortress-guard-tower-side` | Side tower with arrow slits |
| `fortress-policy-library` | Annexed library where policies are catalogued |
| `fortress-barracks` | Guard barracks, austere |
| `fortress-armory` | Armory with rack of polearms visible |
| `fortress-kitchen` | Mess hall and kitchen |
| `fortress-courtyard-fountain` | Functional fountain in courtyard |
| `fortress-portcullis-mech` | Portcullis mechanism (brass gears visible) |
| `fortress-wall-segment` | Reusable wall segment with parapet |

**NPCs** — `dashboard/public/sprites/fortress/npcs/`
| ID | Description |
|---|---|
| `fortress-npc-guard` | Guard with halberd and tabard |
| `fortress-npc-validator` | Validator at gate, brass-edged uniform |
| `fortress-npc-sandbox-keeper` | Sandbox-keeper in heat-resistant apron |
| `fortress-npc-inspector` | Inspector with policy clipboard |
| `fortress-npc-cook` | Mess-hall cook |

**Props** — `dashboard/public/sprites/fortress/props/`
| ID | Description |
|---|---|
| `fortress-prop-validation-orb` | Glowing orb (incoming validation event) |
| `fortress-prop-validation-orb-accept` | Green-glowing orb (accept) |
| `fortress-prop-validation-orb-reject` | Red-glowing orb (reject) |
| `fortress-prop-zero-unsafe-plaque` | Engraved brass plaque "0 UNSAFE" |
| `fortress-prop-policy-scroll` | Policy scroll (in-flight) |
| `fortress-prop-brass-gear` | Brass gear (mechanism detail) |

### 6.4 The Academy (13 buildings · 7 NPCs · 6 props)

**Buildings** — `dashboard/public/sprites/academy/buildings/`
| ID | Description |
|---|---|
| `academy-lecture-hall` | Lecture hall with switching board on wall (visible through window) |
| `academy-thinking-tower` | Tower topped with a Tesla-coil thinking device |
| `academy-dormitory-east` | Scholar dormitory, 3 stories |
| `academy-dormitory-west` | Scholar dormitory, 3 stories |
| `academy-bookbinder` | Bookbinder's shop, exposed binding press |
| `academy-quad-gateway` | Open archway entry to the quad |
| `academy-quad-fountain` | Quad fountain with tortoise statue |
| `academy-debate-hall` | Round building with tiered seating visible |
| `academy-experiment-lab` | Lab with glassware visible through windows |
| `academy-orrery` | Building housing a working orrery |
| `academy-greenhouse` | Glass greenhouse with glowing plants |
| `academy-archive-bridge` | Covered bridge connecting Academy → Library |
| `academy-rooftop-tesla` | Rooftop Tesla coil (separate sprite for animation overlay) |

**NPCs** — `dashboard/public/sprites/academy/npcs/`
| ID | Description |
|---|---|
| `academy-npc-scholar-01` | Scholar with glowing tome under arm |
| `academy-npc-scholar-02` | Scholar in robes mid-debate |
| `academy-npc-lecturer` | Lecturer at podium with pointer |
| `academy-npc-sandbox-debugger` | Debugger in goggles with portable Tesla device |
| `academy-npc-model-router-attendant` | Attendant operating switching board |
| `academy-npc-rag-archivist` | Archivist carrying scroll between Library and Academy |
| `academy-npc-student` | Student carrying multiple tomes, hurried |

**Props** — `dashboard/public/sprites/academy/props/`
| ID | Description |
|---|---|
| `academy-prop-glowing-tome` | Glowing tome (open or closed variant) |
| `academy-prop-tesla-coil` | Tesla coil with electric arc animation frame |
| `academy-prop-switching-board` | Switching board with lit/unlit lamp variants |
| `academy-prop-thought-bubble` | Thought-bubble overlay (text-bearing) |
| `academy-prop-rag-scroll` | Scroll mid-flight (RAG context retrieval) |
| `academy-prop-orrery-globe` | Spinning orrery globe (animated detail) |

### 6.5 The Tavern (10 buildings · 5 NPCs · 5 props)

**Buildings** — `dashboard/public/sprites/tavern/buildings/`
| ID | Description |
|---|---|
| `tavern-main` | Main inn building, 2 stories, hanging sign |
| `tavern-hearth-room` | Attached hearth room, large chimney |
| `tavern-leaderboard-plaque` | Wall-mounted leaderboard plaque (animated) |
| `tavern-gossip-board` | Outdoor gossip board on a post |
| `tavern-beer-garden` | Outdoor seating with arbor |
| `tavern-stable` | Adjoining stable for travelers |
| `tavern-side-cellar` | Cellar entrance with barrel hoist |
| `tavern-rooftop-bell` | Rooftop with the broadcast bell (separate sprite for animation) |
| `tavern-courier-station` | Small courier station for outgoing event runners |
| `tavern-lantern-arch` | Decorated arched entrance with lanterns |

**NPCs** — `dashboard/public/sprites/tavern/npcs/`
| ID | Description |
|---|---|
| `tavern-npc-innkeeper` | Innkeeper behind the bar |
| `tavern-npc-patron-01` | Patron with mug, mid-laugh |
| `tavern-npc-gossip` | Gossip in animated conversation, hand on cheek |
| `tavern-npc-leaderboard-herald` | Herald updating the leaderboard |
| `tavern-npc-courier` | Courier mid-stride with sealed message |

**Props** — `dashboard/public/sprites/tavern/props/`
| ID | Description |
|---|---|
| `tavern-prop-broadcast-bell` | Bronze bell with knot engraving (rings on broadcast) |
| `tavern-prop-broadcast-pulse` | Concentric ring overlay (the WS broadcast pulse) |
| `tavern-prop-leaderboard-card` | Single rank card on the plaque |
| `tavern-prop-mug` | Tavern mug |
| `tavern-prop-gossip-scroll` | Mini-scroll for gossip board entries |

### 6.6 The Library (10 buildings · 5 NPCs · 5 props)

**Buildings** — `dashboard/public/sprites/library/buildings/`
| ID | Description |
|---|---|
| `library-vault-main` | Main archive vault, severe stone façade |
| `library-reading-hall` | Reading hall with tall arched windows |
| `library-index-card-room` | Brass index card room with cabinets visible |
| `library-search-desk` | Search desk at the entrance |
| `library-conservation-lab` | Conservation lab, climate-controlled |
| `library-spiral-stack` | Visible spiral staircase up to the high stacks |
| `library-reading-balcony` | Reading balcony overlooking the hall |
| `library-quiet-cell` | Single-occupancy reading cell |
| `library-archive-bridge-end` | Library-side end of the Academy bridge |
| `library-front-banner` | Front-entrance banner overlay (search-throughput display) |

**NPCs** — `dashboard/public/sprites/library/npcs/`
| ID | Description |
|---|---|
| `library-npc-archivist` | Archivist carrying scroll bundle |
| `library-npc-indexer` | Indexer at brass card cabinet |
| `library-npc-conservator` | Conservator with magnifier and brush |
| `library-npc-search-clerk` | Clerk at the search desk |
| `library-npc-visiting-scholar` | Scholar on visit from Academy (carries glowing tome) |

**Props** — `dashboard/public/sprites/library/props/`
| ID | Description |
|---|---|
| `library-prop-scroll-bundle` | Bundle of scrolls (in-flight or on cart) |
| `library-prop-search-banner` | Animated banner showing recent searches |
| `library-prop-brass-index-card` | Brass index card detail |
| `library-prop-reading-lamp` | Green-shaded reading lamp |
| `library-prop-card-cabinet` | Brass card cabinet (interactive prop) |

### 6.7 Cartographer's Guild (9 buildings · 5 NPCs · 6 props)

**Buildings** — `dashboard/public/sprites/cartographer/buildings/`
| ID | Description |
|---|---|
| `cartographer-mapmakers-office` | Main office with a giant cartograph table visible through wide windows |
| `cartographer-cartograph-table` | Standalone giant cartograph table prop (centerpiece, animated overlay) |
| `cartographer-drafting-room-east` | Drafting room with tilted desks |
| `cartographer-drafting-room-west` | Drafting room with tilted desks |
| `cartographer-reception-gate` | Reception/visitor gate at the front |
| `cartographer-pigeon-coop` | Pigeon coop on the roof for inter-guild messages |
| `cartographer-archive-room` | Archive of historical maps |
| `cartographer-instrument-shop` | Shop selling sextants and compasses |
| `cartographer-courtyard` | Polished marble courtyard |

**NPCs** — `dashboard/public/sprites/cartographer/npcs/`
| ID | Description |
|---|---|
| `cartographer-npc-cartographer` | Senior cartographer with brass dividers |
| `cartographer-npc-draftsman` | Draftsman bent over a desk |
| `cartographer-npc-dispatcher` | Dispatcher at the gate, holding pennants |
| `cartographer-npc-visitor-blue` | Query-visitor (blue, query-type variant) |
| `cartographer-npc-visitor-green` | Query-visitor (green, query-type variant) |

**Props** — `dashboard/public/sprites/cartographer/props/`
| ID | Description |
|---|---|
| `cartographer-prop-cartograph-table-overlay` | The animated map-table top (the headline prop) |
| `cartographer-prop-dispatch-flag` | Pennant for dispatch gestures |
| `cartographer-prop-sextant` | Sextant detail |
| `cartographer-prop-compass-rose` | Compass rose floor inlay |
| `cartographer-prop-visitor-orange` | Query-visitor (orange) — additional variant |
| `cartographer-prop-visitor-purple` | Query-visitor (purple) — additional variant |

### 6.8 Artisan's Workshop (10 buildings · 5 NPCs · 5 props)

**Buildings** — `dashboard/public/sprites/artisan/buildings/`
| ID | Description |
|---|---|
| `artisan-main-workshop` | Main workshop with kiln chimney and exposed beams |
| `artisan-kiln` | Standalone kiln building, glowing |
| `artisan-display-plaza` | Plaza with curtained-tarp display platforms |
| `artisan-shipping-yard` | Yard with crates ready to ship along roads |
| `artisan-workbench-row` | Long building of workbenches |
| `artisan-bellows-house` | Bellows house, visible mechanism |
| `artisan-paint-shop` | Paint shop with samples on the wall |
| `artisan-tool-storage` | Tool storage with racks visible |
| `artisan-blueprint-room` | Blueprint room with rolled drawings |
| `artisan-finishing-pavilion` | Finishing pavilion (final coat, touchups) |

**NPCs** — `dashboard/public/sprites/artisan/npcs/`
| ID | Description |
|---|---|
| `artisan-npc-artisan` | Artisan with chisel and apron |
| `artisan-npc-kiln-keeper` | Kiln keeper in heat-resistant gear |
| `artisan-npc-shipper` | Shipper with crate hand-truck |
| `artisan-npc-displayer` | Displayer mid-tarp-removal |
| `artisan-npc-painter` | Painter with palette and brush |

**Props** — `dashboard/public/sprites/artisan/props/`
| ID | Description |
|---|---|
| `artisan-prop-tarp-display` | Tarp on a display platform (pre-reveal) |
| `artisan-prop-tarp-revealed` | Same after reveal (with new sprite underneath) |
| `artisan-prop-shipping-crate` | Shipping crate (in-transit) |
| `artisan-prop-bellows` | Bellows in motion |
| `artisan-prop-easel-wip` | Easel with work-in-progress sprite |

### 6.9 Roads + countryside (4 building-equiv · 3 NPC variants · 8 props · 9 terrain tiles)

**Building-equivalents** — `dashboard/public/sprites/roads/buildings/`
| ID | Description |
|---|---|
| `roads-milestone-marker` | Stone milestone with road name carved |
| `roads-bridge-stone` | Small stone bridge for road crossings |
| `roads-roadside-shrine` | Small wayside shrine |
| `roads-rest-pavilion` | Wayside rest pavilion |

**NPCs** — `dashboard/public/sprites/roads/npcs/`
| ID | Description |
|---|---|
| `roads-npc-messenger-foot` | Foot messenger with sealed envelope (Kafka payload) |
| `roads-npc-messenger-cart` | Cart messenger with bundled scrolls |
| `roads-npc-traveler` | Generic traveler with walking stick |

**Props** — `dashboard/public/sprites/roads/props/`
| ID | Description |
|---|---|
| `roads-prop-road-sign-broadcast-way` | Sign for `qtown.events.broadcast` |
| `roads-prop-road-sign-traders-road` | Sign for `qtown.economy.trade` |
| `roads-prop-road-sign-settlers-way` | Sign for `qtown.economy.trade.settled` |
| `roads-prop-road-sign-criers-way` | Sign for `qtown.economy.price.update` |
| `roads-prop-road-sign-sentinels-approach` | Sign for `qtown.validation.request` |
| `roads-prop-road-sign-verdicts-return` | Sign for `qtown.validation.result` |
| `roads-prop-road-sign-scholars-path` | Sign for `qtown.ai.request` + `ai.response` |
| `roads-prop-road-sign-gossip-pipeline` | Sign for `qtown.ai.content.generated` |

**Terrain tiles** — `dashboard/public/sprites/roads/terrain/`
| ID | Description |
|---|---|
| `terrain-cobble-road-straight` | Cobble road, straight |
| `terrain-cobble-road-corner` | Cobble road, corner |
| `terrain-cobble-road-tee` | Cobble road, T-intersection |
| `terrain-cobble-road-cross` | Cobble road, four-way crossing |
| `terrain-grass` | Grass tile (countryside) |
| `terrain-dirt-path` | Dirt path tile |
| `terrain-marble-civic` | Marble plaza tile (Town Hall ground tint) |
| `terrain-flagstone` | Flagstone tile (Library/Cartographer ground tint) |
| `terrain-claypaver` | Clay paver tile (Market ground tint) |

### 6.10 Manifest summary

| Neighborhood | Buildings | NPCs | Props | Subtotal |
|---|---|---|---|---|
| Town Hall | 15 | 7 | 4 | 26 |
| Market District | 14 | 6 | 6 | 26 |
| The Fortress | 12 | 5 | 6 | 23 |
| The Academy | 13 | 7 | 6 | 26 |
| The Tavern | 10 | 5 | 5 | 20 |
| The Library | 10 | 5 | 5 | 20 |
| Cartographer's Guild | 9 | 5 | 6 | 20 |
| Artisan's Workshop | 10 | 5 | 5 | 20 |
| Roads + countryside | 4 | 3 | 8 | 15 |
| Terrain | — | — | — | 9 |
| **Total** | **97** | **48** | **51** | **205** |

That's 205 distinct sprites. Add ~10-15% buffer for retries / regenerations / variant splits → plan for **~230 final files**.

---

## 7 · Prompt patterns

The pipeline (§ `v2-pipeline.md`) generates each sprite from a deterministic prompt template substituted with manifest values. Templates below; full per-sprite prompts are written into `docs/v2-prompts/<neighborhood>.txt` during Phase 2 setup.

### 7.1 Building template
```
isometric building sprite, {neighborhood_mood}, {building_description},
materials: {neighborhood_materials},
palette: {neighborhood_palette},
{tech_accent_if_applicable},
single light source warm afternoon sun,
white background, sticker silhouette,
hand-painted soft shadow, no text,
30-degree isometric projection,
clean cartoon style consistent with qtown set
```

### 7.2 NPC template
```
isometric character sprite, {neighborhood_mood} resident,
{role_description}, {clothing_palette},
single neutral pose facing camera-front-right,
white background, sticker silhouette,
soft contact shadow at feet, no text,
clean cartoon style consistent with qtown set
```

### 7.3 Prop template
```
isometric prop, {prop_description},
materials: {prop_materials},
palette: {neighborhood_palette},
no background, sticker silhouette,
soft AO shadow,
clean cartoon style consistent with qtown set
```

### 7.4 Terrain tile template
```
top-down isometric ground tile, {terrain_description},
seamless tileable, palette: {terrain_palette},
soft hand-painted texture, no text, no background bleed,
30-degree isometric projection
```

### 7.5 Negative prompt (all sprites)
```
photorealistic, photograph, modern building, modern clothing,
text, watermark, signature, blurry, low quality, distorted,
multiple subjects, cropped, cut off, perspective lines visible
```

### 7.6 Style anchors (IPAdapter reference images)
- One reference per neighborhood (10 total) curated during Phase 2 setup
- A global reference for "the qtown set look" (sticker-isometric cartoon) — applied to every sprite via IPAdapter
- ControlNet Canny references for buildings (composition lock to 1024×1024 silhouette guide)

---

## 8 · Style consistency strategy

Three layers ensure ~205 sprites feel like one game (full mechanics in `v2-pipeline.md` §§ 3-4):

1. **Base style LoRA** (one, from CivitAI) — defines the global "isometric sticker cartoon white-bg" look that v1's `zavy-ctsmtrc` produced for SDXL. Primary candidate: [Flux Mobile Game Isometric Building](https://civitai.com/models/1901291). Strength 0.8-0.9. No custom training needed in the happy path.
2. **IPAdapter v2 (Flux variant)** — per-neighborhood reference image (strength 0.5-0.7) gives each district its architectural mood, plus a global "qtown set" reference at 0.3 keeps everything in one family. **This replaces what would otherwise be per-district LoRAs** — Flux's multi-LoRA blending issues make IPAdapter the cleaner tool for district variation.
3. **ControlNet Canny** (Flux variant) — composition lock for building sprites against generated silhouette guides. Ensures consistent isometric angle and proportion.

After generation: BiRefNet pass for clean alpha edges → final sprite delivered to `dashboard/public/sprites/`.

**Escape hatch:** if the candidate base LoRAs fail the 5-sprite trial, fall back to training one custom Flux LoRA from v1's existing 76 SDXL sprites (~6-8h on 3090 Ti). See `v2-pipeline.md` § 3.3.

---

## 9 · Acceptance for Phase 1b

This doc is "done" when:
- All 9 neighborhoods + Roads have a complete sprite manifest (§ 6) — **DONE**
- Aesthetic doctrine + palette + materials catalog are unambiguous enough to write Flux prompts from (§ 1-3) — **DONE**
- Per-neighborhood mood is concrete enough to brief an artist or a generator (§ 4) — **DONE**
- Prompt patterns + style consistency strategy are spec'd (§ 7-8) — **DONE**
- User signs off on the manifest before Phase 2 starts

**Open items for Phase 2 setup:**
- Curate the 10 IPAdapter reference images (one per neighborhood + global)
- Source ~150-180 reference images for the 3 architectural-style LoRAs (~50-60 per LoRA)
- Generate per-sprite full prompts (substitute templates with manifest values) into `docs/v2-prompts/<neighborhood>.txt`
- Decide which sprites need ControlNet Canny composition guides vs which run prompt-only
