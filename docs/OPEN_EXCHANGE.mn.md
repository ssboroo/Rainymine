# Нээлттэй өгөгдлийн солилцоо

Төсөл, өгөгдөл, ажлын орчны үндсэн хадгалалт `.rmine` хэвээр. Шинэ командууд: **Мэргэжлийн хэрэгсэл → Нээлттэй солилцоо**, мөн **Бүх хэрэгсэл / Ctrl+K**.

| Команд | Дамжуулах өгөгдөл | Хязгаар |
|---|---|---|
| OMF 2.0-beta.1 экспорт | Collar, 5м алхамтай survey-station оролцуулсан замнал, surface points, strings, mesh triangles, rotated block/sub-block leaves ба бүх block attribute | Зөвхөн экспорт. OMF 1 биш. Хүлээн авагч **2.0-beta.1 Freeform subblocks** дэмжих ёстой. Бүтэн assay/lithology/structure/geotech реляцийн санг OMF geometry гэж дүр эсгэхгүй; тэдгээрийг CSV багцад авна. |
| GeoPackage экспорт | 3D collar, замнал, surface points, string/polygon, mesh triangle тусдаа GIS давхарга; CRS, GIS metadata | Блок загварын орлуулалт биш. Assay interval/block model-ийг энэ файлд экспортлохгүй. Surface нь тусдаа Polygon Z face; topology/solid semantics хадгалах формат биш. |
| GeoPackage импорт | Сонгосон POINT, LINESTRING, POLYGON ба MULTI хувилбарууд, атрибут, CRS, Z | 256MB/200000 vertex. 2D үед Z=0 гэж report-д тэмдэглэнэ. Polygon hole ring тусдаа `ring_role=hole` тэмдэглэгээтэй; нэг solid/domain болгон автоматаар тайлбарлахгүй. Raster/tile, GeometryCollection, NULL geometry дэмжихгүй. |
| CSV / CAD + metadata ZIP | Collar, Survey, Assay, Lithology, Structure, Geotech, Surface CSV; block attributes; geometry.dxf; mesh тус бүр OBJ/STL; manifest.json | Геометрийн формат дангаараа геологийн атрибутыг хадгалахгүй. Багцыг бүхлээр нь өгнө. CSV импортын автомат бүхэл bundle restore энэ хувилбарт байхгүй. |

## Солилцооны гэрээ

- Экспортод тодорхой **projected metre CRS** шаардана. EPSG/WKT, координатын XY дараалал, metre, grade unit (`%`, `g/t`, `ppm`), density `t/m3` metadata-д орно. Export нь CRS reproject эсвэл нэгж conversion хийхгүй. Үл мэдэгдэх CRS-ийг таамгаар шошголохгүй.
- OMF-д native `coordinate_reference_system`, `units`, project/element origin болон UVW axis vectors ашиглана. World coordinate double precision; origin shifting нь байршлыг өөрчлөхгүй.
- Parent grid доторх бодит leaf бүрийг OMF **Freeform subblock** болгон бичнэ. Parent хэмжээ, count, basis хадгалагдана; sparse/model domain-оос хасагдсан блокийг шинээр нөхөхгүй. Undivided parent ч нэг full leaf байна. Давхардал, parent boundary давсан блокийг алдаагаар зогсооно. Нэг parent-д ≤512 leaf.
- Number/text/boolean block attribute нь төрөл болон native NULL-тай. `grade=0` бол тэг; `grade=None` бол NULL. List/dict/tuple attribute JSON text гэж encoding metadata-тай. Агуулга ба variance-ийн нэгж тусдаа.
- CSV нь UTF-8 BOM, float-д 17 significant digit, NULL-д empty field ашиглана. Manifest-д баганын төрөл, nullable, model bounds/size/origin/rotation, агуулгын нэгж болон файл бүрийн SHA-256 байна. Төрөл хамаарах NULL/empty утгыг manifest-тай хамт тайлбарлана.
- OBJ координатын экспорт 17 significant digit болсон. STL ASCII нь мөн double координаттай. DXF/OBJ/STL нь CRS эсвэл бүх атрибутын стандарт хадгалалт биш тул ZIP manifest-тай нь дамжуулна.
- Vertical datum тодорхойгүйг `unspecified` гэж хадгална. Геодезийн өндрийн датумыг таамаглахгүй. Нөөцийн ангиллыг экспорт баталгаажуулахгүй.
- Бүх шинэ экспорт temporary файлд үүсээд atomic replace хийнэ. Алдаа/цуцлалтад өмнөх output хэвээр. Worker дээр project snapshot-оос тооцно. Нийт замналын экспорт ≤1000000 цэг.

## Хувилбар ба баталгаажуулалт

GMG schema/source pin: `64d305790b3415618a01f00a94cd914acd0b80ba`, format **2.0-beta.1**. OMF архив ZIP_STORED + `index.json.gz` + Zstd Parquet arrays; UINT32 индексийг Parquet 2.4 physical INT32 unsigned logical type-аар бичнэ. Required geometry arrays nullable биш. Багцад албан schema болон MIT лиценз орсон; JSON schema-г экспорт бүрд offline шалгана.

Тестүүд нь эргэлттэй UTM coordinate/dimensions-ийг файлаас буцаан тооцож шалгах, sparse sub-block, 0/NULL, parent overlap reject, cancellation/atomic overwrite, Unicode, GeoPackage-ийн OGC хүснэгтүүд/application ID/CRS/Z, CSV/CAD precision ба hash-ийг хамарна. Frozen/installed Windows smoke мөн OMF/GPKG/ZIP файл үүсгэж GPKG-г уншина.

**Бусад vendor программ болон GMG Rust reader-ээр хараат бус acceptance хийгдээгүй.** OMF beta хувилбарууд хоорондоо заавал нийцэхгүй; бодит хүлээн авагчид тест файл нээж geometry, count, tonnage/grade, units-ээ тулган баталгаажуулна. Энэ нь OGC compliance certification эсвэл бүх vendor-тай interoperability баталгаа биш.

Эх сурвалж:

- [GMG OMF](https://gmggroup.org/omf/)
- [Pinned GMG schema](https://github.com/gmggroup/omf-rust/blob/64d305790b3415618a01f00a94cd914acd0b80ba/omf.schema.json)
- [OMF format](https://gmggroup.github.io/omf-rust/format.html), [Parquet schemas](https://gmggroup.github.io/omf-rust/parquet.html)
- [OGC GeoPackage](https://www.ogc.org/standards/geopackage/)
- [Fiona 1.10 manual](https://fiona.readthedocs.io/en/stable/manual.html)
