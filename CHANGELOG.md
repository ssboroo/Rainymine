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
