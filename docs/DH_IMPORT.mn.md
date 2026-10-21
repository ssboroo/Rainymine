# DH багц импорт

**Мэргэжлийн хэрэгсэл → DH өгөгдөл → DH CSV багц импорт**. `dh_collar.csv` болон бусад `dh_*.csv` файлаа хамт сонгоно. Ердийн CSV импортод DH нэртэй файл сонговол багц импорт руу чиглүүлнэ.

Дэмжих нэрс: dh_collar, dh_assay, dh_assay_pivoted, dh_geochemistry, dh_geology, dh_alteration, dh_event, dh_geotech, dh_hyperspectral, dh_recovery, dh_specgrav (`.csv`). Энэ preset нь эдгээр DH баганын гэрээтэй UTF-8 CSV-д зориулагдсан, бүх vendor-ийн дурын CSV биш.

- Collar-ийн `companyholeid` нь үзүүлэх hole ID; `id` нь geology-ийн `collarid`-тай холбогдоно. Давхардсан ID/name-ийг таамгаар нийлүүлэхгүй.
- `easting/northing/elevation/maxdepth/azimuth/dip`-ийг зөв талбарт холбоно. 360° азимутыг 0° болгон зөвшөөрөгдсөн эквивалент өнцөгт оруулж, тоог нь тайлагнана.
- GDA94, UTM/MGA, Australia zone 48…58-ийн metadata-аар EPSG:28348…28358 тодорхойлно. Zone холилдсон эсвэл танигдаагүй CRS-д алдаа гаргана; координат хөрвүүлэхгүй. Өндрийн datum болон эх өнцөг хадгалагдана; bearing true/grid datum-ийг эхэд байхгүй бол шийдсэн гэж үзэхгүй.
- **Downhole survey файл энэ preset-д байхгүй.** Survey station шинээр зохиохгүй. 3D замнал нь амсрын өнцгөөр шулуун гэсэн таамаг; үүнийг импортын тайлан болон төслийн CRS тайлбарт ил тод тэмдэглэнэ.
- Одоогийн core нь нэг grade channel-тай. Assay long эсвэл pivot хүснэгтээс **нэг attribute + unit** сонгож үнэлгээнд оруулна. Long/pivot-ийг давхар нийлүүлэхгүй. Pivot баганын suffix unit нь raw assay-ийн ижил attribute-ийн unit-тэй зөрвөл тэр channel-ийг сонгуулахгүй; raw channel-ийг ашиглана. PPM → ppm, PCT/PERCENT → %, GPT → g/t; Cu ба Cu_1, repeat assay-ийг автоматаар нэгтгэхгүй.
- `NULL`, `None`, хоосон утгыг grade=0 болгохгүй. Negative, `<limit`, LDL/BDL утгыг эх хэлбэрээр archive-д хадгална. Default **Exclude** нь тооцооноос хасна. **Half limit**-ийг хэрэглэгч зориуд сонгосон үед эх limit-ийн 1/2-ийг ашиглаж тайлагнана. `>limit` болон тоо биш утга тооцоонд орохгүй. Grade=0 нь жинхэнэ тэг хэвээр.
- Lithology нь сонгосон primary code attribute-ийн интервал. Бүх geology атрибутыг нэг rock болгон нийлүүлэхгүй. Overlap-ийн бүх оролцогч, orphan/bad-depth мөрийг идэвхтэй загварт оруулахгүй; эх мөр болон алдааны шалтгаан үлдэнэ. Exact duplicate-ийг чимээгүй арилгахгүй.
- `No data found` дан мөртэй файл нь **өгөгдөлгүй** гэж бүртгэгдэнэ. Hyperspectral/геотехникийн хэмжилт шинээр зохиохгүй.
- CSV баганын тоо зөрсөн мөрийг parse issue гэж тэмдэглэж, scientific projection-оос хасна. Эх CSV bytes нь бүхлээрээ хадгалагдана; unquoted comma-г таамгаар засахгүй.

## Бүх эх өгөгдөл хадгалагдана

11 эх файлын byte-exact хуулбарыг SHA-256 + bounded zlib/base64 archive болгон `.rmine` дотор хадгална. `.rmine`-ээ зөөхөд raw data хамт явна. MAX_ROWS=100000 гэсэн core хүснэгтийн хязгаарт урт raw attribute хүснэгтийг хүчээр оруулахгүй; raw нь archive, сонгосон цэвэр интервалууд core таблиц байна.

**DH эх хүснэгт / CSV экспорт** нь 200 мөрөөр хуудаслаж харуулна. Negative, qualifier, lab method, sample ID, бүх multi-element утгыг эхээр нь үзнэ. `Эх CSV-г яг хэвээр гаргах` нь SHA-256 шалгаж original bytes гаргана. Эх upload-ийг өөрчлөхгүй.

**DH сорьцын элемент солих** нь archive-аас шинэ өгөгдлийн төсөл байгуулна. Өмнөх блок/үнэлгээ/геометрийг шинэ элементийн үр дүн гэж авч үлдэхгүй. Амжилттай импортын дараа path цэвэрлэж шинэ `.rmine` нэрээр хадгалуулна; хуучин төслийг автоматаар дарж бичихгүй.

Хязгаар: файл тус бүр ≤32MB, багц ≤128MB, raw файл тус бүр ≤300000 мөр, base64 archive нийлбэр ≤12MB, эцсийн `.rmine` ≤32MB. Шахалтыг нээхдээ bytes/codec/hash/expanded-size-ийг шалгана. Source preset-д байхгүй unit/CRS/schema-г таамгаар холбохгүй.

Тест: byte-exact save/load/recover, 100001 raw мөр, missing/zero/censored, channel сонголт, source duplication, malformed Comments, No data sentinel, overlap/orphan, mixed CRS, cancellation, archive tampering, ердийн CSV-ээс зөв чиглүүлэх. Windows frozen/installed smoke нь зөвхөн synthetic DH fixture ашиглана; хэрэглэгчийн өгөгдлийг repository-д оруулахгүй.
