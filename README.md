# RAINYMINE 2026 · 1.0.0-rc.1

**v1.0 release candidate:** [Шинэ боломж, турших дараалал ба үлдсэн release шалгуур](docs/V1_0.mn.md). Эцсийн үйлдвэрлэлийн баталгаа биш.

**Монгол / English хэлтэй, Windows x64 дээр интернэтгүй ажиллах геологи, 3D загварчлал ба уурхайн тооцооны программ.** PySide6 + VTK native desktop. RAINY STUDIO · Лиценз, дэмжлэг: **90220101**.

Хөгжүүлэлтийн / туршилтын хувилбар. Micromine-ийн бүрэн орлуулалт, баталгаажсан нөөцийн тайлан эсвэл батлагдсан уурхайн төлөвлөгөө гэсэн баталгаа өгөхгүй. Боломж бүрийн бодит хүрээг доорх зааварт тэмдэглэв.

## Татах, суулгах

[Windows build](https://github.com/ssboroo/Rainymine/actions/workflows/windows.yml)-ийн хамгийн сүүлийн **амжилттай** ажиллуулалтын artifacts, эсвэл [Releases](https://github.com/ssboroo/Rainymine/releases)-д бодитоор нийтлэгдсэн assets-ийг сонгоно. Ижил `1.0.0-rc.1` нэртэй багцууд өөр commit агуулж болох тул build-ийн огноо, commit болон manifest-ийг шалгана.

| Багц | Зориулалт |
|---|---|
| `Rainymine-1.0.0-rc.1-Setup-x64.exe` | Ердийн Windows суулгагч |
| `Rainymine-1.0.0-rc.1-Windows-x64.zip` | Бүхлээр нь задалж ажиллуулах portable |
| `Rainymine-1.0.0-rc.1-AI-Offline-x64.zip` | AI модель хамт багтсан offline portable |
| `Rainymine-1.0.0-rc.1-Release-Kit.zip` | Заавар, шаардлага, түгээлтийн бүртгэл |

EXE-д Python, Ollama, API key тусад нь хэрэггүй. Үндсэн тооцоо интернэтгүй ажиллана. Ердийн багцын AI анхны таталт, эх кодын dependency таталт интернэт шаарддаг; SQL холболтод байгууллагын сервер хэрэгтэй. SHA256 нь файлын бүрэн бүтэн байдлыг шалгана; Windows суулгагч одоогоор тоон гарын үсэггүй.

[Суулгах заавар](release/QUICK_START.mn.md) · [Орчны шаардлага](release/SYSTEM_REQUIREMENTS.mn.md) · [Лиценз](release/LICENSING.mn.md)

## Эхний ажлын дараалал

1. Нээгдэх **ЖИШЭЭ** төслөөр камер, давхарга, огтлолыг туршина. Энэ нь зохиомол өгөгдөл.
2. **Ctrl+N** → төслийн тохиргоонд CRS, метр, агуулгын нэгжээ шалгана.
3. Ердийн өгөгдөлд амсар → замнал → сорьц / литологи импортлоно. `dh_*.csv` багцад **Мэргэжлийн хэрэгсэл → DH өгөгдөл → DH CSV багц импорт…** ашиглана.
4. Импортын тайлан, өгөгдлийн шалгалт, интервал ба QA/QC-г хянаж байж композит / үнэлгээ хийнэ.
5. **Ctrl+Shift+S** → шинэ `.rmine` файл; дараа нь **Ctrl+S**-ээр хадгална.

[Дэлгэрэнгүй ашиглах заавар](docs/USER_GUIDE.mn.md) · [Бүх shortcut ба хулганы удирдлага](docs/SHORTCUTS.mn.md) · [Бүх хэрэгсэл](docs/TOOLS.mn.md)

## Ажлын орчин ба shortcut

Зургаан ангиллын ribbon, зүүн давхаргын мод, төвийн 3D / огтлол / төлөвлөгөө, доод хүснэгт, баруун локал туслах ба блокийн шинж чанартай. 2026-10-22 шинэчлэлтээр бүтэн нэртэй хоёр мөрийн хэрэгсэл, хэвтээ гүйлгэх ribbon, уншигдах цайвар palette, Ө/Ү дэмжих 3D фонт, эвхэгддэг блокийн самбар нэмэгдсэн. Хэл солиход төслийн нэр, CSV талбар, хэрэглэгчийн утгыг орчуулахгүй; зарим техникийн алдааны текст English хэвээр.

| Shortcut | Үйлдэл |
|---|---|
| Ctrl+N / Ctrl+O | Шинэ төсөл / төсөл нээх |
| Ctrl+S / Ctrl+Shift+S | Хадгалах / өөрөөр хадгалах |
| Ctrl+Z / Ctrl+Y | Буцаах / сэргээх |
| Ctrl+K | Үйлдэл хайх |
| Ctrl+Shift+P | Бүх хэрэгслийн сан |
| Ctrl+F1 | Ribbon хураах / дэлгэх |
| F10 | 3D төвлөрсөн горим / самбаруудыг сэргээх |
| PageUp / PageDown | Өмнөх / дараах огтлол |

3D дээр зүүн товчийг чирж эргүүлнэ, Shift+зүүн товчоор зөөнө, дугуйгаар томруулна. Сонгох ба хэмжих горимын ялгааг [shortcut заавраас](docs/SHORTCUTS.mn.md) үзнэ.

## Боломж ба дэмжлэгийн хүрээ

| Чиглэл | Одоогийн боломж | Дэлгэрэнгүй |
|---|---|---|
| Өрөмдлөг | CSV mapping, XLSX, Collar/Survey/Assay/Lithology/Structure/Geotech, minimum curvature, QA/QC | [Ашиглах заавар](docs/USER_GUIDE.mn.md) |
| DH CSV | Long/pivot элемент сонголт, NULL/qualifier, geology join, эх файлын архив, 200 мөрийн хуудаслалт | [DH импорт](docs/DH_IMPORT.mn.md) |
| 3D / CAD | RTC координат, огтлол, хоёр viewport, picking, string/polygon, TIN, solid CSG, transform gizmo | [Мэргэжлийн урсгал](docs/PROFESSIONAL_WORKFLOWS.mn.md) |
| Геологийн загвар | Агуулгын RBF, литологийн binary RBF, signed contacts, хавтгай хагарлын тусгаарлалт | Бүрэн stratigraphy / fault restoration биш |
| Нөөцийн тооцоо | NN/IDW/OK/SK, IK, вариограмм, cross-validation, KE/SoR, cutoff/swath | [Инженерийн тайлбар](docs/SRS_V2_ENGINEERING.mn.md) |
| Уурхай | Туршилтын pit maximum closure, spiral ramp, tunnel solid, ring геометр, хязгаартай stope ба blend MILP | Арилжааны MSO, бүрэн үйлдвэрлэлийн scheduling биш |
| Нээлттэй солилцоо | OMF 2.0-beta.1 экспорт, GeoPackage vector импорт/экспорт, CSV–CAD metadata ZIP | [Формат солилцоо](docs/OPEN_EXCHANGE.mn.md) |
| Бусад формат | DXF/OBJ/STL, Surpac ASCII STR/DTM, SHP, projected GeoTIFF DEM, LAS/LAZ preview/ROI | [Форматын нарийн хязгаар](docs/PROFESSIONAL_WORKFLOWS.mn.md) |
| SQL | Windows ODBC, байгууллагын canonical views, snapshot уншилт | [Geobank / SQL тохиргоо](GEOBANK_SQL.md) |

DWG хөрвүүлэлт нь тусдаа суулгасан ODA хэрэгслээс хамаарна. Datamine-ийн native формат дэмжигдээгүй. OMF импорт байхгүй; хүлээн авагч нь яг beta хувилбарын Freeform subblocks-ийг дэмжих ёстой. GeoPackage нь блок загварын бүтэн орлуулалт биш. CRS, нэгж, NULL, блокийн эргэлт ба хэмжээг форматын зааврын дагуу дамжуулна.

## Хадгалалт, хэмжээ ба баталгаажуулалт

- Үндсэн төсөл `.rmine` format v3; хуучин v1/v2 уншина. Форматын дээд хэмжээ 32 MB. DH эх файлууд шахсан архивтайгаа төсөлд багтана.
- Үндсэн scientific өгөгдөлд 5,000 амсар, 100,000 мөр, 50,000 блокийн хязгаар бий. DH эх архивын хязгаар тусдаа; [DH зааврыг](docs/DH_IMPORT.mn.md) мөрдөнө.
- Том Parquet/LAS харагдац нь хязгаартай preview/ROI ашиглана. 10 сая блок / 50 сая цэгийг бүрэн ачаалж 60 FPS ажиллана гэж баталгаажаагүй.
- Хадгалаагүй шинэ төсөл ч dirty үед хоёр минут тутам per-session recovery snapshot-тай. Өмнөх `.rmine.autosave` нь хадгалсан төсөлд нэмэлт нөөц. **Ctrl+S**-ийг тогтмол хэрэглэнэ.
- Үр дүн нь мэргэжлийн хяналт шаардана; JORC / NI 43-101 / ЭБМЗ ангиллыг автоматаар баталгаажуулахгүй.
- Windows CI нь build, тест, EXE/суулгалтын smoke шалгана. Бүх бодит Windows 10/11 төхөөрөмж, GPU болон уурхайн reference acceptance дуусаагүй.

[Мэдэгдэж буй хязгаар](release/KNOWN_ISSUES.mn.md) · [Гадаад баталгаажуулалт](docs/EXTERNAL_VALIDATION.md) · [Release checklist](release/RELEASE_CHECKLIST.mn.md)

## Эх кодоос ажиллуулах

Windows PowerShell, Python 3.11 x64:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

Шалгалт ба build:

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python main.py --smoke --screenshot smoke.png
.venv\Scripts\Activate.ps1
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Dependency-ийн тогтоосон хувилбарууд `requirements.txt`-д байна. AI source тохиргоо: `python scripts/prepare_local_ai.py --model`; анхны таталтад интернэт хэрэгтэй. Build-д AI runtime, шаардлагатай CPU renderer ба installer бэлтгэлийг мөн хийнэ; дээрх script нь portable build хэсэг. Build-ийн бүрэн алхмуудыг [Windows workflow](.github/workflows/windows.yml)-оос үзнэ.

## Баримт бичгийн сан

Шинэ: [Recovery, түгээлтийн preflight, workflow хяналт, reference тайлан, дискэн блок сан, инженерийн analytic модулиуд](docs/PRODUCTION_FOUNDATIONS.mn.md). `.rmdb` нь `.rmine`-д замаар холбогдох тусдаа файл; хамт нөөцөлж/зөөвөрлөнө. Нэг сая блокийн synthetic workflow хэмжилт баримтад бий; энэ нь ордын хараат бус баталгаа биш.

[Баримтын индекс](docs/README.md) · [Шинэчлэлтийн түүх](CHANGELOG.md) · [Түгээлтийн тэмдэглэл](release/RELEASE_NOTES.mn.md) · [Дэмжлэгийн маягт](release/SUPPORT_TEMPLATE.mn.md) · [Брэндбүүк](docs/BRANDBOOK.mn.md)

[Өмнөх дэлгэрэнгүй техникийн лавлагаа](DEVELOPMENT_REFERENCE.md) — түүхэн тайлбар; шинэ модулийн зааврыг давхар мөрдөнө.

Архитектурын шинэчлэл, RF хувилбар ба цэсний засвар: [хэрэгжүүлсэн хүрээ](docs/ROADMAP_IMPLEMENTATION.mn.md).

## Үйлдвэрлэлийн түвшний хөгжүүлэлт

[Acceptance ба эхний блок CSV импорт](docs/PRODUCTION_READINESS.mn.md): Micromine-оос CSV болгон гаргасан блокийг mapping, CRS/нэгжийн баталгаа, NULL ба geometry шалгалттай оруулна. Explicit origin/parent size/RAINYMINE ENU angles-аар эргэлттэй freeform sub-block дэмжинэ; vendor Euler metadata-г таахгүй. Гадаад reference-ийн geometry/NULL/grade comparator, joint-blend schedule-ийн тусдаа feasibility аудиттай. Density/domain-ийг тусад нь mapping хийж, бусад баганыг source text attributes хэлбэрээр хадгална. Native DAT reader дэмжихгүй.

Шинэ native модулиуд: [Pseudoflow, муруй fault DAG, Rust kriging — заавар ба хэмжилт](docs/NATIVE_ENGINES.mn.md).
# ЭБМЗ-д бэлтгэх хяналтын багц

Шинэ: [v2 инженерийн урсгал, CP reference багц, 10 сая блокийн хэмжилт](docs/V2-ENGINEERING-MN.md).

`Блок загвар → ЭБМЗ багц гаргах` буюу `ЭБМЗ тайлан` цэснээс ажиллана.
Эхний удаа ашигт малтмал, байгууллага, ТЗ, боловсруулсан/хянасан мэргэжилтэн,
заагийн агуулга, шаардлагатай бол орлуулах нягт, A3 масштаб, XZ/YZ зүсэлтийн
байрлал, гаралтын үндсэн хавтсыг тохируулна. Тохиргоо төсөлд хадгалагдана.
Дараагийн удаа нэг товчоор огноо, давтагдашгүй нэртэй шинэ багц үүсгэнэ.
Өмнөх багцыг дарж бичихгүй; тооцоо арын урсгалд ажиллаж цуцлагдана.

Багцад:

- Домэйн/эх ангиллын эзлэхүүн, тонн, жинлэсэн агуулга, агуулагдах металл, нийт дүнгийн CSV;
- Амсар, замнал, сорьц, литологийн эх бүртгэлийн CSV;
- Хяналтын жагсаалтын CSV, хэвлэх A4 тайлан PDF, HTML;
- Масштаб, координат, өнгөний тайлбар, зохиогчийн булантай хоёр хуудас A3 вектор PDF;
- Тохиргоо, эх блокийн SHA-256, гарсан файлуудын SHA-256 бүхий manifest орно.

Хувийн агуулгыг металл тоннд `/100`, g/t ба ppm-ийг `/1,000,000` хөрвүүлнэ.
Агуулгыг тонноор жинлэнэ. Заагаас дээш нягт дутсан домэйны тонн/агуулга/металлыг
хэсэгчилсэн дүнгээр орлуулахгүй, хоосон үлдээнэ. Орлуулах нягт хэрэглэсэн тоог тэмдэглэнэ.
Нөөцийн ангиллыг автоматаар тогтоохгүй. Бүх тайлан **хянах төсөл** гэсэн тэмдэглэгээтэй.

Одоогоор эргүүлээгүй, санах ой дахь 200,000 хүртэл блок, 1000 хүртэл домэйн/ангиллын
бүлэг дэмжинэ. A3 зүсэлт нь блокийн хавтгай огтлол; геологийн тайлбарласан зураг,
хагарал/цооног/гадаргын зураг болон дурын азимуттай layout хараахан биш.
CRS тодорхойгүйг ил тод тэмдэглэнэ. A3-г **100% / Actual size** хэвлэнэ;
Fit to page сонговол бичсэн масштаб хадгалагдахгүй.

Энэ нь ЭБМЗ-өөс баталсан нэг мөр албан маягт гэсэн баталгаа биш. Тухайн ашигт
малтмалын хүчинтэй заавар, байгууллагын хүлээн зөвшөөрсөн хүснэгт/зурагтай тулган
мэргэжилтэн хянана. Албан маягтын яг адил экспортод тэр маягтын эх загвар шаардлагатай.
Эх сурвалж: [ЭБМЗ-ийн дүрэм](https://legalinfo.mn/mn/detail?lawId=16230812497421),
[АМГТГ-ын хайгуулын тайлан хүлээн авах үйлчилгээ](https://mrpam.gov.mn/page/ashigt-maltmalyn-khaiguul),
[Аргачилсан зөвлөмж, Боть 1](https://mmhi.gov.mn/wp-content/uploads/2022/12/Аргачилсан-зөвлөмж-Боть-1.pdf).
