# SRS v2 engineering — 2026-10-22

- RTC block-only origin fix, stable curvature series and upward holes.
- Version 3 project schema: Structure/Geotech; backward v1/v2 reads and typed CSV mapping.
- VAL-01…10 preflight, explicit assay-tag policy, oriented-core and density-weighted composites.
- Exponential/Gaussian estimation covariance, support-aware KE/SoR.
- Atomic Morton-sorted Zstd Parquet, Arrow SoA filter scanning and bounded desktop import.
- Optional regular-grid exposed-face surface extraction with original VTK block IDs.
- Frozen Windows dependency checks and engineering acceptance/limitations documentation.

# SRS additions — 2026-10-22

- Analytical balanced tangential / radius-of-curvature trajectory CSV exports; primary 3D remains minimum curvature.
- Lithology-boundary composites with explicit assay coverage.
- Weighted XYZ swath chart/CSV and true 3D survey dogleg reporting.
- Minimum-cost single-period feed blending LP, strict capacity/grade validation and explicit infeasibility.
- Native SRS analysis menu and requirement-by-requirement traceability with unimplemented scope.

## 0.9.0

- Adopt the selected geological-strata/drillhole identity in editable SVG, PNG, ICO and a code-native startup screen.
- Add reversible Mongolian/English display localization, a persisted language selector and reviewed English local-help topics without translating project data or calculation keys.
- Keep every active ribbon tool reachable through the complete tool library and command search; document the live tool inventory.
- Render full demo blocks with edges, translucent terrain, a clearly synthetic fault guide, world-coordinate grid, reversible cutaway and linked property inspection.
- Test both locales, cutaway pick identity, unchanged data, installed English EXE and silent uninstallation in Windows CI.
- Correct dark-splash logo contrast with the shared reverse mark and generated geological background; keep wordmark, year and real progress separate from the artwork.

## 0.8.0

- Merge current main's startup artwork, native icon system, command search, focus/ribbon controls and selected-hole labeling with the 0.7 workspace, lazy block grid and seven-day trial.
- Preserve installer identity, source/packaged/installed checks, local AI scope and signed device activation; use one 0.8.0 version throughout Windows packaging.
- Add Mongolian brandbook, reusable SVG brand board and README logo/startup documentation.
- Reconstruct the conflict resolution with Git CLI in CI and compare the resulting tree before building the Windows installer.

## 0.7.0

- Implement native 2026 reference workspace: light/teal palette, six ribbon categories, grouped layer tree, viewport modes, lazy block table and visible local assistant.
- Preserve geology workflows, picking, sections, project save and seven-day licensing.
- Update reviewed help paths to match moved tools; add code-native vector brand and icon system.
- Distinguish reference poster imagery from actual project geometry and unimplemented splash artwork.

## 0.6.0

- Explicit 168-hour trial; Windows DPAPI file/registry anchors and rollback checks.
- Mongolian activation/status dialog, periodic expiry enforcement, save path preserved.
- Device-bound Ed25519 license verification and separate password-encrypted owner issuer tool. No private keys included; owner public key configuration pending.
- Traceable release kit, checksums, inventory and draft-only packaging pipeline.

## 0.4.0

- RBF grade isosurface, economic maximum-closure pit, exposed voxel envelope; UI, project persistence.
- XLSX mapping workflow; ASCII/binary STL; read-only SQL Server canonical-view adapter.
- Windows source/frozen/installed smoke exercises RBF, HiGHS, Excel, STL, pyodbc load and actual 3D meshes.
- Geobank live server, proprietary mining formats, fault-aware solid, engineering optimization benchmark remain external acceptance gates.

## Геостатистикийн нэмэлт (хөгжүүлэлт)

- Nearest Neighbour, spherical covariance Simple Kriging; SK known mean-ийг хэрэглэгч тодорхойлно.
- Point-support тооцоо; нөөцийн ангилал, мэргэжлийн баталгаажуулалт агуулаагүй.

# Өөрчлөлтийн түүх

## 0.3.0 — 2026-10-21

- Linked 3D drillhole/block picking and persisted per-layer visibility, opacity, RGB/scalar colors and representations.
- Named sections, previous/next section navigation and movable orthogonal block slices.
- Visible, slab-clipped selection highlights and synchronized properties in both viewports.
- Preserves reusable CSV mapping profiles from the existing main branch.

## 0.2.0 — 2026-10-21

- Цайвар scientific workspace, purple ribbon, custom vector icons, Properties/layers, хоёр viewport, coordinate picking.
- CSV mapping/preview/provenance, editable grid, undo/redo, литологи, CRS transform, QAQC controls.
- String/polygon vertex editor, constrained TIN, OBJ/DXF exchange, mesh topology/volume checks.
- Experimental block-centre IDW/ordinary kriging, isotropic variogram/fit, leave-one-hole-out validation ба charts.
- Unclassified density/cutoff tonnage-grade tables; bench/drive prototypes and capacity-constrained greedy schedule.
- `.rmine` schema v2, v1 migration. Бодит өгөгдөл/геологич/signing/device evidence хүлээгдэж байна.

## 0.1.0 — 2026-10-21

- Монгол хэлтэй Qt/VTK desktop ажлын орчин.
- Өрөмдлөг, survey, сорьц, гадаргын CSV импорт; minimum curvature 3D замнал.
- Жинхэнэ босоо slab clipping, гадаргын TIN, 3D зай хэмжилт.
- `.rmine` локал төсөл; композит, замнал, PNG, VTP, HTML экспорт.
- Математик, өгөгдөл, VTK scene тест; Windows EXE/суулгагчийн CI.

Туршилтын хувилбар. Блок модель, кригинг, нөөцийн ангилал болон уурхайн төлөвлөлт ороогүй.

## Unreleased

- Reusable named CSV column mappings saved per import kind inside the project, with explicit application, missing-column checks and undo/redo.
- Reject empty/duplicate CSV headers and report short/extra-field rows instead of silently dropping values.
- Regression coverage for profile persistence, transactional history and malformed CSV input.

- Rotated search ellipsoids (azimuth, dip, roll) in estimation and cross-validation. Physical-distance IDW and isotropic kriging covariance remain unchanged.
- Directional experimental variograms with angular tolerance, perpendicular bandwidth, saved settings and exploratory spherical fits.

## 0.3.0 — Advanced estimation workbench

- Separate geometric-anisotropic spherical covariance ranges/orientation from search rotation.
- Discretized IDW and ordinary block kriging approximation with 1–4 midpoint supports per axis, common centre-selected neighbourhood, and within-block semivariance correction.
- Rotated parent-block geometry, local-axis slices, rotation metadata in project/CSV, invariant volumes, and rejection of unsupported rotated-grid scheduling.
- Non-destructive top cuts, maximum samples per hole, minimum distinct holes, capped counts, status summaries and reproducible run fingerprints.
- Scrollable estimation dialogs, updated in-app help, Windows package version 0.3.0.
- Analytical anisotropy/block-variance controls, rotation/render/persistence tests. Independent deposit benchmark, sub-blocks and professional certification remain pending.

## 0.4.0 — Geological barriers and planning scenarios

- Centre-sampled adaptive sub-blocks with sibling coalescing and explicit resolution limits.
- Infinite planar fault barriers for estimation, validation and variogram pairing; guide meshes without displacement modelling.
- Polyline gradient checks and constant-speed fleet cycle/capacity scenarios.
- Economic optional-task HiGHS MILP with capacity, strict predecessor periods, discounting and solver status/gap.
- External reference CSV comparison, complete matching, provenance hashes and CLI; independent real-deposit review remains pending.

## 0.5.0 — Local software-support assistant

- Native Mongolian support dock, background setup/inference, cancellation and model process cleanup.
- Pinned llama.cpp CPU runtime + Qwen3-1.7B Q4_K_M model, SHA256-checked atomic downloads and model-included offline portable ZIP.
- Strict reviewed-help-ID output; no arbitrary generated instructions, project access, file changes, commands or general chat.
- Localhost-only authenticated process, no proxy/redirect, no cloud inference or API credentials.
- Offline manual help when model unavailable; scope, invalid output, asset integrity and process-boundary tests.
