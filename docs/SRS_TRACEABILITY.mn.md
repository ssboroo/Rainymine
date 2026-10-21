# Mining Platform SRS — хэрэгжилтийн мөрдөх хүснэгт

2026-10-22. Эх: хэрэглэгчийн `Pasted markdown(6).md` техникийн шаардлага.
Энэ баримт нь гүйцэтгэлийн баталгаа, нөөцийн гэрчилгээ биш. Одоогийн архитектур:
Qt 6 / PySide6 desktop, C++ VTK OpenGL, NumPy/SciPy native тооцоолол, оффлайн .rmine JSON.
Python UI-г бүхэлд нь C++/Rust болгох, веб сервер нэмэх нь одоогийн Windows/offline зорилгын зайлшгүй нөхцөл биш.

| SRS | Одоогийн хэрэгжилт / нотлох код | Үлдэгдэл / хүлээн авах шалгуур |
|---|---|---|
| MOD-01 CSV/TXT/XLSX | CSV багана mapping, delimiter, transaction validation; XLSX values (`data_tools`, `exchange`) | Ерөнхий TXT grammar тодорхойгүй; Access, DWG, SHP, LAS, GeoTIFF, DM, STR тусгай уншигч дутуу. DWG/DM SDK болон бодит fixture шаардлагатай. |
| MOD-01 schema | Collar, Survey, Assay, Lithology тусдаа хүснэгт, метр, CRS, нэг grade unit | Олон элемент Au/Cu зэрэг хадгалах schema, Status, Alpha/Beta structural log дутуу. Одоогийн scalar grade-г чимээгүй олон элемент гэж тайлбарлахгүй. |
| MOD-01 desurvey | Minimum curvature 3D үндсэн замнал; balanced tangential / radius of curvature сонголттой CSV экспорт (`core`, `srs_ui`) | Экспортын өөр арга 3D/үнэлгээний үндсэн замналыг өөрчлөхгүй. Бүх pipeline-д арга сонгох бол metadata/cache migration хэрэгтэй. |
| MOD-01 validation | Missing collar, давхардал, интервал overlap/гүн/тоон утга, QA/QC coverage; 3D dogleg degrees/30m босгын тайлан | Алдаатай эх файлыг автоматаар засахгүй. Нэгдсэн олон алдааны import issue grid бүрэн биш. |
| MOD-02 view | Ортографик/перспектив, хоёр viewport, absolute XYZ ба дурын slab, давхаргын style, жинхэнэ picking (`scene`, `navigation`, `viewing`, `workspace`) | Vertex/interval picking, transform gizmo дутуу. 1M цэг 60 FPS, 5M блокийн GPU instancing батлагдаагүй; өнөөгийн 32 MB/100k row/5000 collar хязгаар хэвээр. |
| MOD-03 explicit | String/polygon, огтлолуудын loft, TIN/breakline, DXF/OBJ/STL, topology/volume | Interactive snapping, self-intersection repair, robust CSG union/intersection/difference дутуу. Хаалттай mesh гэдэг нь self-intersection байхгүй гэсэн баталгаа биш. |
| MOD-03 implicit | Орон зайн RBF grade isosurface, локал координат, bounded resolution, degeneracy cleaning (`implicit`) | Cubic/TPS kernel UI, lithology/contact signed constraints, structural trends, fault-constrained implicit дутуу; extrapolation мэргэжлийн хяналттай. |
| MOD-04 compositing | Fixed length, overlap-уртаар жинлэлт, coverage; литологийн хил бүрээс эхлэх fixed bins (`srs_tools`) | Логгүй интервалыг литологийн үр дүнд оруулахгүй; gaps тэг агуулга болохгүй. |
| MOD-04 variography | Experimental directional variogram, spherical fit, rotated covariance ellipsoid (`estimation`) | Exponential/Gaussian fit, 3D variogram map дутуу. |
| MOD-04 block | Rotated grid, boundary adaptive subblocks, domain/fault restrictions | Одоогийн тоо/санах ойн хязгаарууд; multi-million performance архитектур дутуу. |
| MOD-04 estimation | NN, IDW, OK, SK; block support quadrature, topcut, per-hole cap, cross-validation | Indicator kriging, independent geological benchmark, multi-pass production validation дутуу. |
| MOD-04 validation/report | Cross-validation, external CSV benchmark, cutoff volume/tonnage/grade; XYZ swath график+CSV, length/volume weighting ба missing support (`srs_tools`, `srs_ui`) | Swath нь block/sample centre bin; boundary clipping integration биш. JORC/NI 43-101 автоматаар баталгаажуулахгүй; Competent/Qualified Person хяналт дутуу, UNCLASSIFIED хэвээр. |
| MOD-05 pit | Economic maximum-closure prototype, conservative slope graph, voxel envelope; circular benches (`optimization`, `planning`) | Whittle/LG commercial equivalence батлагдаагүй. Ramp/spiral, turning radius, pushbacks, geotechnical sectors, economic unit verification дутуу. |
| MOD-05 underground | Шулуун drive geometry | MSO stope optimizer, fan/ring blast engineering дутуу. |
| MOD-06 survey | Delaunay TIN, mesh эзэлхүүн/тайлан | Surface-to-surface exact cut/fill, Z slice integration, LAS/UAV streaming дутуу. |
| MOD-07 schedule | Capacity/precedence greedy, optional economic MILP, route/fleet scenarios | Gantt editor, multi-period blending/mining coupled optimum дутуу. |
| MOD-07 blend | HiGHS LP: тонн тэнцэл, grade interval, feed availability, хамгийн бага feed cost; infeasible үед partial хольцгүй (`srs_tools`) | Нэг үеийн тасралтгүй feed; олборлолтын precedence, discrete blocks, recovery, олон элемент орохгүй. |
| Storage | Atomic .rmine JSON, undo/redo, backup, lazy Qt block grid | DuckDB/Parquet store, spatial persistent index, streaming, schema migration дутуу. JSON-г нэр солиод Parquet гэж үзэхгүй. |
| Platform | Windows source/frozen/installed EXE smoke CI, software rendering fallback, portable offline AI | Физик GPU/Windows hardware acceptance, million-block frame-time benchmark, signed installer certificate дутуу. |

## Шинэ хэрэгслүүдийг ашиглах

`Шинжилгээ / SRS` цэсээс замнал CSV, литологийн композит, XYZ swath, survey dogleg, хүдэр холих LP нээнэ.
Swath графикийг хаахад түүхий харьцуулалтын хүснэгт нээгдэж CSV экспорт хийнэ.
Хольцын CSV баганууд: `hole_id,tonnes,grade,cost_per_tonne`; hole_id нь материалын давтагдашгүй ID.
Агуулгын нэгж нь төслийн нэгжтэй, бүх зардал нэг валюттай байна. Эдгээр тайлан төслийг засварлахгүй.

## Дараагийн томоохон үе шат

1. Бодит anonymized fixture ба хараат бус геологичийн expected results-ийг import/desurvey/estimate/report бүрээр батлах.
2. Parquet/DuckDB schema + migration + chunked IO; million-block benchmark-ийг тодорхой CPU/GPU/RAM дээр хэмжих.
3. Robust mesh/CSG болон geometry predicates, snapping; дараа нь contact/fault-constrained implicit modelling.
4. Unit-aware pit economics, engineering-reviewed ramps/MSO; scheduling/ore blending-ийг холбох.
5. Формат бүрийн лиценз/SDK ба fixture acceptance, физик Windows/GPU QA, code signing.

Шалгалт: `python -m unittest tests.test_srs tests.test_core` нь аналитик траектор, station continuity,
литологийн хил, missing support, swath weighting, LP-ийн аналитик optimum/infeasibility-г шалгана.
