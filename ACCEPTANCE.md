# RAINYMINE — хүлээн авах шалгалтын төлөв

## Автомат шалгалт

- Synthetic математик control: cardinal/vertical drillholes, analytic arc, spherical variogram, symmetric IDW/kriging, constant reproduction.
- Geodesy control: EPSG:4326 (105E, 0N) → EPSG:32648 (500000E, 0N); projected CRS round-trip and bearing checks.
- Data integrity: mapping/rejected-row provenance, interval overlap, QAQC controls, undo/redo, project migrations and round-trip, atomic save/size protections.
- Geometry: tetrahedron and rectangular drive volume, topology, OBJ/DXF round-trip, self-crossing polygon rejection, constrained TIN edge verification, real slab clipping.
- Estimation: missing support, holdout-hole exclusion, baseline/metrics, domain grid, density/cutoff reconciliation, reproducible input fingerprint.
- Planning: precedence cycle rejection, capacity feasibility, period/tonnage reconciliation. Algorithm is explicitly heuristic.
- Windows: native UI, two viewports, demo block scene, portable executable and installed executable smoke.

## Гадаад баталгаажуулалт — аваагүй

| Шаардлага | Хэрэгтэй зүйл | Одоогийн төлөв |
|---|---|---|
| Бодит уурхайн acceptance | Зөвшөөрөлтэй anonymized collar/survey/assay/lithology/CRS dataset + expected outputs | Өгөөгүй, synthetic fixtures ашигласан |
| Independent estimation benchmark | Хараат бус геологичийн dataset, reference software results, tolerances, review | Хийгдээгүй |
| Нөөцийн ангилал / uncertainty | Density/QC/domain/reasonable prospects болон qualified professional review | Ангилалгүй; бүх model UNCLASSIFIED |
| Engineering mine plan | Геотехник, ramp/support/ventilation, equipment/capacity/haulage, independent engineer review | Prototype geometry ба heuristic schedule |
| Signed installer | Хүчинтэй code-signing identity/certificate, verified signature/timestamp | Сертификат холбогдоогүй; unsigned |
| Бодит төхөөрөмж | Windows 10/11 x64, хэд хэдэн GPU/driver, offline/upgrade/uninstall test log | CI runner-ээс өөр төхөөрөмжөөр шалгаагүй |

Эдгээр дутуу evidence-ийг программ зохиомлоор үүсгэж баталгаажуулсан мэтээр харуулахгүй.

## 0.3.0 шалгалтын нэмэлт

- Two-sample anisotropic analytic weights (2.598 expected grade).
- Two-support ordinary block kriging: point variance 0.151; discrete block variance 0.0755.
- Rotated grid volume / model save-load, large-coordinate covariance rotation invariance.
- Rotated full-cell and local-slice VTK geometry stays inside the reference local grid.
- Top-cut source preservation, per-hole caps, minimum distinct holes, cancellation protection.
- Offscreen Qt parameter dialog with 35 fields: scroll area and visible accept controls.
- Latest Windows build/installed smoke must be checked on the PR commit; local mathematical tests are not a Windows executable test.

## 0.4.0 development controls

Synthetic tests check sub-block volume conservation/coalescing, planar fault separation, project round-trip, hand-calculated haul capacity (3072 t/shift), MILP against exhaustive enumeration, grade-unit conversion and complete/partial external reference matching. These do not complete the independent real-deposit acceptance gate. See docs/EXTERNAL_VALIDATION.md.
