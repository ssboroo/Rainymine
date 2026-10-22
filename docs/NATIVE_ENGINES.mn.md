# Pseudoflow, муруй хагарлын сүлжээ, Rust kriging

Эдгээр нь native Windows ажлын орчинд холбогдсон туршилтын инженерийн боломжууд. Хараат бус ордын баталгаажуулалт, CP/QP дүгнэлтийг орлохгүй.

## Ашиглах

1. **Дискэн том pit:** Мэргэжлийн хэрэгсэл → Дискэн блок сан → Дискэн Pseudoflow pit. `.rmdb` сонгоод бүх блокийн сонголтыг хадгалах `.csv`, эдийн засгийн параметр, налуу, RAM төсөв, value scale өгнө. NULL агуулгыг хаягдал гэж таахгүй; бүх агуулга шаардана. Нягт байхгүй блокт хэрэглэгчийн density fallback хэрэглэнэ. CSV нь бүх block ID, selected, net value, тонн, processed баганатай. Тайланд input/output SHA256, CRS, grade unit, solver revision, rounding bound хадгална. Эх санг өөрчлөхгүй.
2. **RF ба mesh:** Мэргэжлийн хэрэгсэл → Төлөвлөлт → Pit RF хувилбар / үе шат → Backend `pseudoflow`. Legacy `.rmine` модель 50,000 хүртэл блок; 3D mesh ба RF хүснэгт/график үүсгэнэ. `milp` сонголт 5,000 хэвээр.
3. **Муруй fault:** Мэргэжлийн хэрэгсэл → Геологи / Үнэлгээ → Муруй хагарлын сүлжээ JSON. `examples/acceptance/curved-fault-network.json` жишээ ашиглаж болно. Bounds нь таны төслийн координатаар байна. Импорт хагарлын guide mesh-үүдийг сольж, өмнөх block grade-ийг хүчингүй болгоно. Дахин үнэлнэ; өмнөх implicit гадаргууг stale гэж тэмдэглэнэ.
4. **Rust үнэлгээ:** Блок үнэлгээний параметрт Backend=`Rust`, Арга=`kriging`, Variogram=`spherical`, Block support=`Point` сонгоно. Search ellipsoid, per-hole limits, minimum holes, top cut, fault barrier, covariance anisotropy дэмжинэ. Python сонголт нь бусад аргыг хэвээр ажиллуулна. Rust тохироогүй арга/support-ийг чимээгүй солихгүй, алдаагаар тайлбарлана.
5. **Explicit slip:** Fault treatment=`Explicit slip restoration` нь JSON-ийн `slip` XYZ векторыг + талын цэгээс хасаж, сэргээсэн координатад үнэлнэ. Нэг талын barrier хэвээр. Энэ хувилбар point support дэмжинэ. Slip-ийг гадаргуунаас автоматаар таахгүй.

## Алгоритм ба тоон хяналт

**Pseudoflow:** MineFlow C++ хөдөлгүүрийг Rust PyO3 модульд холбосон. MIT лиценз, upstream `6f5dd7091070b1bd85457b3ce9fd95c4e345c983`; өөрчлөлтгүй эх файлууд `native/rainymine_core/vendor/mineflow`-д бий. Регуляр grid-ийн conservative square next-level slope stencil-ийг implicit байдлаар үүсгэнэ: Python-д бүх precedence arc хадгалахгүй. Generic explicit graph интерфейс мөн бий. Integer int64 утгад бодно; `value × scale`-ийг nearest integer болгоно. Үнэлгээний rounding, нийт абсолют rounding error, `N / scale` conservative objective-loss bound тайланд гарна. Overflow-ийг эхэнд шалгана. Үр дүнгийн precedence-ийг бие даан шалгана. Model extent-ээс гаднах stripping, haul road, discounting, scheduling орохгүй.

Дискэн сангийн дээд хэмжээ 10 сая regular блок хэвээр. Solver-ийн node/excess төлөв RAM-д байрлана; бүрэн out-of-core solver биш. RAM admission estimate 1024 byte/block, default төсөв 2048 MiB; бодит allocator peak-ийн баталгаа биш. Хэт том ажлыг эхлэхээс өмнө төсөвт тулгаж буцаана. 50 сая блокийн туршилт хийгдээгүй.

**Муруй fault network:** Хавтгай болон signed RBF (`linear`, `cubic`, `thin_plate_spline`) гадаргуу холимог байж болно. 8 хүртэл fault, тус бүр 4–10,000 finite, координат давхцаагүй signed control; эерэг/сөрөг тал шаардана. `active_if: {"parent name": 0 эсвэл 1}` нь DAG-ийн parent-ийн аль талд үргэлжлэхийг заана. Нэр давхцах, parent алга болох, cycle-ийг хориглоно. Идэвхгүй хэсгийг negative талтай нэг zone болгож нийлүүлэхгүй. Sample/target-ийг zone-оор тусгаарлана; contact RBF нь fault зааг давсан grid cell-ийг үлдээхгүй. Guide гадаргуу нь resolution-оор sample хийж, triangle centroid-оор scope шүүнэ; яг огтлолцсон solid биш. Boundary гаднах extrapolation, interpretation-ийн зөв байдлыг геологич хянана.

`active_if` нь геометрийн scope DAG; автоматаар тогтоосон геологийн нас биш. Scope parent-first дарааллаар explicit slip сэргээнэ; хоорондоо хамааралгүй fault-ийн JSON дараалал нь сэргээх дараалал. Үүнийг ордын түүхтэй тулгаж хэрэглэгч тодорхойлно. Хагарлын муруй, offset, intrusion/erosion chronology-г хооронд нь адил гэж үзэхгүй.

**Rust OK:** NumPy оролтыг owned массивт хуулж GIL-ийг суллаад Rayon-оор цэг бүрийн spherical ordinary kriging матриц, SVD condition check, LU solution, variance/KE/SoR бодно. Python/SciPy neighborhood policy болон KD-tree ашиглана; бүх хайлт Rust руу шилжээгүй. Багц хэмжээг боломжит candidate тоонд тааруулна. Python reference-тэй 1e-9 tolerance-аар харьцуулна. Singular болон invalid variance нь NULL/status болж гарна; чимээгүй ridge нэмэхгүй. SK/IK, бусад variogram, quadrature block support, dynamic anisotropy Rust backend-д хараахан ороогүй.

Native solve GIL-ийг суллана. Cancel дарахад дэмжсэн багц/экспорт зогсоно; нэг MineFlow solve-ийн дотор хүчээр таслахгүй, буцаж ирсэн үр дүнг хэрэглэхгүй. Ажиллаж буй native worker дуусахаас өмнө цонх устгахгүй.

## Бодит хэмжилт ба шалгалт

Linux, Python 3.12, 9 logical CPU, synthetic нэг сая блок: pseudoflow implicit-grid 5.461 секунд, процессын оргил RSS 354.684 MiB. 200 сорьц / 1000 point target / 16 хөрш бүхий бүтэн kriging урсгал: Python 0.992 секунд, Rust 0.820 секунд; grade/variance/KE/SoR хамгийн их абсолют зөрүү 5.329e-15. Нэг удаагийн хэмжилт; төхөөрөмж, ачаалал, support-оос хамаарна. `docs/benchmarks/native-1m-linux.json`-д хадгалсан. GPU FPS болон хараат бус ордын хэмжилт биш.

Тест: 25 exhaustive жижиг DAG, implicit/explicit stencil parity, rounding/overflow, point exactness/singular matrix, covariance anisotropy, hole/fault policy, restoration, DAG cycle/scope, муруй contact signed controls, SQLite pit ба atomic cancel. Windows CI native модулийг заавал хөрвүүлж, reference benchmark болон багцалсан/суусан EXE дотор closure ба kriging ажиллуулна.

## Хөгжүүлэгчийн build

Rust 1.85.1 ба C++17 compiler шаардлагатай. `python -m pip install maturin==1.7.8`, дараа `python scripts/build_native.py`. `Cargo.lock`-ийг өөрчлөхгүйгээр `--locked` build хийнэ. Windows build script энэ алхмыг ажиллуулж, `rainymine_core.pyd`-ийг EXE-д оруулна. Түгээлтэд MineFlow LICENSE болон Cargo dependency license texts-ийг `NATIVE-NOTICES.txt` болгон багцална.

Эх сурвалж: https://github.com/MineFlowCSM/MineFlow · Deutsch, Dağdelen, Johnson (2022), https://doi.org/10.1007/s11053-022-10035-w
