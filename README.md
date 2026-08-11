# Iran 3D Peaks

Interactive 3D mountain atlas for Iran, starting with **Mount Damavand**.

The product direction is a real-terrain experience: DEM-derived mountain geometry, satellite imagery, cinematic camera movement, climbing routes, shelters and mountain landmarks. The current branch is the foundation migration from the original Empire Atlas viewer.

## Current status — Phase 1

Phase 1 establishes a peak-native product domain while deliberately keeping the proven Three.js rendering engine stable.

- `Peak` domain model added under `src/types/peak.ts`
- Damavand is the only product dataset rendered at runtime
- peak library and peak information panel replace empire-facing UI
- site/package metadata renamed to Iran 3D Peaks
- a narrow `peakToViewerModel` adapter isolates the legacy viewer contract
- no civilization models are preloaded by the runtime dataset
- real Damavand DEM geometry is intentionally deferred to Phase 2
- real satellite texture is intentionally deferred to Phase 3

The 3D canvas still uses the original Persian GLB as a **temporary rendering placeholder**. That is intentional: Phase 1 validates architecture and product wiring; Phase 2 replaces it with the real Damavand terrain model.

## Architecture

```text
Peak domain
   ↓
src/data/peaks/damavand.ts
   ↓
Peak UI
   ├─ PeakLibrary
   └─ PeakInfoPanel
   ↓
peak-viewer-adapter.ts   ← temporary Phase-1 boundary
   ↓
Existing Three.js ViewerEngine
   ↓
Damavand GLB (Phase 2)
```

The target architecture after the terrain migration is fully data-driven:

```text
PEAKS = [damavand, alamKuh, sabalan, ...]
```

Adding a peak should eventually require only peak metadata, terrain/model assets, routes and hotspots — not viewer changes.

## Development

Requires Node.js 20+.

```bash
npm install
npm run dev
```

Quality gates:

```bash
npm run build
npm run lint
```

## Seven-phase roadmap

1. **Foundation** — peak domain, Damavand-only runtime, stable viewer boundary
2. **Real Terrain Pipeline** — DEM → terrain mesh → optimized Damavand GLB
3. **Satellite Material & Lighting** — aligned satellite texture and mountain lighting
4. **Camera & Cinematic Experience** — intro flight, orbit, camera constraints and presets
5. **Routes & Mountain Intelligence** — GPX routes projected onto terrain
6. **Hotspots & Peak UI** — summit, shelters, landmarks, hazards and final product UI
7. **Production Hardening** — LOD, texture compression, caching, mobile GPU handling and tests

## Upstream

This repository began as a fork of `thebuggeddev/empire`, whose Three.js viewer architecture is being adapted for a mountain-specific experience. The upstream repository currently does not declare a license, so reuse/distribution of upstream code should not be assumed to grant commercial rights without permission from the original author.
