---
docType: analysis
project: migratory-viewer
topic: tech-debt-audit
dateCreated: 20260726
dateUpdated: 20260726
status: complete
---

# Tech Debt Audit — migratory-viewer

Generated: 2026-07-26

## Executive summary

- 0 Critical findings, 2 High, 12 Medium, 13 Low across 27 findings.
- **camera.ts (463 LOC, 9th most modified file) has zero test coverage** and is the most complex state-machine in the viewer. This is the single biggest gap.
- **5 known vulnerabilities** in the Vite dependency chain (2 moderate, 3 high). A `pnpm update vite` resolves them.
- **4 dead exports** in camera.ts remain from a pre-CameraRig refactor — comments say "kept for backward compat" but no caller exists.
- **State layer imports from rendering layer** — `state.ts` depends on `rendering/terrain.ts` for `getTerrainHeight`, creating a circular-ish layering violation (state should sit between protocol and rendering, not reach into rendering).
- **terrain.ts at 587 LOC** is the largest production file and mixes material creation, geometry building, terrain application, and height lookup. Ripe for extraction.
- The **`CameraRig` API uses 13 `as CameraRigState` downcasts** instead of a proper class or closure. Every public function immediately casts its argument.
- **Duplicate resize handler** — both `scene.ts` and `main.ts` independently listen for `window.resize`.
- The `@types/three` devDependency **contradicts the architecture doc**, which correctly notes types are bundled since r152. Risks version-mismatch bugs.
- The architecture doc's file tree lists `ui/legend.ts` which does not exist (legend lives in `hud.ts`).
- Overall the codebase is clean, well-documented, and deliberately built. Test coverage on the protocol layer is excellent. The debt is concentrated in rendering/camera, untested UI code, and a few structural items.

## Architectural mental model

The viewer is a ~6K LOC TypeScript single-page application built with Vite and Three.js WebGPU (r183). It connects to an external Migratory world server over binary WebSocket, receives world state via a custom wire protocol (SNAPSHOT, STATE_UPDATE, TERRAIN), and renders entities and terrain in real-time 3D.

Data flows one-directionally: **WebSocket binary frame → `protocol/terrain-assembler.ts` (dispatch + terrain state machine) → `net/connection.ts` (state mutations via `state.ts`) → render loop in `main.ts` (reads `viewerState`, updates Three.js scene)**. The viewer is a pure consumer — no client-to-server messages.

State management is a single mutable `ViewerState` object (`state.ts`), written exclusively by `connection.ts`, read by everything else. This is simple and effective for the current scope.

The camera system (`rendering/camera.ts`) is a dual-mode rig (orthographic + perspective) with animated transitions, pan/orbit/dolly, and world-bounds clamping. It exposes a narrow `CameraRig` public interface but internally downcasts to `CameraRigState` everywhere.

The protocol layer (`protocol/`) is the strongest part of the codebase: thorough validation, deliberate error tiering (tier-1 drop vs. tier-2 close-1002), and comprehensive tests covering dtype/compression/chunking combinations.

Configuration lives in a single `config.ts` with a flat exported object. The 120-series architecture (world authoring) plans to decompose this into a YAML-driven tiered config system — that refactor has been designed but not yet implemented.

This mental model matches the README accurately. The README is honest and current.

## Findings

| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|----|----------|-----------|----------|--------|-------------|----------------|
| F001 | architectural-decay | src/rendering/camera.ts:148 | Medium | S | Dead export `createCamera` — comment says "thin wrapper so existing callers continue to compile during migration" but no caller exists in the codebase | Delete `createCamera`, `resizeCameraToWorld` (line 200), `handleResize` (line 246), and `updateCamera` (line 299). All four are dead code from the pre-CameraRig refactor. |
| F002 | architectural-decay | src/protocol/deserialize.ts:49 | Low | S | `parseMessage()` is exported but never imported in production code — only used in tests. The terrain assembler calls `parseSnapshot`/`parseStateUpdate` directly. | Remove the export (keep as module-internal if tests need it) or convert tests to use the assembler's `feed()` entry point. |
| F003 | architectural-decay | src/state.ts:12 | Medium | M | State layer imports `getTerrainHeight` from `rendering/terrain.ts`. This creates a downward dependency: state → rendering, when state should sit between protocol and rendering. | Extract `getTerrainHeight` into a shared utility (e.g., `src/terrain-lookup.ts`). Both `state.ts` and `rendering/terrain.ts` import from it. Alternatively, move the `bakeEntityHeights` call to the render loop where the terrain reference is already available. |
| F004 | architectural-decay | src/rendering/terrain.ts:1 | Medium | M | terrain.ts at 587 LOC is above the project's ~300-line target and mixes four concerns: TSL material creation (lines 1–170), unified geometry building (lines 212–453), terrain application (lines 520–557), and height lookup (lines 564–587). | Extract `buildUnifiedGeometry` + `computeTopNormals` into `src/rendering/terrain-geometry.ts`. Extract `createTerrainMaterial` + helpers into `src/rendering/terrain-material.ts`. Keep `applyTerrainToMesh`, `applyFlatPlane`, and `getTerrainHeight` in `terrain.ts` as the public API. |
| F005 | architectural-decay | src/rendering/terrain.ts:176 | Low | S | `getTerrainMaterialHandle()` is exported but never imported anywhere in the codebase — dead code. | Delete the function and the module-level `terrainMaterialHandle` variable (line 173) if no consumer is planned. If slice 122 will use it, document the intent. |
| F006 | architectural-decay | src/rendering/camera.ts:47 | Low | S | `computeZoomFit()` always returns `1` — a stub that was never implemented. Called from `handleRigResize` (line 227) and `zoomBy` (line 438). The zoom-fit clamp is therefore a no-op. | Either implement the zoom-fit calculation or remove the calls and the function. If zoom-fit is intentionally deferred, add a comment explaining what it should do and which slice owns it. |
| F007 | consistency-rot | src/main.ts:26 | Low | S | Duplicate `window.addEventListener('resize', ...)` — `scene.ts:38` updates `renderer.setSize()` and `main.ts:26` calls `handleRigResize(rig)`. Two independent handlers for the same event. | Move the `renderer.setSize()` call into the `main.ts` resize handler (or have `createScene` return a `resizeRenderer()` callback that `main.ts` calls). Single handler, single source of truth. |
| F008 | consistency-rot | src/protocol/deserialize.ts:11 | Low | S | Import path style inconsistency: some files use `.ts` extensions (`from './config.ts'`), others omit them (`from '../config'`). Both work under Vite's bundler resolution, but the drift makes the codebase harder to grep. | Pick one convention and apply it everywhere. The project uses `"allowImportingTsExtensions": true` in tsconfig, so `.ts` extensions are the natural choice. A global find-and-replace fixes this in minutes. |
| F009 | consistency-rot | src/rendering/camera.ts:149 | Medium | M | 13 `as CameraRigState` downcasts throughout camera.ts. The public interface `CameraRig` has 2 readonly fields; every exported function immediately casts its argument to access the 12 additional private fields. This is a de facto class encoded as free functions + a type-narrowing cast. | Refactor `CameraRig` to a class with private fields. The public API stays the same (method names become instance methods). This eliminates all 13 casts and makes the state machine's encapsulation honest. Alternatively, use a WeakMap keyed by `CameraRig` to store the private state — avoids a class but removes the casts. |
| F010 | type-contract-debt | src/config.ts:127 | Low | S | `import.meta.env.VITE_SERVER_URL as string \|\| 'ws://localhost:8765'` — the `as string` cast suppresses `string \| undefined`. If the env var is set to an empty string, the `\|\|` fallback fires (empty string is falsy), which is arguably correct but the cast obscures the intent. | Use a null-coalescing check: `const raw = import.meta.env.VITE_SERVER_URL; const serverUrl = typeof raw === 'string' && raw.length > 0 ? raw : 'ws://localhost:8765';` |
| F011 | test-debt | src/rendering/camera.ts:1 | High | L | camera.ts (463 LOC) has **zero test coverage**. It is the 4th-largest production file, has been modified 9 times in 6 months, and contains a state machine (transition animation), input processing (pan, orbit, zoom), and world-bounds clamping. All untested. | Write unit tests covering: mode toggle and transition animation, pan in ortho and perspective, orbit clamping, zoom limits, `resizeRigToWorld`, and `resetPerspective`. The CameraRig refactor (F009) would make these tests much easier to write. |
| F012 | test-debt | src/ui/hud.ts:1 | Medium | M | hud.ts (214 LOC) has zero test coverage. TPS calculation logic (rolling window), profile legend rebuild, and connection-status DOM update are all untested. TPS calculation involves a time-window trimming algorithm that could have off-by-one errors. | Extract the TPS calculator into a pure function and unit-test it. The DOM manipulation is harder to test without a DOM environment, but the logic can be separated. |
| F013 | test-debt | src/main.ts:1 | Medium | L | The render loop orchestration (world-resize detection, terrain rebuild trigger, tick-change guard) is untested. The conditional logic at lines 44–65 determines when geometry is rebuilt and when entity updates happen — correctness matters for performance. | This is hard to unit-test because it depends on Three.js and the animation loop. Consider extracting the "should rebuild terrain?" and "should update entities?" predicates into testable functions. |
| F014 | test-debt | src/rendering/scene.ts:1 | Low | M | scene.ts (80 LOC) has zero test coverage. The `logBackend` and `registerDeviceLossHandlers` functions fire-and-forget promises that could silently fail. | Low priority — the functions are small and mostly Three.js boilerplate. If tested, mock the renderer. |
| F015 | dependency-config-debt | package.json:19 | High | S | `pnpm audit` reports **5 vulnerabilities** (2 moderate, 3 high) in the Vite dependency chain. Vite 8.0.x has known issues including NTLMv2 hash disclosure (GHSA-v6wh-96g9-6wx3) and PostCSS vulnerabilities. Patched in Vite >=8.0.16. | Run `pnpm update vite` to pull in the patched version. Then re-run `pnpm audit` to confirm zero vulnerabilities. |
| F016 | dependency-config-debt | package.json:19 | Low | S | `@types/three` is listed as a devDependency, but Three.js r183 bundles its own TypeScript definitions. The architecture doc (100-arch.viewer-foundation.md:269) explicitly states "no separate @types/three needed." Having both risks type-definition version mismatch — the separate `@types/three@0.183.1` may diverge from `three@0.183.2`'s bundled types. | Remove `@types/three` from devDependencies: `pnpm remove @types/three`. Verify `tsc --noEmit` still passes (it will — Three.js bundles its own `.d.ts` files). |
| F017 | performance-resource | src/rendering/scene.ts:38 | Low | M | 12 `addEventListener` calls across scene.ts (2), main.ts (1), camera-input.ts (6), and hud.ts (2) with zero corresponding `removeEventListener` calls. In the current single-page-app with no teardown, this is benign. If the viewer is ever embedded as a component that mounts/unmounts, these all leak. | Acceptable for now. If a component lifecycle is introduced, add cleanup: store references to all listeners and remove them in a `destroy()` method. |
| F018 | performance-resource | src/ui/hud.ts:170 | Low | S | `tickTimestamps.shift()` runs in a while loop every render frame. `Array.shift()` is O(n) due to re-indexing. At realistic TPS (30–60), the array has ~60 entries max, so the cost is negligible, but the pattern is suboptimal. | Replace with a circular buffer or maintain a start-index pointer instead of shifting. Alternatively, accept the O(n) cost with a comment noting the max array size. |
| F019 | performance-resource | src/rendering/entities.ts:12 | Low | S | Module-level mutable state `lastAppliedCount` with a `__resetEntityRenderState()` test-only export. Works but is a minor code smell — the double-underscore convention signals the author knew it was a workaround. | If camera.ts is refactored to a class (F009), consider making entities a class too, moving `lastAppliedCount` into instance state. Low priority. |
| F020 | error-handling-observability | src/rendering/scene.ts:43 | Medium | S | `logBackend(renderer)` returns a Promise that is not awaited or caught. If `renderer.init()` rejects, the error becomes an unhandled promise rejection. Similarly, `registerDeviceLossHandlers` at line 46 calls `renderer.init()` again via `void renderer.init().then(...)` (line 75) — a second init call whose rejection is also uncaught. | Consolidate to a single `await renderer.init()` in `createScene` (make it async), then run both `logBackend` and `registerDeviceLossHandlers` synchronously afterward using the already-initialized renderer. This also eliminates the double-init. |
| F021 | error-handling-observability | src/rendering/scene.ts:75 | Low | S | `renderer.init()` is called twice — once in `logBackend` (line 53) and once in `registerDeviceLossHandlers` (line 75). While `init()` is idempotent in Three.js, the double call is wasteful and the second call's error is swallowed by `void`. | Covered by F020's recommendation — consolidate to one `init()` call. |
| F022 | error-handling-observability | src/ui/hud.ts:29 | Low | S | Module-level mutable variables (`smoothFps`, `lastConnectionStatus`, `cachedEntityCount`, `lastTick`, `tickTimestamps`) have no reset path. If the viewer ever needed to reinitialize without a full page reload, these would retain stale state from the previous connection. | Low priority — page reload handles it. If hot-reload or component lifecycle lands, add a `resetHudState()` function (same pattern as `__resetEntityRenderState()`). |
| F023 | documentation-drift | project-documents/user/architecture/100-arch.viewer-foundation.md:269 | Low | S | Architecture doc states "Type definitions are bundled with three since r152 — no separate @types/three needed" but `@types/three` is still in package.json. | Remove `@types/three` (see F016). Update the architecture doc if you decide to keep it. |
| F024 | documentation-drift | project-documents/user/architecture/100-arch.viewer-foundation.md:148 | Low | S | Architecture doc's Component Architecture file tree lists `ui/legend.ts` as a separate file. In reality, the profile legend is built inside `ui/hud.ts`. `legend.ts` does not exist. | Update the architecture doc file tree to remove `legend.ts` and note that the legend is part of `hud.ts`. |
| F025 | documentation-drift | README.md:52 | Low | S | README hardcodes the test count: "145 tests". This will drift as tests are added or removed, creating a stale claim. | Remove the exact count or use wording like "Run the test suite (Vitest)". |
| F026 | other | src/rendering/camera.ts:12 | Medium | S | `createScene` returns a `SceneContext` but there's no `dispose()` or cleanup method. The `renderer`, `scene`, lights, and event listeners created in `createScene` are never cleaned up. If `createScene` is ever called twice (e.g., in a test or HMR scenario), the old renderer and listeners leak. | Add a `destroyScene(ctx: SceneContext)` function that calls `renderer.dispose()`, removes the resize listener, and removes context-loss listeners. Low urgency for production but would help test isolation. |
| F027 | other | src/config.ts:126 | Medium | S | All configuration (33 fields) is a single flat object with no grouping. Camera config, lighting config, biome config, protocol config, and debug flags are all siblings. This makes it harder to find and organize config as the viewer grows. The 120-series architecture plans to decompose this, but until that ships, the flat structure is the working reality. | Acceptable as-is since the 120-series refactor is planned. If that work is delayed, consider grouping into nested objects (`config.camera.fov`, `config.lighting.directionalColor`, etc.) as an incremental improvement. |

## Top 5 — if you fix nothing else, fix these

### 1. F015 — Update Vite to patch 5 known vulnerabilities

```bash
pnpm update vite
pnpm audit
```

This is a 30-second fix with zero risk. The current Vite 8.0.x has 3 high and 2 moderate CVEs, all patched in 8.0.16+.

### 2. F011 — Write tests for camera.ts

camera.ts is 463 LOC, has been modified 9 times in the last 6 months, and has zero test coverage. It contains a state machine (ortho↔perspective transitions with timed animation), input processing (pan in two coordinate systems, orbit with pitch/yaw clamping, zoom with world-bounds enforcement), and multi-camera management. This is the module most likely to regress silently.

Start with:
- `toggleCameraMode` — verify mode changes, transition state, and that double-toggle during animation is blocked
- `panMove` — verify ortho pan moves camera, perspective pan moves orbit target
- `zoomBy` — verify ortho zoom clamps to `[zoomMin, zoomMax]`, perspective dolly clamps to `[dollyMinRatio, dollyMaxRatio]`
- `resizeRigToWorld` — verify frustum recalculation and dolly re-clamp

The current cast-heavy API makes testing awkward — refactoring to a class (F009) first would make the test suite much cleaner.

### 3. F003 — Fix the state → rendering layering violation

`state.ts` imports `getTerrainHeight` from `rendering/terrain.ts`. This makes the state layer depend on the rendering layer, which inverts the intended data flow. The cleanest fix:

```typescript
// src/terrain-lookup.ts — new file, extracted from terrain.ts
export function getTerrainHeight(grid: TerrainGrid | null, x: number, z: number): number {
  // ... bilinear interpolation (unchanged, moved from terrain.ts)
}
```

Both `state.ts` and `rendering/terrain.ts` import from the new shared module. No behavior change, just a dependency direction fix.

### 4. F001 — Delete 4 dead camera functions

```diff
- export function createCamera(...) { ... }
- export function resizeCameraToWorld(...) { ... }
- export function handleResize(...) { ... }
- export function updateCamera(): void { }
```

~50 lines of dead code with comments explicitly stating they're backward-compat wrappers for callers that no longer exist. Deleting them reduces the file from 463 LOC to ~410 LOC and removes cognitive load.

### 5. F009 — Refactor CameraRig casts to proper encapsulation

The 13 `as CameraRigState` casts are a design smell: the type system is being circumvented at every call site. Refactor to a class:

```typescript
export class CameraRig {
  readonly mode: CameraMode;
  readonly activeCamera: THREE.Camera;
  // ... private fields (orthoCamera, perspCamera, pitch, yaw, etc.)

  panStart(screenX: number, screenY: number): void { ... }
  panMove(screenX: number, screenY: number): void { ... }
  // ... etc
}
```

This eliminates all casts, makes the state machine testable via instance methods, and honestly represents the encapsulation boundary. The public API shape doesn't change — callers already pass the rig as the first argument to every function.

## Quick wins

- [ ] F015: Run `pnpm update vite` to patch 5 CVEs (Effort: S, Severity: High)
- [ ] F016: Run `pnpm remove @types/three` — types are bundled since r152 (Effort: S, Severity: Low)
- [ ] F001: Delete 4 dead camera exports — `createCamera`, `resizeCameraToWorld`, `handleResize`, `updateCamera` (Effort: S, Severity: Medium)
- [ ] F005: Delete dead `getTerrainMaterialHandle()` export (Effort: S, Severity: Low)
- [ ] F006: Delete or implement `computeZoomFit()` stub that always returns 1 (Effort: S, Severity: Low)
- [ ] F007: Consolidate duplicate resize handlers into one (Effort: S, Severity: Low)
- [ ] F008: Normalize import path extensions to `.ts` throughout (Effort: S, Severity: Low)
- [ ] F025: Remove hardcoded test count from README (Effort: S, Severity: Low)
- [ ] F020: Consolidate double `renderer.init()` calls into one awaited call (Effort: S, Severity: Medium)

## Things that look bad but are actually fine

- **The `viewerState` singleton is a plain mutable object, not a reactive store or event emitter.** This looks like it should be Redux or Zustand or at least EventTarget. But the data flow is one-directional (connection writes, render loop reads), the viewer is a single-page app with one consumer of each field, and the render loop reads state every frame anyway. A reactive store would add complexity for no benefit here. The architecture doc explicitly makes this case and it's correct.

- **Module-level mutable state in `entities.ts` (`lastAppliedCount`) and `hud.ts` (5 variables).** These look like they should be instance variables on a class or at least passed through a context object. But the viewer creates exactly one entity mesh and one HUD, never tears them down, and the `__resetEntityRenderState()` test helper handles test isolation. This is load-bearing simplicity.

- **The terrain assembler is 508 LOC.** This looks like a god file, but it implements a genuine protocol state machine (IDLE ↔ EXPECTING_CHUNKS) with chunked reassembly, dtype decoding, dequantization, decompression dispatch, and coverage validation. All of that complexity is inherent to the wire protocol specification. It's well-tested (342 + 453 LOC of tests) and the internal functions are appropriately scoped. Splitting it further would scatter the state machine.

- **`parseMessage()` being dead in production (F002).** This is technically unused, but it serves as the obvious "parse any message" entry point and is heavily used in tests. Deleting it would make the test file harder to read. Keeping it exported is a reasonable trade — it's 15 lines and costs nothing at runtime.

- **No vite.config.ts file.** The project runs on Vite defaults, which is fine for a project with zero custom build config. The 120-series architecture will add a config file when the manifest plugin lands. No need to create an empty one preemptively.

- **The `as string` cast on `import.meta.env.VITE_SERVER_URL` (F010).** Vite's env var types are `string | boolean | undefined`. The cast is technically unsound, but the `|| 'ws://localhost:8765'` fallback handles the `undefined` case, and Vite env vars are always strings when defined. The cast is pragmatic, not dangerous.

- **Exponential backoff constants hardcoded in `connection.ts`.** These look like they should be in `config.ts`, but they're implementation details of the reconnect strategy, not user-configurable values. Nobody tunes reconnect backoff via config files. Keeping them as module-level constants is the right call.

## Open questions for the maintainer

- **Is `computeZoomFit()` (camera.ts:47) intentionally deferred?** It always returns `1`, making the zoom-fit clamp a no-op. Was this meant to be implemented in a specific slice, or was the zoom-fit concept abandoned? The `handleRigResize` and `zoomBy` functions both reference it.

- **Is `getTerrainMaterialHandle()` (terrain.ts:176) intended for slice 122?** It's exported but never called. If the 120-series config externalization will use it to update biome materials at runtime, it should stay. Otherwise it's dead code.

- **Is the `legend.ts` file listed in the architecture doc a stale reference or a future intent?** The doc lists it as a separate module, but legend rendering lives in `hud.ts` today.

- **The `@types/three` dependency — was it added intentionally despite the architecture doc's guidance?** Some teams prefer the community types over bundled types for faster IDE feedback. If this was deliberate, the architecture doc should be updated to match.

- **Is `parseMessage()` in `deserialize.ts` kept as a public API for downstream consumers, or is it purely a test convenience?** If it's test-only, it could be un-exported and accessed via the assembler in tests.

<!-- squadron:findings:begin v1 -->
```yaml
findings:
  - id: F001
    category: architectural-decay
    location: src/rendering/camera.ts:148
    severity: Medium
    effort: S
    summary: 4 dead exports (createCamera, resizeCameraToWorld, handleResize, updateCamera) from pre-CameraRig refactor — no caller exists
  - id: F002
    category: architectural-decay
    location: src/protocol/deserialize.ts:49
    severity: Low
    effort: S
    summary: parseMessage() is exported but never imported in production code — only used in tests
  - id: F003
    category: architectural-decay
    location: src/state.ts:12
    severity: Medium
    effort: M
    summary: State layer imports getTerrainHeight from rendering/terrain.ts, creating a layering violation (state depends on rendering)
  - id: F004
    category: architectural-decay
    location: src/rendering/terrain.ts:1
    severity: Medium
    effort: M
    summary: terrain.ts at 587 LOC mixes material creation, geometry building, terrain application, and height lookup — above project's ~300-line target
  - id: F005
    category: architectural-decay
    location: src/rendering/terrain.ts:176
    severity: Low
    effort: S
    summary: getTerrainMaterialHandle() is exported but never imported anywhere in the codebase — dead code
  - id: F006
    category: architectural-decay
    location: src/rendering/camera.ts:47
    severity: Low
    effort: S
    summary: computeZoomFit() always returns 1 — a stub that was never implemented, making the zoom-fit clamp a no-op
  - id: F007
    category: consistency-rot
    location: src/main.ts:26
    severity: Low
    effort: S
    summary: Duplicate window resize handler — scene.ts:38 and main.ts:26 both add independent resize listeners
  - id: F008
    category: consistency-rot
    location: src/protocol/deserialize.ts:11
    severity: Low
    effort: S
    summary: Import path style inconsistency — some files use .ts extensions, others omit them
  - id: F009
    category: consistency-rot
    location: src/rendering/camera.ts:149
    severity: Medium
    effort: M
    summary: 13 as CameraRigState downcasts throughout camera.ts — a class encoded as free functions with type-narrowing casts
  - id: F010
    category: type-contract-debt
    location: src/config.ts:127
    severity: Low
    effort: S
    summary: "import.meta.env.VITE_SERVER_URL as string" cast suppresses string | undefined without explicit null check
  - id: F011
    category: test-debt
    location: src/rendering/camera.ts:1
    severity: High
    effort: L
    summary: camera.ts (463 LOC, modified 9 times in 6 months) has zero test coverage — state machine, pan, orbit, zoom all untested
  - id: F012
    category: test-debt
    location: src/ui/hud.ts:1
    severity: Medium
    effort: M
    summary: hud.ts (214 LOC) has zero test coverage — TPS calculation, profile legend rebuild, connection-status update all untested
  - id: F013
    category: test-debt
    location: src/main.ts:1
    severity: Medium
    effort: L
    summary: Render loop orchestration (world-resize detection, terrain rebuild trigger, tick-change guard) is untested
  - id: F014
    category: test-debt
    location: src/rendering/scene.ts:1
    severity: Low
    effort: M
    summary: scene.ts (80 LOC) has zero test coverage — logBackend and registerDeviceLossHandlers are fire-and-forget promises
  - id: F015
    category: dependency-config-debt
    location: package.json:19
    severity: High
    effort: S
    summary: pnpm audit reports 5 vulnerabilities (2 moderate, 3 high) in Vite dependency chain — patched in Vite >=8.0.16
  - id: F016
    category: dependency-config-debt
    location: package.json:19
    severity: Low
    effort: S
    summary: "@types/three" devDependency contradicts architecture doc — Three.js r183 bundles its own types, risking version mismatch
  - id: F017
    category: performance-resource
    location: src/rendering/scene.ts:38
    severity: Low
    effort: M
    summary: 12 addEventListener calls across 4 files with zero removeEventListener calls — benign in SPA but would leak in component lifecycle
  - id: F018
    category: performance-resource
    location: src/ui/hud.ts:170
    severity: Low
    effort: S
    summary: tickTimestamps.shift() in while loop every frame — O(n) on small array (~60 entries max), suboptimal but negligible
  - id: F019
    category: performance-resource
    location: src/rendering/entities.ts:12
    severity: Low
    effort: S
    summary: Module-level mutable state lastAppliedCount with __resetEntityRenderState() test-only export — minor code smell, already mitigated
  - id: F020
    category: error-handling-observability
    location: src/rendering/scene.ts:43
    severity: Medium
    effort: S
    summary: logBackend(renderer) returns unhandled Promise — if renderer.init() rejects, error is an unhandled promise rejection
  - id: F021
    category: error-handling-observability
    location: src/rendering/scene.ts:75
    severity: Low
    effort: S
    summary: renderer.init() called twice — once in logBackend (line 53) and once in registerDeviceLossHandlers (line 75), second call's error swallowed by void
  - id: F022
    category: error-handling-observability
    location: src/ui/hud.ts:29
    severity: Low
    effort: S
    summary: Module-level HUD state variables (smoothFps, lastConnectionStatus, etc.) have no reset path for reinitialization scenarios
  - id: F023
    category: documentation-drift
    location: project-documents/user/architecture/100-arch.viewer-foundation.md:269
    severity: Low
    effort: S
    summary: Architecture doc says no @types/three needed but package.json still has it
  - id: F024
    category: documentation-drift
    location: project-documents/user/architecture/100-arch.viewer-foundation.md:148
    severity: Low
    effort: S
    summary: Architecture doc file tree lists ui/legend.ts as separate module but legend lives in hud.ts — legend.ts does not exist
  - id: F025
    category: documentation-drift
    location: README.md:52
    severity: Low
    effort: S
    summary: README hardcodes test count "145 tests" — will drift as tests change
  - id: F026
    category: other
    location: src/rendering/camera.ts:12
    severity: Medium
    effort: S
    summary: No dispose/cleanup method for SceneContext — renderer, scene, lights, and event listeners created in createScene are never cleaned up
  - id: F027
    category: other
    location: src/config.ts:126
    severity: Medium
    effort: S
    summary: All 33 config fields are a single flat object with no grouping — camera, lighting, biome, protocol, and debug flags are siblings
```
<!-- squadron:findings:end -->
