# Өгөгдөл хамгаалалт ба мэргэжлийн урсгалын өргөтгөл — 2026-10-22

Энэ хувилбар таван хөгжүүлэлтийн чиглэлд бодит боломж нэмсэн. Сертификат, бодит ордын хараат бус хяналт, хэрэглэгчийн физик төхөөрөмжийн шалгалтыг автоматаар дууссан гэж үзэхгүй.

## 1. Сэргээх, лиценз, түгээлт

- Хадгалаагүй шинэ төсөл ч 120 секунд тутам dirty үед per-session recovery файлтай болно. AppLocalDataLocation/recovery дотор atomic replace + fsync ашиглана. Өмнөх амжилттай snapshot нь шинэ snapshot алдахад үлдэнэ. Сүүлийн snapshot-оос хойших ажил хамгаалагдаагүй хэвээр.
- Эхлэхэд болон **Файл → Хадгалаагүй төсөл сэргээх…**-ээс нөөц сонгоно. Сэргээсэн төсөл шинэ хуулбар, dirty, Save As шаардлагатай; эх `.rmine`-ийг автоматаар дарж бичихгүй. Эвдэрсэн нөөц, бусад session-ийн snapshot-ийг автоматаар устгахгүй. Амжилттай Save, шинэ төсөл, хэвийн хаалт нь зөвхөн тухайн session-ийн snapshot-ийг цэвэрлэнэ.
- Recovery нь `.rmine`-ийн өгөгдлийг хадгална. Холбосон `.rmdb` тусдаа файл; snapshot нь түүний хуучин агуулгын хуулбар биш. Нэг `.rmdb`-г олон төсөл холбож болох тул DB-г тусад нь нөөцөлнө.
- `.rmine` v1/v2/v3 уншилт, шинэ форматаар дахин хадгалалтыг автомат тест хамарна.
- Undo/Redo нь шахсан snapshot, 20 алхам болон нийт 64 MiB хадгалалтын хязгаартай. Нэг snapshot хязгаараас том бол тухайн алхмын Undo хадгалагдахгүй. Засварлах үеийн түр deepcopy санах ойн хэрэгцээг энэ нь арилгаагүй.
- `python scripts/check_release_readiness.py` нь preview-д blocker тайлагнана. `--production` нь owner public key, signing болон validation тохируулаагүй үед nonzero exit буцаана. Энэ бол тохиргооны preflight; мэдэгдлийн үнэн зөвийг нотлох аудит биш.
- `scripts/sign_windows.ps1 -Path ... -Required` нь Windows CurrentUser/My certificate store дахь `RAINYMINE_SIGN_THUMBPRINT`-ийн private key-ээр SHA256 + timestamp гарын үсэг хийж, Windows trust болон signer identity-г шалгана. Private key репозиторид орохгүй. Түлхүүргүй ердийн build нь **unsigned preview** хэвээр.
- Portable EXE-г ZIP үүсэхээс өмнө, installer-ийг ISCC-ийн дараа sign хийнэ. Production portable build: `./scripts/build_windows.ps1 -Production`; installer build-ийн дараа `./scripts/sign_windows.ps1 -Path dist/Rainymine-0.9.0-Setup-x64.exe -Required` ажиллуулна. CI одоогоор preview build; сертификат зохиож оруулаагүй.
- Шинэчлэгч файлыг ажиллуулахын өмнө `scripts/verify_update.ps1 -Installer ... -ExpectedSha256 ... -ExpectedSignerThumbprint ...` ашиглаж болно. Hash ба signer-ийг итгэлтэй release эхээс авна. `-Install` өгсөн үед л installer ажиллана. Automatic download/update service ороогүй.
- Installer нь өмнөх AppId, per-user замаа хадгалж, ажиллаж буй программыг хаах хүсэлт гаргана. CI нэг installer-ийг нэг замд хоёр удаа суулгадаг; энэ нь бүх түүхэн installer-аас upgrade шалгасан гэсэн үг биш. Лиценз/trial anchor, хэрэглэгчийн төсөл uninstall script-ээр устгагдахгүй.
- 7 хоногийн trial болон Ed25519 лицензийн байгаа тестүүд мөн ажиллана. Арилжааны owner түлхүүр/сертификат одоогоор тохируулаагүй; subscription billing/seat server шинээр нэмээгүй.

## 2. Өдөр тутмын урсгал

**Мэргэжлийн хэрэгсэл → Ажлын урсгал → Импорт → QA/QC → Үнэлгээ → Экспорт…**

Импорт, өгөгдөл шалгах, лабораторийн QA/QC, модель/үнэлгээ, reference, экспорт руу шууд орно. Амсар/сорьц/CRS, QA/QC мөр, блок/тооцоогүй блокийн тоо харагдана. Үе шат бүрийн observed outcome, шалгасан хүн/алдааны тэмдэглэл, interaction duration төсөлд хадгалагдана. Duration-д цонхтой ажилласан хугацаа орно; арын тооцооны нийт хугацаа биш. Completed нь хэрэглэгчийн өөрийн тэмдэглэл; программ геологичийн дүгнэлт болгож баталгаажуулахгүй.

## 3. Reference харьцуулалт

Үндсэн `x,y,z,grade` CSV дээр `dx,dy,dz,density,domain` нэмэлт багана дэмжинэ. `dx/dy/dz`-ийг гурвууланг өгнө. Нягтын нэгж t/m³, координат/хэмжээ метр. Нэгж, CRS, support, геологийн таамаг ижил гэдгийг урьдчилан тохиролцоно; comparator reproject/conversion хийхгүй. Тухайн төсөлд сонгосон grade unit-ийг CLI/UI ашиглана.

- Blank grade = NULL; 0-ээс ялгаатай. Хоёулаа NULL бол numerical null agreement, нөөц баталгаажсан гэсэн үг биш.
- Төв, хэмжээ, нягт, домэйны зөрүү тус бүр мөрөнд харагдана. Хэмжээ/нягтад geometry relative tolerance хэрэглэнэ; grade өөр absolute/relative tolerance-той.
- Эзлэхүүн, тонн, тооцсон материалын contained metal, unestimated count, bias/RMSE/max error гарна. Density эсвэл geometry дутуу бол боломжгүй нийлбэрийг NULL үзүүлнэ; автоматаар 2.7 гэж таахгүй.
- `%` → 0.01, `ppm` / `g/t` → 0.000001 mass fraction. Металл зөвхөн grade-тай блокт хамаарна; тооцоогүй материалыг grade=0 болгохгүй.
- **HTML/JSON тайлан** хадгална. HTML-д гаднын текстийг escape хийнэ.
- Харьцуулалт нь block centre/dimensions/attributes; rotated orientation, mesh overlap, full topology, geological validity, resource classification-ийн шалгалт биш. Reference ≤50,000 блокийн өмнөх хязгаар хэвээр.

```bash
python scripts/compare_reference.py project.rmine independent.csv --density 2.7 --output review.html
```

Reference-ийг өөрийн үр дүнгээс хуулж independent гэж нэрлэхгүй. Бодит ордын зөвшөөрөл, эх reference-ийн хувилбар/гарал, мэргэжилтний тэмдэглэл, гарын үсэг шаардлагатай хэвээр.

## 4. Дискэн том блок сан

**Мэргэжлийн хэрэгсэл → Дискэн блок сан** дотор:

1. Төслийн projected metre CRS, grade unit-ээ тохируулна.
2. `.rmdb` regular, world-axis grid үүсгэнэ (дээд хязгаар 10 сая блок); эсвэл байгаа санг холбоно. Хязгаар нь бүх хэмжээнд гүйцэтгэлийн баталгаа биш.
3. Composite support-оос centre-support IDW ажиллуулна. Radius, neighbours, minimum, power-оо өгнө. Дубликат sample coordinate-ийг засахыг шаардана. Энэ engine нь kriging, anisotropy, geological/fault/layer boundary, per-hole limits агуулдаггүй; тэдгээрийг шаардсан том үнэлгээнд хэрэглэхгүй.
4. Блокийн ID-аар grade/density/domain засна. Өөрчлөлт дискэнд шууд commit хийгдэнэ; `.rmine` Save-аас хамаарахгүй.
5. Тусдаа дискэн Undo/Redo нь хааж нээсний дараа ч ажиллана. 20 revision / 2 сая өөрчлөгдсөн мөр хүртэл хадгална; түүнээс том bulk өөрчлөлт rollback-able transaction боловч commit-ийн дараах Undo түүх нь хадгалагдахгүй байж болно.
6. Тонн/металл бүх блок дээр тооцогдоно. Preview ≤100,000 sampled block; grade байхгүй үед цэгээр харуулна. Preview нь бүх блокийн дүрслэл/интерактив засвар биш.
7. Экспортын ZIP дотор бүх мөртэй `blocks.csv`, CRS/grade/density/null/grid metadata ба SHA256 бүхий `manifest.json` байна. CSV empty domain-г NULL гэж үзнэ. Grid, estimator дундаа cancel/error бол DB transaction бүхлээр rollback хийнэ. CSV/ZIP экспорт atomic replace ашиглана.

`.rmine` нь холбоосын **absolute path** хадгална. Төслөө өөр компьютерт зөөхдөө `.rmdb`-г хамт хуулж, тухайн төхөөрөмжийн замаар дахин холбоно. Үндсэн 50,000 блокийн in-memory model-ийн хязгаарыг өсгөөгүй. Windows support нь Python-д багтсан SQLite `UPDATE FROM` (3.33+) шаарддаг.

Дахин хэмжих:

```bash
python scripts/benchmark_disk_workflow.py --side 100 --output disk-workflow.json
```

Synthetic 1,000,000 блок: create → IDW → edit → undo/redo → bulk undo/redo → aggregate → sampled VTK buffers → бүх мөрийн CSV → reopen. Report нь platform, CPU, Python/SQLite, хугацаа, peak RSS, файл/hash, analytic mass balance агуулна. [Linux хэмжилт](benchmarks/disk-workflow-1m-linux.json). Windows CI ижил workflow-г ажиллуулж `windows-disk-workflow.json` artifact гаргана. Физик GPU FPS эсвэл бодит ордын хэмжилт биш.

## 5. Хязгаар нь тодорхой инженерийн боломж

**Мэргэжлийн хэрэгсэл → Хяналттай инженерийн загвар**:

- **Давхарга / хавтгай хагарлын шилжилт**: нийтлэг нормалтай зэрэгцээ contact plane-ууд, өсөх contact coordinate, доороос дээших unique layer names. Positive half-space дээрх planar shear-ийг chronology-ийн урвуу дарааллаар restore хийнэ. Slip нь fault plane-д tangent байх ёстой; finite tip/fold/erosion/contact network/watertight solid solver биш. Төвөөр ангилна; boundary clipping биш. Өмнөх grade/variance/diagnostics хүчингүй болно.
- **Давхаргаар тусгаарласан IDW**: дээрх frame-ийн restored coordinates дээр samples болон block centres-ийг ижил аргаар ангилж, layer тус бүр өөр estimator-той. Layer хооронд sample холихгүй. Sample-гүй layer NULL хэвээр. Үндсэн «шинэ модель үүсгэх» командаар геометрийг дахин үүсгэхэд тусдаа шинэ модель болно; layer workflow-г үргэлжлүүлэхдээ энэ командыг ашиглана.
- **Зангилааг бусад шугамд тааруулах**: vertex index, tolerance сонгож бусад шугамын vertex/segment-д тааруулна. Өөрийн шугамыг target болгохгүй. Polygon validation, native project Undo дэмжинэ; бүрэн mouse-driven CAD биш.
- **Овоолго / дахин таталтын баланс**: CSV-д `period,pile,received_t,received_grade,reclaimed_t,capacity_t`. Нэг pile/period нэг мөр; receipt дараа reclaim, perfect mixing, peak inventory capacity, period processing/haul limits, closing inventory/metal, mass balance. Haul capacity нь receipt+reclaim тонн. Optimization, segregation, losses, plant recovery, dispatch simulation биш.
- **Замын хэсэгчилсэн тээвэр**: signed gradient-ийн contiguous speed bands; ачаатай чиглэл ба хоосон буцах чиглэлийн налуу эсрэг тэмдэгтэй. Хэсэг бүрийн хугацаа, cycle, fleet throughput. Acceleration/braking/traffic/fuel/geotechnical road approval ороогүй.

[Жишиг оролтууд](../examples/acceptance/README.mn.md) болон `tests/test_foundations.py`-ийн analytic fixtures нь хөгжүүлэгчийн хяналт; хараат бус инженерийн sign-off биш.

## Хүлээгдэж буй бодит нотолгоо

- Owner public key, trusted code-signing certificate, байгууллагын түгээлтийн нөхцөл.
- Геологичдын ажлын бодит туршилт, бүртгэсэн алдаа/хугацаа, шийдсэн issue-үүд.
- Зөвшөөрөлтэй ордын independent reference, тохиролцсон tolerance, хянан баталсан тайлан.
- Хэрэглэгчийн Windows/GPU төхөөрөмж дээр project/driver/display matrix, crash/restore/upgrade acceptance.
- Нийлмэл fault network, том домэйнд geostatistics, integrated optimization/stockpile/dispatch зэрэг дараагийн мэргэжлийн solver-ууд.
