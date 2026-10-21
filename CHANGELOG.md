# Өөрчлөлтийн түүх

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
