# Архитектурын шинэчлэл: хэрэгжүүлсэн хүрээ

Дараагийн нэмэлтээр Pseudoflow, муруй fault DAG, Rust OK холбогдсон: [шинэ native заавар](NATIVE_ENGINES.mn.md). Доорх нь эхний RF/MILP өөрчлөлтийн үеийн хүрээ.

2026-10-22. Хэрэглэгчийн өгсөн v1–v2 зааврын дагуу эхний нэмэлтүүд.

## Энэ өөрчлөлт

- Цэс, параметрийн цонх нээхэд global WaitCursor тавихаа больсон. Унших үйлдэлд төслийг бүхлээр deepcopy/compare хийхгүй. Давхар guard нэг Undo бүртгэнэ; алдаатай солилтыг буцаана.
- Блокийн үнэлгээ, cross-validation, variogram, implicit гадарга, pit, MILP schedule, SQL snapshot-ийг worker руу шилжүүлсэн. Дэмжсэн тооцоонд явц ба цуцлалттай. Native solver/ODBC дуудлага шууд тасрахгүй байж болно; цуцалсан үр дүнг төсөлд хэрэглэхгүй.
- Тайланг QAbstractTableModel-оор шаардлагатай нүдээр уншина. Харагдах текст хязгаартай, CSV эх утгыг хадгална.
- GPU preview NumPy→VTK шилжүүлгийг deep=False болгож backing массивын lifetime-ийг dataset дээр хадгалсан. Float32/RTC хөрвүүлэлт өөрөө шаардлагатай санах ой хэрэглэнэ.
- Мэргэжлийн хэрэгсэл → Төлөвлөлт → Pit RF хувилбар / үе шат. RF 0.30–1.20, алхам 0.05 default; өөрчилж болно. Background тооцоо, явц, цуцлалт, scenario тус бүрийн mesh ба хүснэгт, CSV экспорт, Undo дэмжинэ.
- RF тайлан тухайн RF-ийн болон суурь үнээрх net value, тонн, processed тонн, нэмэгдсэн/хасагдсан индекс, өмнөх shell дотроо багтсан эсэхийг хадгална. Тэнцүү optimum үед shell-ийн багтаалт зөрвөл нууж union хийхгүй.

## Тооцооны хязгаар

Pit RF нь одоогийн exact HiGHS MILP maximum closure-ийг давтана: 5000 хүртэл бүтэн world-axis regular блок, 50 хүртэл RF, бүрэн агуулга шаарддаг. Нэг solve 30 секундийн хязгаарт optimum батлагдаагүй бол үр дүн хэрэглэхгүй. Conservative square slope stencil, model extent гаднах stripping, discounting, зам, scheduling орохгүй. Энэ нь pseudoflow, инженерээр батлагдсан pushback эсвэл MSO биш.

## Дараагийн хөгжүүлэлт ба хүлээн авах нөхцөл

| Чиглэл | Одоогийн суурь | Дараагийн шаардлагатай ажил |
|---|---|---|
| Том өгөгдөл | SQLite .rmdb 10 сая хүртэл regular grid; Parquet streaming; sampled glyph preview | DuckDB/Zarr migration-ийн transaction/recovery/backward-compatibility; бодит өгөгдөлтэй 50 сая блокийн RAM/хугацааны benchmark |
| Дүрслэл | Native GPU instancing, RTC, pinned NumPy arrays | Regular volume LOD/reslice, VRAM budget, тодорхой GPU дээр FPS/latency хэмжих |
| Үнэлгээ | NumPy/SciPy, worker, cancel | Rust kernel reference parity, numerical tolerances, Windows packaging; dynamic anisotropy domain/reference шалгалт |
| Геологи | Contact/trend RBF, bounded planar fault/stratigraphy | Curved fault DAG, explicit throw, chronology, vein HW/FW; topology ба геологийн reference шалгалт |
| Ангилал | Үнэлгээний diagnostics | Геологичийн тохируулдаг matrix, conservative smoothing, provenance; эрх бүхий мэргэжилтний хяналт |
| Солилцоо | OMF beta export, GeoPackage, CSV/CAD | OMF round-trip fixtures; proprietary формат зөвшөөрөгдсөн specification/SDK ба reference файлууд |
| Local AI | Програмын offline туслах | Зөвшөөрсөн command registry, typed arguments, unit/element validation, write preview/Undo, дурын код ажиллуулахгүй |
| Release | Signing script, readiness gate | Эзэмшигчийн сертификат/лицензийн түлхүүр, төхөөрөмжийн туршилт, хараат бус ордын баталгаажуулалт |

Parquet compression нь memory-mapped zero-copy query гэсэн үг биш. 100 сая блок 60 FPS, 0 ms slice, 50–100 дахин хурд, 100% watertight, signing хиймэгц SmartScreen арилна гэсэн баталгаа өгөхгүй. Үр дүнг төхөөрөмж, өгөгдөл, тохиргоо, benchmark тайлантай хамт үнэлнэ. Ангиллын matrix нь JORC/NI 43-101 баталгаажуулалтыг орлохгүй.
