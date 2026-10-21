# Geobank / SQL Server adapter

Энэ нь Geobank-ийн proprietary API client биш. Geobank-ийн SQL Server өгөгдлийг DBA-ийн бэлтгэсэн canonical views-ээр уншдаг adapter. Vendor configuration tables-д хандахгүй, schema-г таахгүй, database-д INSERT/UPDATE/DELETE хийхгүй.

## DBA-ийн бэлтгэл

1. Geobank-ийн бодит schema-гаас дараах views-ийг үүсгэнэ. SQL schema нэрийг UI-д оруулж болно (default `dbo`).
2. Windows integrated-auth, зөвхөн эдгээр views дээр SELECT эрхтэй account ба 64-bit SQL Server ODBC driver/DSN бэлтгэнэ. SQL Driver нь application installer-д багтахгүй.
3. Тухайн database дээр SNAPSHOT isolation зөвшөөрсөн байна. App нь `SET TRANSACTION ISOLATION LEVEL SNAPSHOT`, `BEGIN TRANSACTION` ашиглаад дөрвөн view-г уншсаны дараа rollback/close хийнэ. Database settings-ийг app өөрчлөхгүй.
4. RAINYMINE → Загвар / оновчлол → Geobank / SQL унших. DSN нэр, schema оруулна. DSN-д credential хадгалуулахын оронд Windows эрх хэрэглэнэ. DSN/server/password төсөлд хадгалахгүй.

| View | Яг тохирох баганууд |
|---|---|
| RainymineCollars | hole_id, x, y, z, depth, azimuth, dip |
| RainymineSurveys | hole_id, depth, azimuth, dip |
| RainymineAssays | hole_id, from_m, to_m, grade |
| RainymineLithology | hole_id, from_m, to_m, rock |

Координат ба гүн метр; azimuth хойноос цагийн зүүний дагуу 0 ≤ azimuth < 360; dip −90…0. Assay grade нь одоогийн project grade_unit-тай ижил байна. CRS/unit-ийг adapter таахгүй; project тохиргоонд урьдчилан тааруулна. NULL, duplicate collar, interval/reference error, overlap зэргийг хүлээн авахгүй. View бүрд 100000 мөр; SQL timeout 20 секунд. Хоосон survey/lithology view зөвшөөрнө. Бүх хүснэгт validation давсны дараа нэг transaction байдлаар локал project шинэчлэгдэнэ; undo боломжтой.

Блок модель ба pit result-ийг цэвэрлэнэ; өмнөх RBF/pit meshes-ийг хуучин өгөгдөл гэж нэрлэнэ. Бусад custom geometry/surface-ийг автоматаар source database гэж үзэхгүй. Connection error-д driver-ийн нууц мэдээлэлтэй raw diagnostic харуулахгүй.

## Хүлээн авах тест

Unit tests нь fake DB connection дээр query boundary, snapshot, rollback, алдааны үед project өөрчлөгдөхгүй байхыг шалгана. Windows smoke нь pyodbc native module болон driver enumeration-ийг шалгана. Энэ нь байгууллагын бодит Geobank холболтын баталгаа биш.

Бодит acceptance-д DBA-аас canonical views, test DSN, anonymized reference export, CRS/grade units хэрэгтэй. Row counts, collar/sample keys, утгуудыг reference export-той тулгана. Нууц үгийг chat эсвэл git-д оруулахгүй.

Албан эх сурвалж: https://webhelp.micromine.com/gb/24.0/English/Content/gbcore/IDH_DATABASE_ENGINE.htm
RBF reference: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.RBFInterpolator.html
