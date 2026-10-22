# Мэдэгдэж буй хязгаар — 0.9.0

- Туршилтын, UNCLASSIFIED үр дүн. Бодит ордын хараат бус reference, геологичийн дүгнэлт байхгүй.
- Одоогийн нэмэлт боломж, хязгаарын эх сурвалж: [мэргэжлийн урсгал](../docs/PROFESSIONAL_WORKFLOWS.mn.md), [OMF/GeoPackage](../docs/OPEN_EXCHANGE.mn.md), [DH CSV](../docs/DH_IMPORT.mn.md).
- Sub-block нь finest-cell centre ангилал; exact solid clipping биш. Хагарал нь infinite plane barrier; displacement/curved fault restoration дэмжихгүй. RBF нь тусдаа extrapolation, structural constraint-гүй.
- Composite midpoint нь point support. Block midpoint quadrature-д convergence, sample-support regularization ба хараат бус тооцооны шалгалт дутуу.
- Schedule нь world-axis parent grid-д; rotated/sub-block schedule дэмжихгүй. Capacity MILP ба pit maximum-closure optimizer нь тусдаа үнэ/зорилго/нэгжтэй. README/диалогийн нэгжийг мөрдөнө. Spiral ramp / tunnel / ring геометр ба хязгаартай stope, joint blend MILP тусдаа нэмэгдсэн; traffic/dispatch, stockpile/reclaim/network coupling, иж бүрэн батлагдсан mine plan биш.
- SQL canonical views/site acceptance тусдаа. Тухайн байгууллагын өгөгдлийн эрх, серверийн бэлэн байдлыг программ өөрөө батлахгүй.
- Зарим том тооцоо, solver UI-г түр ачааллуулна. Өгөгдлийн/блокийн дээд хязгаарыг README-д үзнэ.
- Windows CI runner дээр шалгасан; бүх бодит компьютер/GPU, clean Windows 10/11, uninstall/upgrade matrix бүрэн биш.
- Суулгагч гарын үсэггүй. Системийн хамгаалалтыг унтраах заавар өгөхгүй; эзэмшигчийн эх холбоос ба hash-ийг шалгана.
- Брэндбүүкийн зураг энэ хувилбарын яг screenshot биш; лого, эхлэл, native ажлын талбарыг кодод оруулсан; постерын фото нь геологийн model биш. Бүх техникийн тайлбар монголчлогдсон гэж үзэхгүй.
- Local туслах нь reviewed-help routing; ерөнхий чат, мэргэжлийн геологийн зөвлөмж биш. Бусад GGUF/CPU хувилбарыг бүхэлд нь баталгаажуулаагүй.

- OMF нь 2.0-beta.1 экспорт л; импорт ба хараат бус cross-vendor acceptance хүлээгдэж байна. GeoPackage нь сонгосон vector layer, блокийн бүтэн сан биш.
- DH импорт raw эхийг хадгалдаг ч алдаатай scientific мөрийг засаж зохиохгүй. Survey байхгүй үед шулуун замналын таамаглал хэрэглэнэ; элемент солих нь хуучин scientific model-ийг дахин байгуулна.
- DWG нь гаднын ODA хэрэгслээс хамаарна; Datamine native reader байхгүй. Том external preview нь бүх өгөгдлийг GPU-д бүрэн ачаалсан 60 FPS баталгаа биш.
