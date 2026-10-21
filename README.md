# RAINYMINE 0.2.0 — Монгол оффлайн 3D уул уурхайн workbench

Windows desktop, Qt/PySide6 + VTK. Интернэт, сервер, бүртгэл, API key шаардахгүй. Суулгасан EXE нь Python шаардахгүй. Эх кодын dependency таталт болон Windows build-д интернэт хэрэгтэй.

**Энэ нь хөгжүүлэлтийн / туршилтын хувилбар. Micromine-ийн бүрэн орлуулалт, баталгаажсан нөөцийн тайлан, үйлдвэрлэлийн уурхайн төлөвлөгөө гэж үзэхгүй.** Micromine-ийн код, хаалттай формат болон брэнд ашиглаагүй.

## Windows суулгагч татах

1. [Windows desktop build](https://github.com/ssboroo/Rainymine/actions/workflows/windows.yml)-ийн хамгийн сүүлийн **амжилттай** ажиллуулалтыг нээнэ.
2. **Rainymine-Windows-x64** artifact татаж задална (GitHub нэвтрэлт шаардагдаж болно).
3. `Rainymine-0.2.0-Setup-x64.exe` суулгана. Эсвэл portable ZIP-ийг бүхлээр нь задалж `Rainymine.exe` ажиллуулна.
4. GPU/драйверын улмаас цонх хар байвал `Rainymine-Software.bat` эсвэл Start цэсний CPU rendering хувилбарыг ашиглана. Mesa/llvmpipe оффлайн драйвер багцад бий. Системийн DLL/драйверийг солихгүй; CPU горим том өгөгдөлд удаан байж болно.

EXE, суулгагч бэлэн болсон эсэхийг Actions-ийн **ногоон үр дүнгээр** шалгана. Өмнөх амжилттай 0.1.0 artifact нь шинэ 0.2.0 боломжуудыг агуулахгүй. Кодын тоон гарын үсгийн сертификат одоогоор холбогдоогүй.

## Мэргэжлийн интерфэйс

Цайвар ажлын орчин, нил ягаан navigation, бүлэглэсэн icon-той ribbon:

- **Төсөл:** нээх/хадгалах, CSV mapping, CRS, хүснэгт, undo/redo.
- **Өрөмдлөг:** collar/survey/assay/lithology, coverage, QA/QC controls, композит.
- **Геологи / DTM:** string/polygon засвар, constrained TIN, mesh topology, DXF/OBJ.
- **Блок модель:** grid/domain, IDW/ordinary kriging, variogram, cross-validation, tonnage-grade.
- **Уурхай:** bench prototype, шулуун underground drive, capacity schedule.
- **Харагдац:** камер, хоёр viewport, литологийн өнгө, зай/координат, PNG/VTP.

Зүүн талд layer list ба шинж чанар/огтлол, голд том цагаан 3D талбар, доор координатын хүснэгт болон status мөр. Эхлэхэд нээгдэх **ЖИШЭЭ** төсөл нь зохиомол орд, литологи, блокийн гурван ортогонал зүсэлттэй; бодит уурхайн өгөгдөл биш.

## Боломж ба бодит хязгаар

| Чиглэл | Оруулсан боломж | Хараахан баталгаажаагүй / дутуу |
|---|---|---|
| Өгөгдөл | CSV багана mapping/preview, мөрийн алдааны тайлан, SHA256 provenance, editable grid, 20 алхмын undo/redo, v1→v2 төслийн migration | Бодит уурхайн anonymized acceptance dataset өгөөгүй; detection-limit workflow дутуу |
| CRS | PROJ/pyproj, оффлайн, explicit source/target, XY axis order, метрийн projected target, local bearing rotation | Z босоо datum ба measured-depth scale хөрвүүлэхгүй; geometry/block model үүсгэхийн өмнө хөрвүүлнэ; геодезийн хяналтын бодит цэг хэрэгтэй |
| Өрөмдлөг / QAQC | Minimum curvature, assay/lithology интервал, missing-support coverage, standard Z-score, blank threshold, duplicate RPD | Хяналтын хязгаарыг лаборатори/геологич сонгоно; зөвшөөрөлгүй outlier устгахгүй; лабораторийн бүрэн batch certification биш |
| Геометр | XYZ TIN, breakline constrained TIN ба edge verification, string/polygon vertex editor, OBJ triangles, DXF LINE/POLYLINE/3DFACE, topology/volume report | Mesh self-intersection, robust Boolean solids, fault-aware modelling, full DXF entity coverage дутуу |
| Блок / үнэлгээ | Axis-aligned parent blocks, XY polygon extrusion domain, isotropic IDW / spherical ordinary kriging, ellipsoid neighbor search, variogram/fit, leave-one-hole-out validation, residual/observed charts | Point estimate at block centre; block kriging, rotated/sub-block model, directional variogram, top-cuts/domain-by-lithology, independent benchmark дутуу |
| Тайлан | Density t/m³, cutoff scenarios, volume/tonnes/mean grade, missing volume, kriging variance атрибут | **UNCLASSIFIED**; variance нь нөөцийн ангилал биш. Density fields, geologist review, uncertainty sensitivity / reporting-code certification дутуу |
| Төлөвлөлт | Circular bench/berm/slope prototype, straight underground drive mesh, capacity/precedence reconciliation ба greedy schedule | Ramp, geotechnics, ventilation/support, slope-sector precedence, haulage/stockpile, economic/global optimization дутуу |
| Түгээлт | Native Windows EXE, portable ZIP, Inno Setup, CPU renderer, source/packaged/installed smoke checks | Signed installer, бодит Windows төхөөрөмж/GPU matrix хараахан байхгүй |

Дэлгэрэнгүй бүтээгдэхүүний чиглэл: [ROADMAP.md](ROADMAP.md). Дээрх хязгааруудыг хэрэгжсэн мэтээр нэрлэхгүй.

## Ажиллуулах дараалал

1. `Төсөл → Шинэ`.
2. Project тохиргоогоор grade unit (%, g/t, ppm) сонгоно. Нэгж солих нь тоон утгыг хөрвүүлэхгүй.
3. `Өрөмдлөг → Амсар` сонгож CSV багануудыг зураглана. Дараа нь Survey, Сорьц, Литологи.
4. Өөр CRS-тай бол **геометр/блок модель үүсгэхийн өмнө** explicit source/target CRS-тай хөрвүүлнэ.
5. `Геологи / DTM`-д XYZ, strings/polygons, OBJ/DXF импортлоно.
6. `Блок модель үүсгэх`-д арга, search, variogram, composite coverage, bounds, cell size, domain тохируулна. Progress/cancel нь model тооцоонд ажиллана. Цуцлахад өмнөх model солигдохгүй.
7. Cross-validation, variogram, coverage/QAQC-г шалгаж дараа нь density/cutoff тайлан гаргана.
8. `.rmine` төсөлд хадгална. Хадгалах замтай өөрчлөгдсөн төсөлд 2 минут тутам `.autosave` үүснэ. Нөөцийг хуулж `.rmine` өргөтгөлтэй болгоод сэргээнэ.

## CSV форматууд

UTF-8/BOM, comma/semicolon/tab delimiter-ийг танина; эхний мөр гарчиг. Import mapping-оор өөр нэртэй баганыг зураглаж болно. Загварын нэр өгвөл амжилттай импортын дараа баганын тохиргоо төсөлд хадгалагдана. Дараагийн ижил төрлийн импортод загвараа сонгоод «Загвар хэрэглэх» дарна. Багана дутуу бол загвар хэрэглэхгүй; гараар шалгаж тохируулна. Ижил нэртэй загварыг шинэчилж болно; undo/redo дэмжинэ. Гарчиг давхардсан/хоосон эсвэл мөрийн баганын тоо зөрсөн CSV-г хүлээн авахгүй. `.xlsx`-ийг шууд нээхгүй; Excel-ээс CSV UTF-8 экспортлоно.

```csv
hole_id,x,y,z,depth,azimuth,dip
RM-001,500000,5300000,1450,250,45,-65
```

```csv
hole_id,depth,azimuth,dip
RM-001,0,45,-65
RM-001,250,60,-75
```

```csv
hole_id,from_m,to_m,grade
RM-001,0,10,0.3
```

```csv
hole_id,from_m,to_m,rock
RM-001,0,100,Боржин
```

```csv
x,y,z
499900,5299900,1450
500100,5299900,1460
500000,5300100,1455
```

QA/QC controls:

```csv
sample_id,type,measured,expected,sd
STD-1,standard,1.02,1,0.05
BLK-1,blank,0.01,,
DUP-1,duplicate,1.1,1,
```

X зүүн, Y хойд, Z дээш; ажиллах координат метр. Survey depth нь measured depth; azimuth хойноос цагийн зүүний дагуу; dip −90 босоо доош. Survey 0 м-ээс эхэлж, сүүлийн станцаас TD хүртэл тогтмол чиглэлээр сунгана. Интервалууд нэг хүснэгт дотроо давхцахгүй. Импорт бүхлээрээ хүчинтэй үед л сан солигдоно; буруу мөрийг чимээгүй алгасахгүй.

## Тооцооны тэмдэглэл

- Minimum curvature: `Δr=L/2·(u+v)·RF`, `RF=2tan(θ/2)/θ`, θ→0 үед RF=1. Partial station position нь spherical tangent interpolation-той.
- Composite нь 0-ээс anchored bins; `Σ(overlap·grade)/Σ(overlap)`, coverage нь support/bin length. Missing support 0 агуулга болж хувирахгүй.
- IDW нь сонгосон эллипсоид дотор nearest support, physical metre distance-аар жинлэнэ. Ordinary kriging нь spherical semivariogram + unbiasedness constraint бүхий linear system. Singular системийг unestimated гэж ил гаргана. Negative kriging grades-ийг чимээгүй clamp хийхгүй.
- Variogram isotropic; олон pair дээр deterministic seed 2026 ашиглаж 250000 хүртэл pair авна. Spherical fit exploratory бөгөөд геологийн model сонголтыг орлохгүй.
- Cross-validation нь default leave-one-hole-out; withheld hole-ийн бүх support-ыг training-с хасна. Training-fold mean baseline-тай харьцуулна. Независимый geological benchmark биш.
- Domain нь polygon-ийн XY extrusion ба Z bounds; cell-centre membership ашигладаг тул boundary volume нь ойролцоо. Block-centre point estimates-ийг block-average гэж нэрлэхгүй.
- Tonnage нь cell volume × constant density; unestimated volume тайланд тусдаа гарна. %/g/t/ppm-ийн weighted mean grade-г тооцно, contained metal conversion эсвэл resource classification хийдэггүй.
- Schedule нь value-per-tonne greedy heuristic. Predecessor өмнөх period-д дууссан байна. Capacity хэтэрсэн indivisible task төлөвлөгдөхгүй; infeasibility шалтгаан гаргана. Энэ нь economic pit optimizer биш.
- VTP export нь одоогоор цооногийн локал геометр. `.origin.json` offset-г нэмэхэд absolute coordinate сэргээнэ. PNG нь үндсэн viewport.

## Хэмжээ ба шалгалт

Хүснэгт бүр 100000 мөр; 5000 collar; 50000 блок; проект/импорт 32 MB хүртэл. Том төсөл хязгаар хэтэрвэл error гарна; хуучин файл солигдохгүй. Polygon 2000 орой хүртэл. Mesh self-intersection хараахан шалгахгүй. Том model render болон зарим analysis UI-г түр ачааллуулж болно; бүх computation background thread болоогүй.

```powershell
python -m unittest discover -s tests -v
python main.py --smoke --screenshot smoke.png
```

CI нь математик/өгөгдөл/геометр тест, ribbon + 2 viewport + block scene smoke, EXE build, packaged smoke, суулгагч build, silent install, installed EXE smoke хийдэг. Windows runner нь CPU OpenGL горим ашигладаг. Энэ нь бодит хэрэглэгчийн компьютер, бүх GPU болон бодит ордын independent review-г орлохгүй.

## Эх кодоос

Python 3.11/3.12 x64. `Setup-Windows.bat` нэг удаа, дараа нь `Start-Windows.bat`.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

EXE: `pip install pyinstaller==6.12.0`, дараа нь `scripts/build_windows.ps1`. CPU renderer: `scripts/prepare_mesa.ps1`. Inno Setup 6: `ISCC.exe installer\Rainymine.iss`.

Dependency лицензүүд тусдаа хүчинтэй: Qt/PySide6 LGPL/GPL/Commercial, VTK BSD, NumPy/SciPy BSD, PROJ/pyproj болон ezdxf-ийн upstream licenses. Dynamic Qt libraries-ийг багцад хэвээр хадгална. Micromine native file compatibility амлаагүй.
