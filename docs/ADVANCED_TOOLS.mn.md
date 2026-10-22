# Геостатистик, өдөр тутмын хэрэгсэл, хэвлэлт ба локал копилот

2026-10-22 · Native PySide6 / VTK · хөгжүүлэлтийн хувилбар.

## Шинэ дөрвөн tab

| Tab | Бодит команд |
|---|---|
| Геостатистик / Geostatistics | Top-cut histogram, decile ба lognormal probability; high-grade restriction; cell declustering; local orientation; ангиллын санал |
| Өдөр тутмын ажил / Daily operations | Хэмжилтийн цооногийн Rectangular/Staggered тор; хүдэр/хоосон/NULL хил; TIN cut/fill; Schmidt/Wulff проекц |
| Хэвлэлт / Plotting | Вектор PDF + SVG план/зүсэлт; өмнөх ЭБМЗ draft pack; контакт чиглүүлэгчийн section editor |
| Автоматжуулалт / Automation | Зөвхөн унших блокийн копилот; QA/QC зөвлөх; аргачлалын ноорог; хязгаартай JSON workflow recorder/replay |

MN/EN солиход шинэ tab, бүлэг, товчны нэр орчуулагдана. Зарим техникийн параметр ба шалгалтын алдаа English хэвээр. Ctrl+K ба Ctrl+Shift+P-ээр шинэ товчнуудыг мөн олно.

## Геостатистикийн дараалал

1. Collar/Survey/Assay импорт, нэгж, QA/QC, NULL болон сонгосон элементийг шалгана.
2. **Top-cut шинжилгээ**: композитын урт, судлах cap-аа сонгоно. Support-weighted histogram/mean, equal-count decile contribution, эерэг утгын lognormal probability plot гарна. Тэг утгыг log plot-оос тусад нь тоолно. Cap-ыг автоматаар зөв гэж сонгохгүй. Үнэлгээнд хэрэглэх global top-cut-ыг estimator-ийн тохиргоонд тусад нь оруулна.
3. **Өндөр агуулгын зай**: threshold ба radius_m. Эхлээд global top-cut, дараа нь тухайн блокийн төвөөс радиусын гаднах дээжийг threshold хүртэл тайрна. Доторх дээж global cap-аас бусад утгаа хадгална. Support subpoint бүрд өөр cap хэрэглэхгүй; төвөөр сонгосон нийтлэг neighborhood ашиглана. Python болон Rust spherical point-support OK дэмжинэ.
4. **Cell declustering**: X/Y/Z cell size; анхдагч 8 half-cell shift. Эзлэгдсэн cell бүр ижил жинтэй, cell дотор support-ийн харьцаагаар жинлэнэ. Нийт жин 1. Жинг Kriging-д автоматаар оруулахгүй; cell-size sensitivity-г геологич шалгана. Polygonal declustering ороогүй.
5. **Хувьсах эллипсоид**: JSON `normal_controls` эсвэл ScalarField-ийн `field_gradient` жорыг сонгоно. Блок бүр дээр local strike/dip/normal frame-аар search ellipsoid ба тохируулсан anisotropic covariance ranges эргэнэ. Одоогоор Python backend; Rust сонговол тайлбартайгаар татгалзана. Normal controls нь nearest-control, smoothing/parallel transport биш. Zero gradient / хүрээнээс гаднах control-д алдаа өгнө. Mesh-ээс normal-ыг автоматаар олборлох импорт ороогүй.
6. **Ангиллын санал**: JSON priority rules. Variance, SoR, nearest sample distance, distinct hole count, estimation pass-ыг шалгана. Дутуу diagnostic-тай блок Unclassified. Үр дүн `classification_proposal`-д хадгалагдаж, `resource_class` хэвээр үлдэнэ. Одоогийн нэг үнэлгээний run нь pass=1; бүрэн 3-pass estimation scheduler нэмэгдээгүй. Nearest sample нь nearest collar-ийн зайтай ижил биш.

Жишээ JSON-ууд `examples/advanced/` дотор. Тэдгээрийн босго нь зохиомол жишээ, JORC/ЭБМЗ-ийн батлагдсан шалгуур биш. Measured/Indicated/Inferred-ийг A/B/C1/C2-той автоматаар адилтгахгүй.

## Өдөр тутмын хэрэгсэл

- **Өрөмдлөгийн тор**: төслийн closed polygon сонгоод spacing, row spacing, top/bottom Z, azimuth оруулна. Хэмжилтийн/сорьцын координат, геометрийн гүнтэй хүснэгт гарна. Тэсрэх бодис, цэнэг, тэсэлгээний паспортын тооцоо хийгдээгүй.
- **Хүдэр / хоосон хил**: axis-aligned блокийн тодорхой elevation дээр cutoff-оор хүдэр, хоосон, NULL гурвыг тусад нь нэгтгэнэ. Доторх нүх хадгалагдана. Projected metre CRS шаардсан DXF, PolygonZ Shapefile, PRJ/CPG, metadata гарна. Эргэлттэй блок, LandXML, олборлолтын GPS-ийн үйлдвэрлэгчийн сертификат ороогүй. Өгөгдлийн давхцал, block-boundary ойролцооллыг инженер хянана.
- **TIN Cut / Fill**: өмнөх ба дараах хоёр triangulated surface сонгоно. XY common coverage дээр triangle overlay хийж хэсэгчилсэн шугаман өндрийн зөрүүг яг интегралчилна. Cut/Fill тусдаа; density оруулсан үед л тонн. Хамрахгүй хэсэгт эзлэхүүн зохиохгүй. Vertical/overlapping/non-terrain triangles-ыг хүлээж авахгүй. Нэг surface тус бүр 50,000 triangle хүртэл; Windows performance guarantee биш.
- **Wulff / Schmidt**: `dip_direction,dip` CSV шаардана. Alpha/Beta-г orientation context-гүй таахгүй. Lower hemisphere poles, angular rings; planar, wedge, flexural-toppling геометрийн урьдчилсан screening. Бүрэн great-circle net, FoS, persistence, water pressure, direct-toppling solver, ханын тогтвортой байдлын баталгаа биш.

## Вектор план / зүсэлт

**Хэвлэлт → План / зүсэлт PDF**: XZ/YZ/XY, plane position, drillhole slab width, A3/A1/A0 landscape, auto эсвэл denominator scale сонгоно. Шинэ хавтаст `map.pdf`, `map.svg`, `layout.json` атомикаар үүснэ.

- Блокийн эргэлттэй хайрцгийн plane intersection бодит polygon, координатын тор ба масштабын шугамтай.
- Цооногийн minimum-curvature trace нь тодорхой slab-д тайрагдана; lithology interval-ыг schematic chord/hatching-аар, assay midpoint-ыг bar/value-аар харуулна. Нэг plane дээр ойр цооногуудыг проекцолсон болохыг slab setting-ээр тайлбарлана.
- Хүдрийн triangle mesh-ийн contour, сонголтоор блокийн агуулга ба **бүтэн блокийн** тонн бичнэ. Тонн нь огтлолын 2D талбайн нөөц биш. Давхацсан эсвэл хүрээнээс гарсан annotation-ыг priority-гаар хасаж уншигдах байдлыг хадгална.
- CRS, legend, title block, author/reviewer; XY дээр north arrow. Штамп нь RAINYMINE-ийн **хянах загвар**, ЭБМЗ-өөс баталсан үндэсний маягт гэсэн статусгүй.
- 100% хэмжээгээр хэвлэж масштаб хадгална. Дурын azimuth section, interactive print-layout editor, нарийн lithology legend одоогоор ороогүй. Mesh plane-тай бүхэлдээ давхацсан face-ийн контурыг автоматаар баталгаажуулахгүй.

## Контакт чиглүүлэгч

Блок model-ийн extent-тэй XZ section дээр contact цэгүүдийг хулганаар нэмнэ. Геологич normal X/Y/Z ба signed offset-ийг ил тод сонгоно; цэг бүрийн 0 болон ±offset constraint үүснэ. **Хадгалаад RBF Update** бодит linear-RBF surface-ийг background-д шинэчилнэ. Давхардсан зөрчилтэй constraint татгалзана. Шугамыг хадгалж болох ч автомат 3D geological interpretation биш; гарсан геометрийг мэргэжилтэн хянана.

## Локал копилот

Баруун туслах дээр **Төслийн өгөгдөл — зөвхөн унших** горим сонгоно. Жишээ: `агуулга > 0.5 Z > 1200` эсвэл өгөгдөлд байгаа exact domain нэр. Desktop block model эсвэл яг нэг attached `.rmdb` store шаардана. Au/Cu гэх элементийг ашиглахад импортын идэвхтэй channel батлагдсан байх ёстой; байхгүй бол `grade/агуулга` хэрэглэнэ.

Энгийн хүсэлтийг deterministic parser тайлна. Бусад хүсэлтэд суулгасан local engine/model байвал JSON tool plan санал болгоно. Ганц allowlisted `filter_blocks` tool; grade/x/y/z/density/domain, AND нөхцөл, numeric comparisons ба domain equality. AI-ийн бичсэн SQL/Python ажиллуулахгүй. SQLite нь mode=ro, query_only, bound parameters. Domain/нөхцөл болон үр дүнгийн query-г хэрэглэгчид харуулна.

Бүх таарсан блокийн statistics, тусдаа хязгаартай хүснэгт ба 3D preview гарна. Анхдагч preview 50,000, дээд 250,000; statistics нь бүх match дээр. Үндсэн блок загвар/агуулгыг өөрчлөхгүй. Байхгүй grade/density-г зохиохгүй. Энэ нь бүрэн autonomous geology agent биш; LLM plan-ыг хянан хэрэглэнэ.

QA/QC CSV-ээс lab/batch, CRM expected/SD, duplicate pair бодит утгыг хадгалж threshold давсан мөрийг зөвлөнө. CRM-д Shewhart Z, duplicate-д mean–absolute-difference diagnostic. Бүрэн calibrated Thompson–Howarth загвар биш. Methodology draft нь бүртгэлтэй параметр, статистик дээр тулгуурласан хянах ноорог; geological justification болон CP-ийн дүгнэлтийг зохиохгүй.

## Workflow recorder / Re-run All

**Бичлэг эхлэх** → дэмжсэн командуудыг ажиллуулах → **Бичлэг хадгалах**. Top-cut/declustering, estimate, classification proposal, contact RBF параметрүүдийг JSON-д хадгална. Replay allowlist: validate, composite, estimate, cap_analysis, decluster, classification_proposal, contact_rbf, report. Python/shell болон дурын function нэр хүлээж авахгүй. Import болон бүх UI үйлдлийг автоматаар бичдэг ерөнхий macro recorder хараахан биш.

Re-run нь deep-copy candidate дээр явж, амжилттай дууссаны дараа нэг удаа commit/Undo хийнэ. Алдаа/цуцлалт эх төслийг өөрчлөхгүй. Report нь зөвхөн сүүлийн алхам; output хавтсыг recipe дотроос биш хэрэглэгч тусад нь сонгоно. Урт task background-д ажиллана.

## Build ба хамгаалалт

`scripts/build_windows.ps1` нь Shapely/GEOS-ыг багцална. `scripts/build_nuitka.ps1` нэмэлт optional standalone compilation recipe; Nuitka-г тусад нь суулгаж, Windows дээр smoke-test хийх шаардлагатай. Үндсэн PyInstaller release pipeline хэвээр. Native compilation нь reverse engineering / лицензийн bypass-ийг боломжгүй болгохгүй; бүх Python бизнес логикийг Rust руу шилжүүлээгүй. Startup 2–3 дахин хурдан болсон гэсэн хэмжилт байхгүй.

## Шалгалт

Linux Python 3.12 / Qt 6.8.3: 321 тест амжилттай (native Rust/C++ extension ачаалсан). Шинэ analytic тестүүдэд Python/Rust high-grade restriction parity, dynamic-neighborhood selection, declustering weight, classification guard, crossing-TIN exact volume, hole-preserving CAD/GIS, read-only disk/desktop aggregate parity, workflow failure isolation, A3/A1/A0 PDF/SVG багтсан. Энэ нь бодит ордын хараат бус validation, Windows installer smoke test эсвэл үйлдвэрлэлийн сертификатыг орлохгүй.
