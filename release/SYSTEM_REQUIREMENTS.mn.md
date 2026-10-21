# Орчны шаардлага ба турших суурь

- Зориулсан орчин: Windows x64 desktop. Windows 10/11 хэрэглэгчийн төхөөрөмж дээрх шалгалт эцэслээгүй.
- Баталгаажуулсан автомат орчин: GitHub Windows Server 2022 runner; Python 3.11 build, Qt/PySide6, VTK, optional Mesa CPU renderer.
- Ердийн EXE-д Python тусад нь суулгахгүй. CPU engine архитектурын нийцлийг бодит төхөөрөмж дээр шалгана.
- GPU: тохирох OpenGL driver; хар viewport үүсвэл багцын CPU renderer ашиглаж туршина. CPU renderer том өгөгдөлд удаан байж болно.
- RAM/дискний баталгаажсан хамгийн бага тоо тогтоогоогүй. 8 GB RAM-ыг эхний туршилтын суурь, model/том өгөгдөлд 16 GB-ыг турших суурь болгон авч хэмжинэ; энэ нь hardware certification биш.
- Сул диск: ZIP хэмжээ + задласан программ + model + төслийн өгөгдөл/нөөцийн нийлбэрээс илүү байна. Offline багцын model дангаараа ~1.28 GB. Таталтын хэмжээ нь задласан хэмжээтэй адил биш.
- Интернэт: таталт, dependency/build, ердийн багцын model анхны setup-д хэрэгтэй. Local model inference нь тухайн компьютерийн 127.0.0.1 process-ийг ашиглана. SQL-д байгууллагын сервер/ODBC driver шаардлагатай байж болно.

Нийтлэхийн өмнө release checklist дээр бодит төхөөрөмжийн Windows build, CPU, RAM, GPU/driver, model ачаалалтын цаг, memory хэрэглээг бүртгэнэ.
