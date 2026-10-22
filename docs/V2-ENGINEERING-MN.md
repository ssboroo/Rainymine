# RAINYMINE: v2 инженерийн ажлын урсгалын суурь

Энэ өөрчлөлт нь Micromine/Leapfrog-той бүрэн дүйцсэн бүтээгдэхүүн, CP баталгаажуулалт,
эсвэл production release гэсэн зарлал биш. Шинэ функцүүдийн хамрах хүрээг доор тодорхойлов.

## 1. Том CSV → дискэн сан

`Мэргэжлийн баталгаажуулалт → Том CSV → дискэн блок сан…`.
World X/Y/Z төв, метрийн DX/DY/DZ, агуулгын багануудыг mapping хийж, шаардлагатай бол
нягт/домэйныг сонгоно. Төслийн projected metre CRS болон %, g/t, ppm нэгжийг эх файлтай
тулгана. 20 сая хүртэл мөрийг 32,768 мөрийн багцаар SQLite `.rmdb` рүү бичнэ.
Төслийн `.rmine` файлд блокийн жагсаалтыг нэмж материалжуулахгүй, сангийн холбоос хадгална.

Импорт нь эргүүлээгүй, өөр өөр хэмжээтэй leaf блок дэмжинэ. Энэ нь leaf хоорондын
давхцал, regular-grid topology, эцэг/хүүхдийн давхар тооллыг баталгаажуулсан гэсэн үг биш.
Тиймээс импортолсон санг regular-grid pseudoflow руу шууд дамжуулахгүй.
Нягт/агуулгын NULL хадгалагдана. Эх файлын SHA-256, mapping, CRS, нэгж бүртгэгдэнэ.
Алдаа/цуцлалтын үед түр санг устгаж, өмнөх файлыг дарахгүй.

2026-10-22-нд Linux дээр бодитоор хэмжсэн synthetic үр дүн:

| Мөр | Импорт | Нийт дүн | CSV экспорт | Процессын оргил RSS |
|---|---:|---:|---:|---:|
| 1,000,000 | 6.04 сек | 0.33 сек | 3.30 сек | 259.8 MiB |
| 10,000,000 | 65.04 сек | 3.12 сек | 29.67 сек | 260.1 MiB |

Дахин нээх, нэг блок засах/Undo/Redo, NULL тоо, аналитик тонн/металл болон CSV мөрийн
тоог шалгасан. 3D буферийн шалгалт зөвхөн 50,000 sampled блоктой; GPU FPS хэмжээгүй.
Энэ нь Windows төхөөрөмжийн хэмжилт, 10 сая блокийн kriging, эсвэл бодит ордын баталгаа биш.
Машин/үе шатуудын JSON: `docs/benchmarks/disk-import-{1m,10m}-linux.json`.

Давтах:

```bash
python scripts/benchmark_disk_import.py --rows 10000000 --output benchmark.json
```

## 2. GPU preview

Parquet preview-ийн API нь сонгосон RAM төсөвт багтах 10 сая хүртэл display block зөвшөөрнө;
үндсэн утга 250,000 хэвээр. Консерватив admission estimate нь display block тутамд 256 byte.
Энэ нь GPU VRAM-ийн баталгаа биш. Instancing ашигладаг; дүрслэлийн float32 RTC координат
нь хадгалсан шинжлэх ухааны float64 координатыг сольдоггүй. NULL саарал өнгөөр үлдэнэ.
Хэмжээ нь leaf бүрийн DX/DY/DZ; сонгох ID нь эх файлын мөрийн ID хэвээр.
Ray picking нь 65,536 блокийн багцаар ажиллаж түр RAM-ийг хязгаарлана; нийт хугацаа O(N).

Шахсан Parquet хуудсууд RAM-д decode хийнэ. `memory_map=True` гэсэн сонголт нь бүх
өгөгдлийг zero-copy болгохгүй. 0.1 сек нээлт, 60 FPS гэсэн тогтмол амлалт байхгүй.
`vtkImageData` regular-grid volume renderer болон бүх өгөгдлийн GPU benchmark цаашдын ажил.

## 3. CP / мэргэшсэн геологичийн хяналтын багц

`Мэргэжлийн баталгаажуулалт → CP харьцуулалтын багц…`.

1. Ашиглах эрхтэй бодит ордын Collar/Survey/Assay/Lithology-г төсөлд импортолж QA/QC хийнэ.
2. Reference программын хувилбар, composite/top-cut, variogram, search, discretization,
   NULL болон density дүрэм, block support, domain, rotation-ийн тохиргоог хадгална.
3. Тэр тохиргоогоор RAINYMINE модель бодуулна. Reference блок CSV нь
   `x,y,z,dx,dy,dz,grade` ба боломжтой бол `density,domain` баганатай байна.
4. Reference desurvey CSV нь `hole_id,depth,x,y,z`; бүх цооногийг хамруулах хэмжсэн гүнүүдтэй байна.
5. `examples/acceptance/cp-reference-metadata-template.json`-ыг өөрийн бодит мэдээлэл,
   эх файлуудын SHA-256, нэгж/CRS, explicit ENU grid angles болон normalized параметрээр бөглөнө.
6. Хүлээн авах tolerances, common swath width, cutoff жагсаалт, хэрэгтэй бол fallback density-г
   мэргэжилтэнтэй урьдчилан тогтоож багц үүсгэнэ.

Гаралт: Minimum Curvature coordinate error CSV; X/Y/Z volume-weighted model-vs-reference swath;
cutoff бүрийн volume, tonnes, mass-weighted mean grade, contained-metal хүснэгт;
SVG графиктай HTML; бүх мөр/тохиргоо/хэштэй JSON; хүний хяналтын жагсаалт.
HTML урт хүснэгтийн эхний 500 мөрийг харуулна; бүрэн өгөгдөл CSV/JSON-д үлдэнэ.
50,000 хүртэл desktop блок, reference тус бүр 32 MB/50,000 мөрийн хязгаартай.

Автомат шалгалт тэнцсэн ч `independent_review_verified=false` хэвээр.
±1–2% нь төслийн сонгосон тоон босго; CP-ийн эрх, ордын геологийн үнэмшил, local bias,
wireframe/domain-ийн үндэслэл, JORC/ЭБМЗ-ийн нийцэл, гарын үсгийг автоматаар батлахгүй.
Validation Letter-ийг программ өөрөө бичиж баталгаажуулахгүй. CP-ийн хяналтын хамрах хүрээ,
өгөгдлийн гарал, зөрүү бүрийн тайлбар, хязгаарлалт, огноо, гарын үсэг тусдаа шаардлагатай.
Нөөцийн A/B/C ангилал болон Measured/Indicated/Inferred-ийг автоматаар хооронд нь хөрвүүлэхгүй.

## 4. Геологийн үеийн дараалал

`Мэргэжлийн баталгаажуулалт → Геологийн үеийн дараалал JSON…`.
`examples/acceptance/chronology-demo.json` нь **локал координатын аналитик жишээ**;
өөрийн ордын координат/интерпретациар солихгүйгээр demo UTM төсөлд хэрэглэхгүй.

`events` жагсаалт хөгшнөөс залуу руу явна. Intrusion нь field ≥0 талд материал өгнө;
vein/stratigraphy нь lower ≥0, upper <0 хоёр гадаргын хооронд үүснэ; erosion нь ≥0 талын
өмнөх материалыг арилгана. Залуу үйл явдал өмнөх харьяаллыг дарна. Блокийн төв бүр нэг
материал эсвэл UNASSIGNED болно. Grade, variance, хуучин run hash болон холбоотой үр дүн
хүчингүй болж дахин үнэлгээ шаардана. Өнгө/тайлбартай instanced preview нээгдэнэ.

Field төрөл нь plane эсвэл signed-control local linear RBF. 4–50,000 control, 4–128 local
neighbor дэмжинэ; глобал N×N dense матриц байгуулахгүй. Backend нь SciPy local-neighbor RBF;
**Rust FMM/PoU биш**, хурд болон глобал залгаасын гөлгөр байдлын баталгаа биш.
Recipe-ийн curved/planar FaultNetwork нь explicit slip-тэй нийтлэг restored frame өгнө.
Fault/stratigraphic event-үүдийн бүрэн цаг хугацааны сэргээн байгуулалт биш.
Одоогийн desktop хэрэглээ 50,000 блок, 32 event; watertight geological solids, arbitrary
mesh CSG, adaptive boundary conformity болон Leapfrog-ийн цөмтэй equivalence хийгдээгүй.

## 5. Эргэлтийн хөрвүүлэлт

CSV-ийн `Explicit rotated / sub-block grid` сонголтод `Orientation source`-оос эх JSON сонгож болно.
Мөн тусдаа `Эх программын эргэлт хөрвүүлэх…` хэрэгсэлтэй. Source Software dropdown нь
Micromine/Leapfrog/Datamine/GSLIB-ийн гарал бүртгэх зориулалттай; vendor convention таахгүй.

Дэмжих representation:

- `matrix_enu`: 3×3 right-handed orthonormal matrix; баганууд нь local axes, мөрүүд нь ENU.
- `axes_azimuth_plunge`: эх программын экспортолсон **хоёр perpendicular тэнхлэгийн**
  азимут (хойноос CW), plunge (доош эерэг). Зөвхөн Axis 1-ийн bearing+plunge хангалтгүй.
- `euler_explicit`: active right-handed Euler; `sequence`-ийн том үсэг intrinsic,
  жижиг үсэг extrinsic; radians биш degrees. Vendor талбаруудыг энэ дүрэмд нийцүүлэн
  баталгаажуулахгүйгээр сонгохгүй.
- `rainymine_enu`: одоогийн ENU azimuth/dip/roll.

Матрицыг orthogonality/determinant/reconstruction шалгалтаар хянана. Эх тодорхойлолт,
түүний SHA-256 болон хөрвүүлсэн өнцгийг импортын metadata-д хадгална.
`verified_against_vendor_fixture=false` хэвээр. Дор хаяж cardinal/tilted/vertical,
non-cubic rotated block болон search-neighbor fixture бүрийг vendor экспорттой тулгана.
Жишээ: `examples/acceptance/orientation-axes-demo.json`.

Native Micromine DAT/STR parser энэ өөрчлөлтөд нэмэгдээгүй. DAT нь binary талбартай байж
болох тул тодорхойлолт, хувилбар тус бүрийн зөвшөөрөлтэй reference fixture эсвэл SDKгүйгээр
байт/NULL/төрлийг таамгаар уншихгүй. Одоогоор vendor-оос CSV болон DXF/OBJ экспорт хэрэглэнэ.
Одоо байгаа Surpac STR уншигчийг Micromine STR уншигч гэж нэрлэхгүй.

## 6. Floating stope ба signing

Stope MILP нь 1–8 хэмжээтэй бүрэн regular-grid box candidate-ийг бүх боломжит байрлалд
гүйлгэн, давхцалгүй сонгоно. Per-block density, тонноор жинлэсэн агуулга, cutoff-оос доош
материалын **дотоод** dilution fraction, minimum mean grade-ийн хязгаартай.
5,000 блок/3,000 candidate-ийн хязгаар хэвээр. HiGHS-ийг SciPy MILP-ээр ашиглана;
Rust solver backend нэмээгүй. Pillar, stand-off, wall angle, external dilution, geotechnical
viability, arbitrary slice-based MSO болон Deswik/Micromine арилжааны MSO equivalence биш.

Windows дээр:

```powershell
./scripts/build_windows.ps1 -Production -Installer
```

Production preflight, EXE signing, Inno Setup installer build, installer signing-ийг нэг
командаар ажиллуулна. Certificate private key нь эзэмшигчийн Windows certificate store-д,
`RAINYMINE_SIGN_THUMBPRINT` тохирсон байна. Code-signing EKU, хүчинтэй хугацаа, signer identity,
trust verification, timestamp-ийг шалгана. Private key репод оруулахгүй.
Энэ өөрчлөлтөөр certificate худалдаж аваагүй, шинэ EXE/installer-д бодит гарын үсэг зураагүй.
Linux дээр PowerShell/certificate-store ажиллагаа туршаагүй; Windows release шалгалт шаардлагатай.

## Албан эх сурвалж

- JORC Code 2012, Competence and Responsibility, Table 1:
  https://www.jorc.org/docs/JORC_code_2012.pdf
- Micromine rotation fields / exported axes:
  https://onlinehelp.micromine.com/origin-beyond/en/mmfiles/IDH_FILE_ROTATION_FIELDS.htm
- Micromine binary fields → text conversion:
  https://webhelp.micromine.com/mm/24.5/English/Content/mmfiles/IDH_FILE_CONVERT_OLD.htm
- VTK glyph mapper:
  https://vtk.org/doc/nightly/release/9.3/html/classvtkGlyph3DMapper.html
- Microsoft SignTool:
  https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool
