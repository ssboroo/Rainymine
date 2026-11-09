# Render ба production хүлээн авах шалгалт

2026-10-23 · ажлын орчны бодит нэмэлт ба нээлттэй release шалгуур.

## Шинэ ажлын удирдлага

**Харагдац → Дүрслэлийн хяналт** бүлэг эсвэл Ctrl+K хайлт:

- **Render тохиргоо**: fast / balanced / quality. Fast нь depth peeling/FXAA-г унтрааж ирмэгийн зардлыг багасгана; Quality нь ирмэг ба FXAA ашиглана. Бодит тунгалаг дүрслэлийн depth peeling нь GPU/driver дэмжлэгээс хамаарна, хэмжилт дээр `depth_peeling_used` харагдана. Дэмжээгүй драйверт чанарыг батлахгүй.
- **Fixed grade range**: жишээ `0,3.2`; legend ба mapper ижил range ашиглана. Blank бол автоматаар тогтооно. Эх агуулга тайрахгүй, тооцоо өөрчлөхгүй. NULL-г тэг гэж үзэхгүй.
- **Show NULL blocks**: агуулгагүй блокуудыг NaN scalar, саарал өнгөөр харуулна. Анхдагч false нь өмнөх төслийн дүрслэлийг хадгална.
- **Камер хадгалах / сэргээх**: 30 хүртэл named bookmark, world XYZ position/focus, view-up, projection, scale/angle. `.rmine`-д хадгалагдаж local-origin өөрчлөгдөхөд world coordinates хэвээр. Хадгалах/тохиргоо өөрчлөх нь төслийн Undo-той; камер сэргээх нь түр харагдац.
- **3D clipping box**: world-metre min/max зургаан mapper plane; section/cutaway filter-тэй давхар ажиллана. Source geometry, block IDs, grade, tonnes өөрчлөхгүй. GPU clipping-ийн задгай нүүрийг битүү solid cap гэж үзэхгүй; watertight geological cap solver нэмэгдээгүй.
- **Render хэмжилт**: одоогийн сцен дээр 12 camera-orbit кадрын median/p95 ms, FPS, viewport pixels, OS/VTK, depth-peeling төлөвийг хүснэгтээр гаргана. Цуцлах боломжтой. Нэг богино хэмжилт нь урт хугацааны тогтвортой ажиллагааны баталгаа биш.

Блок хүснэгтэд Ctrl/Shift-ээр олон мөр сонгоход 3D дээр ягаан хүрээ гарна. Ctrl+3D click нь сонголт нэмэх/хасах. Эх model-ийн эргэлттэй geometry, index-ийг ашиглана. Нэг удаад 2,000 хүрээ зурж GPU/CPU ачааллыг хязгаарлана; сонгосон бүх мөр хэвээр, status дээр дүрсэлсэн тоог ялган харуулна. Давхарга/хүснэгт refresh хийхэд хуучин сонголтыг арилгана.

Хулганыг 300 мс хөдөлгөөнгүй байлгахад block/цооногийн tooltip гарна. Камер хөдөлгөж байх үед, тооцоо/хэмжилтийн горимд hover picking ажиллахгүй. Tooltip координатыг Qt-ийн devicePixelRatio-оор хөрвүүлнэ; physical multi-monitor DPI acceptance тусдаа.

## Том preview-ийн LOD

Гаднын `.rmdb`/Parquet/AI preview-ийн native GPU pipeline-д **Хөдөлгөөний LOD ≤25,000** checkbox нэмсэн. 50,000-аас олон preview point байвал анхдагчаар идэвхжинэ. Камер хөдөлж эхлэхэд deterministic display thinning, зогсоход анхны бүтэн preview буцна. Source ID, grade, хэмжээ, quaternion orientation массив хадгалагдана. Тооцооны өгөгдөл болон эх файлыг өөрчлөхгүй.

Энэ нь зөвхөн draw budget; full preview RAM-д хэвээр байна. Бүрэн out-of-core viewport paging / adaptive octree LOD биш. Өмнөх ROI болон preview allocation budget хүчинтэй. Үндсэн desktop model-ийн 50,000 блокийн хязгаарыг арилгаагүй.

## Хэмжсэн нотолгоо

[Linux render хэмжилт](benchmarks/render-linux-20261023.json): synthetic 720 блок, 20 цооног, viewport 1002×509, Quality, 12 кадр, median ойролцоогоор 25.0 ms (40 FPS), p95 28.9 ms, depth peeling ажилласан. Xvfb/software OpenGL; Windows, сая блок, тогтвортой 60 FPS гэсэн баталгаа биш.

Бодит Qt/VTK цонхонд 60,000 external block preview → ≤25,000 interaction LOD → 60,000 full preview сэргээх ба хаах шалгалт амжилттай. MN/EN цонхны screenshot-ийг дотоод QA-аар шалгасан. Unit tests нь camera persistence/origin, finite input, clip planes/source IDs, NULL/selection geometry, LOD массивуудыг шалгана.

Өмнөх Windows build `39810380112` дээр UTF-8 manifest/SVG/HTML-ийг CP1252 default-аар уншсан 3 test error гарсныг explicit UTF-8 болгон зассан. Өгөгдлийн UTF-8 экспорт зөв байсан; assertion-ыг сулруулаагүй. Шинэ Windows run-ийн амжилтыг тусад нь шалгана.

## Production: хэрэгжүүлэлт ба баталгааг ялгах

Өмнөх чатны хувь нь хэмжсэн acceptance score байгаагүй. Цаашид дараах шалгалтын нотолгоогоор статус тогтооно:

| Шалгуур | Одоогийн нотолгоо / үлдсэн ажил |
|---|---|
| UI / MN-EN / жижиг дэлгэц | Automated native layout/readability тест; physical Windows DPI/multi-monitor шалгалт үлдсэн |
| Render / selection | GPU preview LOD, clipping, NULL, camera, tooltip, multiple selection хэрэгжсэн; cap topology ба out-of-core paging үлдсэн |
| Тооцоолол | Analytic болон Python/native parity тестүүд; arbitrary бодит ордын хараат бус баталгаа биш |
| Бодит орд / CP | Жишиг comparator ба review pack бэлэн; зөвшөөрөлтэй reference dataset, мэргэжилтний гарын үсэг шаардлагатай |
| Том өгөгдөл | Өмнөх Linux streamed 10M import/export хэмжилт; тодорхой physical Windows төхөөрөмж дээр бүтэн workflow/RAM/FPS шалгалт үлдсэн |
| Recovery / Undo | Одоогийн automated checks; байгууллагын power-loss, antivirus, network-drive болон upgrade UAT үлдсэн |
| Windows түгээлт | Build pipeline ба signing hooks; owner keys, distribution approval, Authenticode certificate/trust, physical-device acceptance pending |
| Local AI | Allowlist, Undo/cancel/audit тест; бодит GGUF-ийн Монгол хэлний eval ба уурхайн хэрэглэгчийн UAT үлдсэн |

[Production preflight бодит гаралт](benchmarks/production-preflight-20261023.json) нь `production_ready: false` гэж гарсан. Public key, code signing, owner distribution decision, independent deposit validation, physical Windows validation, owner signing-key configuration нь нээлттэй. Эдгээрийг кодонд `completed` гэж сольсноор баталгаа үүсэхгүй. Micromine-той бүрэн дүйцсэн эсвэл 100% production болсон гэж энэ өөрчлөлтөөр зарлахгүй.
