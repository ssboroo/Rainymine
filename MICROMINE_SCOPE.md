# RAINYMINE — хэрэглэгчийн өргөтгөсөн шаардлага

Зорилго: Монгол интерфэйстэй, Windows дээр суулгаж интернэтгүй ажиллах геологи, уурхайн программ. Доорх нь хөгжүүлэлтийн хамрах хүрээ; хэрэгжсэн боломжийн баталгаа биш.

| Багц | Одоогийн суурь | Дараагийн хүлээн авах шалгуур |
|---|---|---|
| Өгөгдөл | CSV mapping, editable grid, collar/survey/assay/lithology validation, CRS, QA/QC | Бодит нэргүйжүүлсэн өгөгдөл; Excel/Access/SHP/TAB adapter; format round-trip |
| CAD | DXF, triangular OBJ | DWG болон Datamine/Surpac/Vulcan хувилбар тус бүрийн specification, лиценз, эталон файл |
| 3D | Цооног, terrain, mesh, blocks, clipping, picking, хоёр viewport | Том өгөгдлийн performance benchmark; plot layout/хэвлэх |
| Геологи | Strings/polygons, constrained TIN, mesh topology checks | Explicit loft, RBF implicit, stratigraphy, fault constraints; геометрийн эталон |
| Геостатистик | IDW, OK; нэмэлт NN/SK; spherical variogram, cross-validation | IK probability, directional variography/maps, rotated ellipsoid, sub-blocking, swath plots |
| Нөөц | Density/cutoff tonnage-grade; UNCLASSIFIED | Uncertainty, domain boundary validation; хараат бус геологичийн benchmark, эрх бүхий мэргэжилтний JORC/NI 43-101 хяналт |
| Ил уурхай | Circular benches prototype | Economic pit shell, slope precedence, ramps, pushbacks, dumps/roads; эдийн засаг ба геометрийн эталон |
| Далд уурхай | Straight rectangular drive prototype | MSO, shafts, branching drives, rings, drill/blast; мэргэжлийн зураг төслийн хяналт |
| Маркшейдер | Surface TIN | LAS/LAZ, cut/fill, face survey reconciliation |
| Хуваарь | Capacity/precedence greedy scheduler | Gantt, grade control, material movement, blending, global optimization benchmark |
| Geobank / автоматжуулалт | Локал project persistence, undo/redo | Логгингийн сан, macro execution; Geobank API/эрх/тестийн сервер |
| Alastri/Spry/Advance төрлийн ажлууд | Тусгай модуль хэрэгжээгүй | Урт/богино хугацаа, нүүрс/dragline, далд уурхайн sequencing тус бүрийн solver ба benchmark |
| Pitram / Nexus төрлийн ажлууд | Хэрэгжээгүй | Fleet event ingestion, dispatch, optional sync/collaboration; offline conflict resolution |
| Windows түгээлт | CI installer, portable build, CPU renderer, native smoke | Code-signing certificate; жинхэнэ Windows төхөөрөмжийн баталгаажуулалт |

## Нэмсэн аргуудын утга

`nearest`: хайлтын эллипсоид доторх физик зайгаар хамгийн ойр сорьц. Minimum support тохиргоо үйлчилнэ. `simple_kriging`: spherical covariance, хэрэглэгчийн known_mean, point-support estimate болон conditional variance. Known mean-ийг held-out сорьцоос автоматаар тооцохгүй. Ordinary kriging нь `kriging` нэрээр хэвээр байна.

JORC/NI 43-101 тайлангийн нэр сонгох нь өөрөө стандартын нийцэл болохгүй. Эндхүү тооцоо мэргэжлийн нөөцийн баталгаажуулалтыг орлохгүй. Бүх модуль бүрэн хэрэгжээгүй.
