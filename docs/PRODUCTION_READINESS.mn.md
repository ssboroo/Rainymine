# Үйлдвэрлэлийн түвшинд хүргэх хүлээн авах шалгуур

Энэ нь хөгжүүлэлтийн зорилго ба acceptance бүртгэл. Бүх шалгуур дууссан, Micromine бүрэн орлосон гэсэн мэдэгдэл биш. Кодод хэрэгсэл байгаа, synthetic тест өнгөрсөн, бодит уурхайн acceptance батлагдсан гэдэг нь тусдаа төлөв.

| Эрэмбэ | Ажлын багц | Хүлээн авах нотолгоо | Одоогийн үлдэгдэл |
|---|---|---|---|
| 1 | Өгөгдөл шилжүүлэх | Нэргүйжүүлсэн Micromine төсөл / экспорт, баганын mapping, ID/NULL/CRS/нэгж ба geometry харьцуулалт | Native DAT / бүтэн төсөл уншихгүй; бодит жишээ шаардлагатай |
| 2 | Хадгалалт ба сэргээх | Save/load/undo, тасалдсан бичилт, autosave сэргээх, schema migration тест | Их хэмжээний өгөгдлийн хадгалалтын шинэ архитектур, бодит эвдрэлийн matrix |
| 3 | Геологи / геостатистик | Тогтоосон эталон, домэйн/хагарал, variogram, kriging, swath, хараат бус геологичийн хяналт | Нийлмэл геологи, support/uncertainty ба үйлдвэрийн benchmark |
| 4 | CAD / уурхай | Зөв solid, slope/ramp/stope, эдийн засаг ба schedule-ийн хараат бус эталон | Бүрэн CAD, pushback, stockpile/reclaim, production sequencing |
| 5 | Том өгөгдөл | Тогтоосон төхөөрөмж дээр cold/warm load, RAM, FPS, cancel, interaction latency | 10M/50M resident SLA батлагдаагүй |
| 6 | Windows түгээлт | Бодит Windows 10/11, GPU/CPU, DPI, install/upgrade/uninstall, signed EXE/installer | Сертификат ба бодит төхөөрөмжийн acceptance |
| 7 | Pilot үйлдвэрлэл | Тогтмол ажиллах хэрэглэгч, алдаа/өгөгдөл алдагдлын бүртгэл, зөвшөөрсөн тайлан | Байгууллага, геологич ба уурхайн инженерийн баталгаажуулалт |

## Блок CSV импорт — суурь ба өргөтгөл

**Мэргэжлийн хэрэгсэл → Блок өгөгдөл → Micromine / CSV блок импорт…**

Micromine-оос CSV болгон экспортолсон блокийн хүснэгтэд зориулсан explicit mapping импорт. Энэ нь Micromine native DAT decoder биш. CSV нь UTF-8 / UTF-8 BOM, comma delimiter, header-тэй байна. Mapping-д x/y/z = **блокийн дэлхийн координат дахь төв**, dx/dy/dz = метрээр хэмжээ, grade = нэг сонгосон агуулгын баганыг өгнө. Баганын нэр заавал x/y/z байх шаардлагагүй; диалогоос сонгоно.

- Төсөл projected metre CRS, зөв агуулгын нэгжтэй байх ёстой; импорт эхлэхийн өмнө хэрэглэгч батална. CSV-ээс CRS-ийг танихгүй, хөрвүүлэхгүй.
- Анхны World-axis uniform parents горим нь ижил хэмжээтэй, эргэлтгүй parent grid; sparse grid зөвшөөрнө. Давхардсан төв, торноос зөрсөн төв, өөр хэмжээтэй блокийг татгалзана. Эргэлттэй / sub-block-д доорх explicit горимыг хэрэглэнэ.
- Хоосон / NULL / NONE / NAN агуулга → None; бодит 0 хэвээр. Сөрөг sentinel, `<limit`, infinity, буруу тоог алдаа гэж үзнэ. Алдаатай мөрийг чимээгүй алгасахгүй.
- 1.0 RC-д нягт, домэйныг ил тод mapping хийж, бусад баганыг текст attributes-д хадгална; эх нөөцийн ангиллыг автоматаар баталгаажуулахгүй. [1.0 заавар](V1_0.mn.md).
- Одоогийн блок модель солигдоно; ажиллаж буй файл өөрчлөгдвөл background үр дүнг хэрэглэхгүй. Төслийн undo/redo ашиглана. Импортын өмнө тусдаа хуулбар хадгална.
- Эхийн нэр, SHA256, mapping, CRS, нэгж, блок/хоосон агуулгын тоо model-ийн import_report ба engineering_runs-д хадгалагдана. Эх CSV өөрөө архивлагдахгүй; эх файлаа хадгална.
- Desktop ≤50,000 блок, CSV ≤32 MB; нийт `.rmine` хадгалалтын 32 MB хязгаар хэвээр. Ангилал **UNCLASSIFIED**.

Synthetic acceptance: UTM координаттай save/load, 0 ба NULL ялгаа, malformed/давхардсан/зөрүүтэй тор татгалзах, cancellation, column mapping, rotation/metre CRS шалгалт; мэдэгдэж буй гурван блокийн cutoff–volume–tonnage эталон. Бодит Micromine экспортын reference acceptance хүлээгдэж байна.

## Нэмэлт: эргэлттэй / freeform sub-block CSV

Импортын **Explicit rotated / sub-block grid** горимд origin XYZ, parent DX/DY/DZ, azimuth/dip/roll-ийг заана. Төв XYZ нь дэлхийн CRS-ийн метр; хэмжээ нь блокийн локал тэнхлэгийн метр. Origin нь parent торны доод булан. Leaf нь нэг parent дотор бүрэн багтана; sparse leaf зөвшөөрнө, parent-ийг children-тэй давхар оруулахгүй. Нэг parent-д ≤512 leaf; axis leaf/parent харьцаа ≥1e-5, parent хэмжээ 1e-6…1e7 м.

RAINYMINE-ийн ENU convention: azimuth хойноос цагийн зүүний дагуу, dip дээш эерэг, roll локал X-ийн тухай. Micromine-ийн Z/X/Y Euler metadata-г шууд эдгээр гурван талбарт хуулахгүй. Тэнхлэг, pivot ба мэдэгдэж буй булангийн координатаар хувиргалтаа батална. Header-ийн дараах field-type / metadata мөрүүдийг хэрэглэгч 0…3 гэж ил тод сонгож алгасуулж болно; тэдгээрийг автоматаар тайлбарлахгүй, тайланд бүртгэнэ. Micromine block export-д **Centre** байрлал ашиглах буюу CSV-ээ world-centre болгож бэлтгэнэ.

[Micromine-ийн албан ёсны CSV export тайлбар](https://onlinehelp.micromine.com/origin-beyond/en/mmfiles/IDH_EXPORT_BM_CSV.htm) нь field types, origin/parent size болон нэмэлт rotation мөрүүдтэйг тайлбарладаг. Энэ reader бүх vendor header / өнцгийн хувилбарыг автоматаар хөрвүүлэхгүй.

Импорт нь хуучин блокт хамаарах tonnage, schedule, optimization, stope, joint-blend ба external benchmark-ийн идэвхтэй үр дүнг цэвэрлэнэ. Undo-гаар өмнөх төслөө сэргээнэ. Нэмэлт source attributes 1.0 RC-д хадгалагдана; desktop хэмжээний хязгаар хэвээр.

## Гадаад инженерийн reference харьцуулалт

**Блок өгөгдөл → Гадаад блок геометр / агуулга харьцуулах…**

Reference CSV нь `x,y,z,dx,dy,dz,grade`; XYZ нь world centre, хэмжээ локал тэнхлэгийнх. Reference-ийн ENU angles-ийг тусад нь тохируулна. Matching нь coordinate tolerance дотор цорын ганц төвтэй, нэг model блокийг нэг л удаа хэрэглэнэ. Бүрэн coverage, хэмжээ, orientation, агуулгын абсолют/харьцангуй хүлцэл ба NULL/0 ялгааг шалгана. Эзэлхүүн, эх reference ба model SHA256, хүлцэл, мөрийн үр дүнг төсөлд бүртгэнэ.

**Numerical pass ≠ инженерийн баталгаа.** Reference-ийг өөрийн model-оос буцааж экспортлох нь хараат бус шалгалт болохгүй. Инженерийн нэр/эрх, эх reference-ийн гарал, Micromine хувилбар, CRS/нэгж, өнцгийн баталгаа, огноо ба гарын үсэг бүхий тусдаа хяналтын акт шаардлагатай. Программ independent_review_verified-ийг автоматаар true болгохгүй.

## Төлөвлөлтийн нэмэлт аудит

Joint mining/feed blend MILP нь сонгосон мөрүүдийг solver матрицаас тусдаа кодоор дахин шалгана: эх task-ийн утга, давхардал, хүчинтэй үе, predecessor нь өмнөх үед дууссан эсэх, олборлолт / боловсруулалтын багтаамж, feed grade-ийн mass inequality ба NPV. Зөрчилтэй үр дүнг төсөлд хэрэглэхгүй. Энэ нь үйлдвэрийн иж бүрэн төлөвлөлт болон хараат бус инженерийн баталгаажуулалтыг орлохгүй; stockpile/reclaim одоогоор байхгүй.

## Хэмжсэн импортын гүйцэтгэл

`python scripts/benchmark_block_csv.py --blocks 50000` — зохиомол UTM CSV, explicit parent geometry validation. [Хэмжилтийн JSON](benchmarks/block-csv-50k.json). CPU импортын хугацаа л хэмжсэн; RAM SLA, бодит уурхай, 10M/50M resident өгөгдөл, GPU FPS-ийг батлаагүй.

## Native DAT-ийн төлөв

Бие даасан native DAT decoder **хэрэгжээгүй**. Micromine-ийн [MMpy.BlockModel.open](https://webhelp.micromine.com/mm/24.5/English/Content/mmpython/MMpy-BlockModel-open.htm) нь Micromine орчны API бөгөөд RAINYMINE-д бие даан ажиллах reader гэж үзэхгүй. Дараагийн ажилд DAT-ийн хувилбар/төрөл, дагалдах файлууд, лицензтэй SDK буюу хэрэгжүүлэхэд хангалттай форматын баримт, мөн reference экспорт ба нууцлалгүй бодит жишээ шаардлагатай. Одоогийн шилжүүлэх зам нь CSV / DXF зэрэг солилцооны формат.

### Том тайлангийн хүснэгт

Read-only тооцооны тайланг QAbstractTableModel / QTableView-ээр харуулна. Нүд бүрт QTableWidgetItem үүсгэхгүй; дэлгэцэд шаардлагатай утгыг хүсэх үед уншина. CSV экспорт бүтэн үр дүнг гаргана. Editable scientific grid тусдаа хэвээр. Сая мөрийн виртуал эх дээрх model тест нь индекс/NULL/0-ийг шалгасан болохоос сая блокийн 3D FPS буюу бүх өгөгдлийн RAM SLA-г батлаагүй.
