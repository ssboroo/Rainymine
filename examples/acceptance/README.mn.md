# Инженерийн жижиг analytic жишээнүүд

Эдгээр нь зохиомол, хөгжүүлэгчийн шалгалтын оролт. Бодит орд, үйлдвэрлэгчийн independent reference биш.

- `stockpile.csv`: grade unit `%`, process ≥50 т/period, haul ≥150 т/period үед 2-р period-ийн reclaim grade=2%, closing=150 т, contained metal=3 т; нийт mass/metal balance error=0.
- `faults.json`: X=500000 plane-ийн positive талын материал +Z 10 м shear авсан гэж үзнэ. Restore нь positive талын Z-ээс 10 м хасна. Plane-ийн нормалд перпендикуляр slip; finite fault tip/complex geology биш. Stratigraphy dialog-ийн JSON талбарт оруулна.
- `haul-speed-bands.json`: зөвхөн хэрэглэгчийн speed band оруулах загвар. Эдгээр хурд нь ямар нэг үйлдвэрийн truck specification биш; инженерийн бодит өгөгдлөөр солино.
