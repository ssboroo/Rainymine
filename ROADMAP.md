# RAINYMINE — Product Roadmap to a Professional Mining Workflow

**Status:** 0.3.0 implementation checkpoint; release gates below remain applicable
**Product direction:** Mongolian-first, Windows desktop, integrated 3D geology and mine-planning workflow  
**Principle:** a feature is not production-ready until it has deterministic tests, documented limits, representative datasets, and domain-expert review where required.

The 0.3.0 workbench adds geometric-anisotropic covariance, discretized block-support approximation, rotated parent grids, directional variograms and estimation controls. These additions do not close the independent-review gates below. The initial desktop foundation provides for drillhole CSV import, minimum-curvature drillhole traces, assay interval coloring, a Delaunay TIN surface, compositing, project persistence, and Windows packaging automation. This roadmap does not imply that the capabilities below already exist.

## Release gates

- **Gate A — Data integrity:** preserve source data, explicit units and CRS, reproducible imports, validation reports, and safe undo/recovery.
- **Gate B — Geological geometry:** geometry editing and exchange formats validated against known reference files.
- **Gate C — Estimation:** independently verified algorithms, reproducible parameters, cross-validation, and geologist sign-off.
- **Gate D — Resource reporting:** transparent assumptions and audit trail; no claim of a compliant mineral resource or reserve without qualified-person review under the applicable reporting code.
- **Gate E — Mine planning:** constraints and schedules reconciled against engineering checks and scenario tests.
- **Gate F — Distribution:** large-data benchmarks, Windows hardware testing, installer integrity, and code signing.

## Phase 1 — Reliable geological data foundation

1. Import anonymized collar, survey, assay, and lithology datasets from real projects with written permission.
2. Add an import wizard with column mapping, preview, type inference, missing-value handling, duplicate detection, and reusable mapping profiles.
3. Make CRS a validated project property. Support explicit source and target CRS, unit checks, coordinate transformation, and transformation metadata. Never silently reinterpret geographic degrees as projected metres.
4. Add an editable data grid with validation feedback, source-row provenance, filtered views, and safe edit history.
5. Add assay QA/QC workflows: standards, blanks, duplicates, control limits, batch summaries, detection-limit flags, and exportable exception reports. Do not silently delete outliers.
6. Add repeatable anonymized fixture datasets and import regression tests. Keep confidential source data out of the public repository.

**Acceptance:** import reports show accepted/rejected rows and reasons; coordinate transformations match known control points within documented tolerances; original source files remain unchanged; QA/QC results can be reproduced from saved settings.

## Phase 2 — Geological interpretation and geometry exchange

1. Model lithology intervals and named geological domains with explicit interval-overlap and gap checks.
2. Add editable strings and polygons with snapping, vertex editing, closure checks, and undo/redo.
3. Add DTM breaklines, boundaries, holes/voids, and constrained triangulation; document limitations around faults and steep walls.
4. Add wireframe and closed-solid workflows with mesh validity checks: open edges, non-manifold edges, self-intersections, orientation, and volume.
5. Implement DXF and OBJ import/export with coordinate-system and unit metadata where the format supports it.
6. Add reference geometry fixtures and round-trip tests.

**Acceptance:** edits are reversible; invalid solids are clearly flagged; supported geometry survives export/import within documented tolerances; no surface is described as fault-aware unless constraints are actually honored.

## Phase 3 — Block model and geostatistics

1. Define block-model origin, rotation, parent/sub-block dimensions, attributes, and domain membership.
2. Implement domain constraints and explicit treatment of composites, missing samples, top cuts, search ellipsoids, and estimation parameters.
3. Add IDW and ordinary kriging as separately testable estimators.
4. Add experimental variograms and model fitting with direction, lag, tolerance, nugget, structures, and anisotropy parameters exposed to the user.
5. Add cross-validation: bias, MAE/RMSE, residual plots, observed-versus-estimated plots, and comparison against simple baselines.
6. Persist all estimation settings and software/version metadata with each run.
7. Benchmark algorithms against independent, reviewed reference cases before using them for professional decisions.

**Acceptance:** unit and property tests cover edge cases; a reproducible estimation report records parameters and input data fingerprint; cross-validation is available; an independent geologist reviews benchmark outputs. Never market algorithm output alone as a validated resource estimate.

## Phase 4 — Tonnage, grade, uncertainty and resource reporting

1. Calculate block volumes and tonnage using documented density fields and unit checks.
2. Generate cutoff-grade scenarios and tonnage-grade tables with explicit inclusion rules and domain filters.
3. Report missing density, unestimated blocks, edge effects, and sensitivity to cutoff and key assumptions.
4. Distinguish interpolation output, exploration targets, and classified mineral resources/reserves.
5. Add audit trails, versioned assumptions, report templates, and review/approval records.
6. Require qualified-person review and compliance checks against the reporting code selected for the project before any public resource/reserve statement.

**Acceptance:** independent calculations reproduce report totals; all assumptions are visible; uncertainty and classification are not inferred solely from grade estimates or kriging variance.

## Phase 5 — Mine design, scheduling and optimization

1. Build open-pit design primitives and constraints: benches, berms, ramps, slope sectors, minimum widths, and geometric validation.
2. Add underground design only as a separately scoped module with method-specific constraints.
3. Add production phases, mining blocks, precedence, mining capacity, processing capacity, haulage and stockpile assumptions.
4. Add scenario-based scheduling and optimization with transparent objective functions and constraints.
5. Validate plans against geometry, tonnage, grade, capacity, and schedule reconciliation reports.
6. Keep engineering assumptions editable, versioned, and reviewable.

**Acceptance:** schedules reconcile to source blocks and capacity limits; infeasible scenarios report why; optimization results are reproducible and compared with a documented baseline.

## Phase 6 — Scale, usability and Windows delivery

1. Profile realistic large drillhole, assay, surface, and block-model datasets; define benchmark fixtures and target hardware.
2. Add spatial indexing, lazy loading, background processing, cancellation, progress reporting, and memory-aware rendering where benchmarks justify them.
3. Add robust undo/redo, coordinate picking, synchronized multiple viewports, section tools, and selection/highlighting consistency.
4. Improve crash recovery, autosave, project migrations, and corrupted-file diagnostics.
5. Run Windows 10/11 x64 tests on more than one real device and GPU/driver configuration; record the tested matrix.
6. Build reproducible portable and installer packages; generate checksums and software version metadata; sign releases with a managed code-signing certificate when available.
7. Test installation, upgrade, uninstall, offline launch, file associations, and clean-machine startup.

**Acceptance:** published release notes state exactly which tests ran, on which environment, and which limitations remain. A CI runner smoke test is not described as validation on every real Windows device. Code signing is not claimed until a signed artifact is verified.

## Test and evidence strategy

- Keep synthetic fixtures for unit tests and deterministic regression checks.
- Use anonymized real-world datasets only with authorization; document how anonymization affects coordinates, grades, geology, and QA/QC interpretation.
- Keep an independent benchmark dataset separate from development fixtures.
- Record expected results, tolerances, data provenance, algorithm parameters, and reviewer sign-off.
- Test CSV parsing, CRS transformations, geometry validity, estimator correctness, numerical stability, save/load round trips, performance, and packaged application behavior.
- Treat failed checks as visible errors; do not silently repair or discard material data.

## Recommended execution order

1. Audit the current implementation and test coverage.
2. Complete Phase 1 data integrity and CRS handling.
3. Deliver Phase 2 geometry editing and exchange.
4. Implement and independently validate Phase 3 estimation.
5. Add Phase 4 reporting with explicit professional review gates.
6. Build Phase 5 mine planning.
7. Complete Phase 6 performance, real-device testing, and signed distribution.

This roadmap is a plan, not a claim that these modules are implemented. Each phase should be split into small reviewable pull requests with tests and evidence.
