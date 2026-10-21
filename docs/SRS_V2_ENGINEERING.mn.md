# SRS v2.0 — инженерийн хэрэгжилт, нарийвчлал, үлдэгдэл

2026-10-22. Хэрэглэгчийн `download.pdf` (Mining Software Platform SRS v2.0)-д тулгасан нэмэлт.
Энэ баримт нь хэмжээгүй GPU/SLA үзүүлэлтийг биелсэн гэж батлахгүй.
Өмнөх шаардлагын матриц: [SRS traceability](SRS_TRACEABILITY.mn.md).

## Нэмэгдсэн бодит хэрэгжилт

| Шаардлага | Хэрэгжилт | Хязгаар / нотолгоо |
|---|---|---|
| RTC local origin | VTK-д дэлхийн double координатаас origin-ийг хасна. Collar/surface байхгүй block/mesh/string-only төсөлд origin сонголтыг зассан. `engineering.rtc_buffer` нь хасалтыг float64 дээр хийсний дараа contiguous float32 болгоно. | UTM 5,300,000 м дээр 1 мм-ийн ялгааны тест. Бүх ордын хэмжээ/камерын нөхцөлд jitter арилсны hardware баталгаа биш. |
| Minimum curvature | β<0.001 rad үед `1+β²/12+β⁴/120`; завсрын гүнд SLERP хэвээр. | Аналитик quarter-circle, straight, station continuity, бараг параллель tangent тест. |
| 6 үндсэн хүснэгт | Collar/Survey/Assay/Lithology дээр Structure ба Geotech нэмэгдсэн. Багана mapping CSV, XLSX generic импорт, project save/load, undo/redo validation замаар орно. | Доорх schema нь хамгийн бага бодит хэрэгжилт; PDF-ийн бүх лаборатори/нүүрс/гэрээлэгчийн атрибут хараахан нэмэгдээгүй. |
| Upward drillholes | Grid azimuth north-clockwise; dip −90°…+90°, эгц дээш +90°. | Өмнөх сөрөг налууны бүх тест хадгалагдсан; дээш чиглэсэн analytic trajectory нэмэгдсэн. |
| Oriented core | Equation 12-ийн `Rz(−azimuth) Rx(dip+90)` ENU хувиргалт, upward hemisphere normal, true dip/dip direction. | Beta нь доод лавлах шугамаас; өөр төхөөрөмжийн beta convention хөрвүүлэхгүй. Horizontal plane direction=None; vertical plane direction 180° ambiguity-г тэмдэглэнэ. |
| VAL-01…10 | `validation.validate_tables`: raw мөрүүдээс бүх issue цуглуулна; code/severity/table/1-based row/hole/field/message. Current project эсвэл нэг CSV-г урьдчилж шалгана. | Readonly тайлан; async clickable error inspector болон auto-fix хараахан биш. Structure/geotech typed admission validation тусдаа ажиллана. |
| Assay tags | `parse_assay_tag`: `<DL`, NS/SNR/IS/хоосон; default NULL, half-DL зөвхөн ил тод сонгосон policy үед. | Анхны source/qualifier хадгална. Автомат import substitution хийхгүй. Unknown tag нь алдаа. |
| Spatial outlier | Mean ±4σ ба optional DTM callback-аас ΔZ>15 м. | Outlier бол warning; геологийн бодит outlier-ийг автоматаар засахгүй. UI current/CSV шалгалтад DTM callback холбоогүй. |
| Density compositing | Нэг цооногийн ижил cross-section интервалд overlap-length × density жинлэнэ. Coverage болон support-ийг тусад нь тайлагнана. | Density нь заавал өгөгдсөн байх; missing interval тэг grade болохгүй. Олон цооног / multi-element / lithology-density combined pipeline биш. |
| Variogram | Spherical, exponential, Gaussian covariance сонгох; isotropic/anisotropic estimation-д ижил family хэрэглэнэ. | Nested structures, 3D fan map болон family-aware fit UI дутуу; одоогийн fit нь spherical хэвээр. |
| Kriging KE/SoR | `block_variance=Cvv`, `KE=1−error_variance/Cvv`, `SoR=Cov(true,predicted)/Var(predicted)`; support-average covariance ба weight-аар бодно. | OK/SK, шинэ тооцоонд хадгална; хуучин блокт буцаан зохиохгүй. Degenerate denominator=None. KE сөрөг байж болно; 0…1-д шахахгүй. Нөөцийн ангилал биш. |
| Exposed faces | Uniform parent-grid-ийн дотоод талстуудыг CPU дээр хасаж, VTK cell бүрт original block_index үлдээнэ. 3³ блокийн 162 face →54 face. | Зориуд сонгох surface-only горим; огтлоход дотор тал үүсгэхгүй. Sub-block adjacency, GPU instancing биш; adaptive блокийг reject хийнэ. |
| Morton/SoA | 21-bit ×3 интерleave, 63-bit утгыг uint64-д хадгална. Arrow баганан массив, stable spatial sort, original row_id ба octree block_id/level хадгална. | Morton spatial sort key нь unique octree ID биш. Tie үед row_id хэвээр. Нэг тэнхлэгт 2²¹ quantized cell-ээс ихийг reject хийнэ. |
| Parquet | Atomic write, Zstd level3, row groups 262144, numeric byte-stream-split, per-column stats, metadata origin/CRS/unit/model params. Predicate-pushdown scanner batch≤262144, GUI materialization≤50000 блок. | Scientific координат/grade-г float64 дээр хадгалж PDF-ийн float32 disk schema-гаас санаатай зөрүүлсэн. GPU fp32 тусдаа. Project .rmine-г орлуулах migration биш. |
| Windows package | PyArrow 19.0.1 pinned, frozen dependency collection; Parquet write/read/scan, RTC, Morton, oriented core, density composite нь EXE smoke-д орсон. | Physical GPU benchmark доорх acceptance хэвээр. |

## Хүснэгтийн хамгийн бага шинэ schema

- `Structure`: hole_id, depth, alpha, beta, feature_type. Depth нь collar-д багтана, alpha 0…90, beta 0…<360.
- `Geotech`: hole_id, from_m, to_m, rqd_pct, tcr_pct, ucs_mpa, jrc. Тоон хэмжилт байхгүй бол persisted model-д None; бодит хэмжилт гэж 0 зохиохгүй. RQD/TCR 0…100, RQD≤TCR, UCS≥0, JRC 0…20; давхардсан интервал reject.
- CSV mapping-д дээрх бүх нэрлэсэн багана шаардана. Дутуу хэмжилттэй Geotech typed Python API нь None дэмжинэ; CSV blank mapping хараахан optional биш.
- `.rmine` шинэ бичилт format v3. v1/v2 нь structure/geotech=[] default-тай уншигдана; хуучин EXE нь v3 файлыг уншихгүй тул эх файлаа overwrite хийхээс өмнө хувилбартай backup хадгална.
- Multi-element assay, Sample_ID relational uniqueness, нүүрсний бүх шинжилгээ, full contractor/status/instrument schema, database FK cascade нь бүрэн болоогүй.

## Parquet хэрэглээ ба contract

`Шинжилгээ / SRS → Morton Parquet экспорт / Parquet блок импорт`.
Импорт нь ижил CRS code ба grade_unit шаарддаг; өөр CRS-г чимээгүй холбохгүй.
`scan_block_batches(path,bounds,columns,batch_size)` нь bounded Arrow SoA batches өгнө;
bounds нь world XYZ centre-ийн inclusive муж, scanner локал origin-ийг хөрвүүлж шүүнэ.
Энэ нь block volume-ийн intersection filter биш. Compressed Parquet нь decode хийх RAM шаарддаг;
`memory_map=True` гэдэг нь compressed буферийг zero-copy болгох амлалт биш.
Atomic write бүтэлгүйтвэл өмнөх файл хэвээр, амжилттай бол tempfile-ийг replace хийнэ.

PyArrow implementation reference:
https://arrow.apache.org/docs/19.0/python/generated/pyarrow.parquet.write_table.html

## Баталгаажуулаагүй / дараагийн инженерийн ажил

1. Logarithmic depth shader, Eye-Dome Lighting, LiDAR LAS/LAZ octree/LOD streaming, GPU instancing, GPU cutoff shader. “0 ms” latency физикийн бодит хэмжилт биш; frame-time budget-ээр шалгана.
2. 10M блок /50M LiDAR /60 FPS, Parquet 10M filter<0.3s, RAM/VRAM/SLA: RTX4060/32GB/NVMe зэрэг тодорхой төхөөрөмж дээр хэмжээгүй. Fixture, camera path, median/p95 frame time, cold/warm cache, selected fraction, memory peak-ийг нийтэлсний дараа pass/fail тогтооно.
3. FMM / H-matrix RBF O(N logN), contact/fault-constrained implicit, watertight two-manifold+self-intersection repair/CSG. Одоогийн RBF нь SciPy bounded local interpolation.
4. Hochbaum pseudoflow/Lerchs–Grossmann commercial parity, geotechnical sectors, инженерийн ramp/MSO/ring blast. Одоогийн max-closure prototype нь эдгээртэй ижил баталгаажсан бүтээгдэхүүн биш.
5. Coupled multi-period extraction+stockpile+multi-element blending MILP; одоогийн scheduling MILP ба feed LP тусдаа.
6. PostGIS/DuckDB full relational backend, Parquet external merge sorting, stream-native estimation/rendering. Одоогийн writer sorting нь source model-ийг RAM-д авна; 50M export гэж амлахгүй.
7. >50ms ажиллагааны worker/cancel graph болон 100 delta-command undo; одоогийн generic numeric dialogs main-thread busy wrapper ашигладаг.
8. JORC/NI43-101/ЭБМЗ A/B/C1/C2 ангиллыг автоматаар ижилсүүлэхгүй. KE/SoR-оос ганц босгоор ангилахгүй; мэргэжлийн геологичийн хяналт, geological confidence, continuity, QA/QC, economic constraints, signed review шаардлагатай. UNCLASSIFIED хэвээр.

SRS-ийн 18 сарын roadmap нь төслийн төлөвлөлтийн эх; дээрх үлдэгдлийг энэ нэмэлтээр дууссан гэж тэмдэглээгүй.

## Verification

`tests/test_engineering_v2.py`: UTM 1mm, Morton bit limits, near-parallel curvature,
core orientation analytic cases, mass weighting/gaps, covariance-derived KE/SoR,
Parquet null/CRS/ID/metadata/compression/filter/atomic preservation, all 10 validation rules,
nested overlap, tags, DTM outlier, exposed VTK original cell IDs, six-table/v1-v2-v3 roundtrip/upward holes.
`tests/test_srs_ui.py`: native menu/readonly chart wiring. Windows smoke tests execute the new dependencies in source/frozen/installed EXEs.
