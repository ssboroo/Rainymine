# Мэргэжлийн ажлын урсгалын өргөтгөл

[OMF / GeoPackage / CSV–CAD metadata солилцоо](OPEN_EXCHANGE.mn.md) — шинэ экспорт/импортын дэмжлэг, хувилбар, хязгаар.

Энэ нэмэлт нь Micromine-ийн бүх модулийн баталгаажсан орлуулалт биш. Доорх хэрэгслүүд бодит тооцоололтой; үйлдвэрлэлийн хүлээн авах шалгалтыг тусад нь гүйцэтгэнэ.

«Мэргэжлийн хэрэгсэл» цэс болон Ctrl+K хайлтаас шинэ үйлдлүүдийг нээнэ.

| Чиглэл | Нэмэгдсэн боломж | Хязгаар |
|---|---|---|
| CAD | Manifold3D union/intersection/difference, conservative mesh repair, transform, интерактив box gizmo | Хаалттай manifold оролт; өөрөө огтлолцсон биетийг бүрэн засахгүй. Gizmo Apply нь хуулбар үүсгэнэ. |
| Snapping | Орой/шугамд ойр цэгийг координатаар хайх | Интерактив зурах бүх үйлдлийн snapping биш; mesh/интервалын иж бүрэн CAD сонголт биш. |
| Surpac | ASCII STR импорт/экспорт; STR-тэй хосолсон ASCII TRISOLATION DTM импорт | Binary, баталгаажаагүй checksum-тай DTM дэмжихгүй. |
| GIS | SHP point/polyline/polygon Z ба DBF/PRJ импорт; GeoTIFF DEM | PRJ UTF-8/Windows-1252; DBF UTF-8. SHP экспортгүй; polygon hole-ийг solid гэж тайлбарлахгүй. DEM нь метрийн projected CRS, band 1, хязгаартай sampled гадарга. |
| LiDAR | LAS/LAZ chunk уншилт, ROI/class filter, raw dimension хадгалсан atomic экспорт | 250k default sampled preview; waveform packet export дэмжихгүй. Бүх эх цэгийг GPU-д ачаалахгүй. |
| DWG / Datamine | Гадна суулгасан ODA-аар DWG→DXF | ODA багцад ороогүй, бодит DWG fixture баталгаажаагүй. Native Datamine SDK/уншигч **байхгүй**. |
| Implicit | Signed contact RBF; литологийн интервалын төвийн binary constraints; anisotropy, kernel, planar fault zone | Fault zone тус бүр салангид; boundary grid gap боломжтой. Fault throw, стратиграфийн бүрэн solver, watertight ore solid биш. |
| Үнэлгээ | Indicator kriging, unresolved block multipass, spherical/exponential/Gaussian fit | IK нь магадлал, металлын grade биш. Multipass centre support; бодит ордын хараат бус benchmark хүлээгдэнэ. |
| Уурхай | Налуу/өргөнтэй spiral ramp surface+centreline, нийлүүлсэн tunnel network solid, ring fan | Бүрэн pit wall/ramp collision, pushback, геотехник, тэсрэх бодисын инженерчлэл ороогүй. |
| Stope | Regular axis-aligned box candidate non-overlap HiGHS MILP | ≤5000 блок/3000 candidate; commercial MSO, dilution, wall-angle optimization биш. |
| Хуваарь | Mining/process capacity, blend grade, precedence, discounted value нэг MILP | Same-period feed; stockpile/reclaim, үйлдвэрийн нэгдсэн ажиллагаа ороогүй. |
| Том модель | Arrow scan, cutoff/ROI, original source ID, VTK instanced sampled preview | Project-ийн 32MB/50000 блок/5000 collar хязгаарыг өсгөөгүй. External viewer нь sampled; full resident model editing биш. |

Мэдэгдсэн CRS нь project-той таарах ёстой. CRS байхгүй үед хэрэглэгч батална; өөр CRS-ийн координатыг чимээгүй дахин шошголохгүй. Хэрэгслүүдийн шинэ хүнд ажлууд worker thread-д ажиллаж, UI thread-д үр дүнг оруулна. Cancel болон project солигдох үед үр дүнг хаяна; native CSG/MILP дуудагдсан дундаа заавал шууд тасрахгүй. Өмнөх бүх хэрэгслийг асинхрон болгоогүй.

## Хэмжсэн гүйцэтгэл

Synthetic fixture, Linux/Python 3.12, бичсэний дараах warm уншилт. CPU scan болон sampled VTK buffer бэлтгэл хэмжсэн; **physical GPU FPS хэмжээгүй**.

| Эх хэмжээ | Parquet scan | Cutoff дараах / preview | LAS scan / preview | Бүх процессын peak RSS |
|---|---:|---:|---:|---:|
| 1 сая | 0.034 s | 705880 / 70588 | 0.048 s / 100000 | 393.50 MiB |
| 10 сая | 0.151 s | 7058820 / 176470 | 0.420 s / 250000 | 732.56 MiB |

Нотолгоо: [1M JSON](benchmarks/streaming-1m.json), [10M JSON](benchmarks/streaming-10m.json). Synthetic fixture Morton code-той боловч globally sorted биш. Cold-cache, бодит уурхайн 10 сая resident блок, 50 сая LiDAR, 60 FPS баталгаа биш.

Дахин хэмжих: `python scripts/benchmark_streaming.py --help` доторх CLI-г ашиглана. Нөөцийн ангилал автоматаар баталгаажихгүй; мэргэжлийн геологич/инженерийн хяналт, бодит аноним өгөгдлийн acceptance, Windows hardware benchmark шаардлагатай хэвээр.

## Хамаарал ба эх формат

Pinned manifold3d 3.1.1, laspy 2.6.1, lazrs 0.7.0, rasterio 1.4.3, pyshp 2.3.1. Лицензүүд `assets/engineering_licenses` дотор багцлагдана.

- [Manifold](https://manifoldcad.org/docs/html/)
- [laspy](https://laspy.readthedocs.io/en/latest/basic.html)
- [Rasterio](https://rasterio.readthedocs.io/en/stable/quickstart.html)
- [PyShp](https://github.com/GeospatialPython/pyshp)
- [Surpac ASCII specification](https://www.cse.unr.edu/~fredh/papers/working/vr-mining/string.html)
- [ODA adapter](https://ezdxf.readthedocs.io/en/stable/addons/odafc.html)
