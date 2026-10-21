# Нийтлэхийн өмнөх шалгах хуудас

## Автомат баримт

- [x] 0.5.0 эх код `6ed490a95e4cb5b957bd0cdf3c55381792795f4a` дээр 94 тест давсан.
- [x] Source desktop, packaged EXE, installed EXE ба бодит local model smoke давсан — run 39605254612.
- [ ] Draft workflow эх build-ийн conclusion, commit, tree, version, ZIP/EXE бүтэц, model hash-ийг дахин баталсан.
- [ ] Гурван бинар файл, release kit, SHA256SUMS, manifest draft-д байршсан.
- [ ] Checksum-ийг дахин уншиж файлуудтай нь тулгасан.

Дээрх хоосон автомат мөрүүдийн бодит үр дүн release-manifest.json болон workflow log-д гарна; урьдчилан амжилттай гэж бөглөөгүй.

## Нийтлэхээс өмнө эзэмшигч шалгах

- [ ] Албан эзэмшигч, программын өөрийн түгээлтийн лиценз/нөхцөл, дэмжлэгийн сувгийг бөглөсөн.
- [ ] Third-party notice/license inventory-г хянасан; дутуу эх/мэдэгдэл байгаа эсэхийг тогтоосон.
- [ ] Code signing холбож шалгасан, эсвэл unsigned preview түгээх шийдвэрээ тодорхой бичсэн.
- [ ] Бодит Windows 10/11 x64 дээр clean install → launch → save/load → uninstall туршсан.
- [ ] Хуучин хувилбараас upgrade, төслийн нөөц ба rollback туршсан.
- [ ] Хоёр өөр GPU/driver болон CPU rendering дээр шалгасан.
- [ ] Offline ZIP-ийг шинэ хавтаст бүрэн задлаад интернэтгүй launch/local AI туршсан.
- [ ] Орон зай/монгол нэртэй зам, стандарт хэрэглэгчийн эрх, disk-full/corrupt download нөхцөлийг шалгасан.
- [ ] Шинэ брэндбүүк зурагтай actual interface-ийн зөрүүг хянаж, маркетингийн screenshot-ийг зөв нэрлэсэн.
- [ ] Геологи/инженерийн хязгаарыг release notes-д хэвээр үлдээсэн; бодит нөөцийн баталгаа гэж сурталчлаагүй.
- [ ] Туршсан төхөөрөмж/огноо/хариуцсан хүн/үр дүнг бүртгэсэн.
- [ ] Draft-ийн бүх файл, тэмдэглэл, tag/commit-ийг хянаад эзэмшигч нийтлэх шийдвэр гаргасан.

Draft workflow хэзээ ч `draft=false` болгохгүй.
