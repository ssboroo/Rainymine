# Мэдэгдэж буй хязгаар — 0.6.0

- Туршилтын, UNCLASSIFIED үр дүн. Бодит ордын хараат бус reference, геологичийн дүгнэлт байхгүй.
- Sub-block нь finest-cell centre ангилал; exact solid clipping биш. Хагарал нь infinite plane barrier; displacement/curved fault restoration дэмжихгүй. RBF нь тусдаа extrapolation, structural constraint-гүй.
- Composite midpoint нь point support. Block midpoint quadrature-д convergence, sample-support regularization ба хараат бус тооцооны шалгалт дутуу.
- Schedule нь world-axis parent grid-д; rotated/sub-block schedule дэмжихгүй. Capacity MILP ба pit maximum-closure optimizer нь тусдаа үнэ/зорилго/нэгжтэй. README/диалогийн нэгжийг мөрдөнө. Инженерийн ramp, traffic/dispatch, stockpile/network coupling, иж бүрэн батлагдсан mine plan биш.
- SQL canonical views/site acceptance тусдаа. Тухайн байгууллагын өгөгдлийн эрх, серверийн бэлэн байдлыг программ өөрөө батлахгүй.
- Зарим том тооцоо, solver UI-г түр ачааллуулна. Өгөгдлийн/блокийн дээд хязгаарыг README-д үзнэ.
- Windows CI runner дээр шалгасан; бүх бодит компьютер/GPU, clean Windows 10/11, uninstall/upgrade matrix бүрэн биш.
- Суулгагч гарын үсэггүй. Системийн хамгаалалтыг унтраах заавар өгөхгүй; эзэмшигчийн эх холбоос ба hash-ийг шалгана.
- Брэндбүүкийн зураг энэ хувилбарын яг screenshot биш; шинэ лого/эхлэл/интерфэйсийг бүхэлд нь кодод оруулаагүй. Бүх техникийн тайлбар монголчлогдсон гэж үзэхгүй.
- Local туслах нь reviewed-help routing; ерөнхий чат, мэргэжлийн геологийн зөвлөмж биш. Бусад GGUF/CPU хувилбарыг бүхэлд нь баталгаажуулаагүй.
