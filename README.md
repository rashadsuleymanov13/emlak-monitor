# Emlak Monitor

Azərbaycandakı əsas emlak saytlarında (bina.az, binatap.az, emlak.az) yeni elanları avtomatik izləyən və push notification göndərən sistem.

## Nə edir?

- bina.az, binatap.az və emlak.az saytlarını mütəmadi olaraq yoxlayır
- Sizin filterlərinizə uyğun yeni elanları tapır
- ntfy.sh vasitəsilə mobil push notification göndərir
- Eyni elanı iki dəfə göndərmir (deduplication)
- İlk işə düşəndə mövcud elanları "görülmüş" kimi qeyd edir — yalnız yeni elanlar bildirilir

## Quraşdırma

```bash
# Repo-nu klonla
git clone https://github.com/YOUR_USERNAME/emlak-monitor.git
cd emlak-monitor

# Virtual environment yarat (tövsiyə olunur)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Dependency-ləri quraşdır
pip install -r requirements.txt
```

## İstifadə

### Normal run
```bash
python -m app.main run
```

### Dry-run (notification göndərmədən)
```bash
python -m app.main run --dry-run
```

### Status yoxla
```bash
python -m app.main status
```

### State sıfırla
```bash
python -m app.main reset
```

## Konfiqurasiya

`app/config.py` faylında bütün parametrləri dəyişə bilərsiniz:

| Parametr | Təsvir | Default |
|----------|--------|---------|
| `price_min` | Minimum qiymət (AZN) | 150,000 |
| `price_max` | Maksimum qiymət (AZN) | 200,000 |
| `area_min` | Minimum sahə (m²) | 60 |
| `area_max` | Maksimum sahə (m²) | 90 |
| `exclude_total_floors` | İstisna edilən bina mərtəbə sayları | [5] |
| `require_title_deed` | Kupça tələb olunur | true |
| `require_mortgage_ready` | İpoteka tələb olunur | true |
| `target_locations` | Hədəf ərazilər | (yuxarıya baxın) |
| `ntfy_topic` | ntfy mövzu adı | rs-emlak |
| `request_delay` | Sorğular arası fasilə (saniyə) | 2.0 |

## ntfy Push Notification

Sistem [ntfy.sh](https://ntfy.sh) istifadə edir. Bu pulsuz push notification xidmətidir.

### Quraşdırma:
1. Telefonunuza ntfy tətbiqini yükləyin ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/app/ntfy/id1625396347))
2. Tətbiqdə `rs-emlak` mövzusuna abunə olun
3. Hazırdır! Yeni elan tapılanda telefona notification gələcək

### Notification formatı:
```
🏠 BINA.AZ
📋 3 otaqlı mənzil
💰 175,000 AZN
📐 80 m²
🏢 Mərtəbə: 7/16
📍 Nərimanov rayonu
✅ Kupça var
✅ İpoteka mümkündür
🔗 https://bina.az/items/12345
```

## GitHub Actions

Sistem GitHub Actions ilə hər 5 dəqiqədən bir avtomatik işləyir.

### Quraşdırma:
1. Repo-nu GitHub-a push edin
2. Actions avtomatik aktivləşəcək
3. Manual da işlədə bilərsiniz: Actions → Emlak Monitor → Run workflow

### Workflow:
`.github/workflows/monitor.yml` faylında konfiqurasiya edilib. State faylı hər run-dan sonra avtomatik commit edilir.

## Yeni Sayt Adapteri Əlavə Etmək

Yeni sayt əlavə etmək üçün:

1. `app/adapters/` qovluğunda yeni fayl yaradın (məs. `yeni_sayt.py`)
2. `BaseAdapter` sinfindən miras alın:

```python
from app.adapters.base import BaseAdapter
from app.models import Listing

class YeniSaytAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "yenisayt.az"

    @property
    def base_url(self) -> str:
        return "https://yenisayt.az"

    def fetch_listings(self) -> list[Listing]:
        # Burada scraping logikasını yazın
        ...
```

3. `app/adapters/__init__.py` faylına əlavə edin:
```python
from app.adapters.yeni_sayt import YeniSaytAdapter
ALL_ADAPTERS = [..., YeniSaytAdapter]
```

## Filterlər Necə İşləyir

Sistem hər elanı aşağıdakı filterlərdən keçirir:

1. **Qiymət filteri**: Elanın qiyməti `price_min` və `price_max` arasında olmalıdır
2. **Sahə filteri**: Elanın sahəsi `area_min` və `area_max` arasında olmalıdır
3. **Mərtəbə filteri**: Binanın ümumi mərtəbə sayı `exclude_total_floors` siyahısında olmamalıdır
4. **Ərazi filteri**: Elanın başlığı, ünvanı və ya təsvirində hədəf ərazilərindən biri olmalıdır
5. **Kupça filteri**: Elanda kupça/çıxarış qeyd olunmalıdır
6. **İpoteka filteri**: Elanda ipoteka/kredit imkanı qeyd olunmalıdır

Ərazi analizi transliterasiya variantlarını da dəstəkləyir (məs. Atatürk = Ataturk, Nərimanov = Nerimanov).

## Köhnə Elan Niyə Təkrar Gəlmir?

Sistem SQLite bazasında hər elanın unikal açarını saxlayır:

1. **İlk prioritet**: Elanın ID-si (saytın verdiyi)
2. **İkinci prioritet**: URL-in hash-i
3. **Son çarə**: Başlıq + qiymət + sahə fingerprint-i

İlk run zamanı bütün mövcud elanlar "görülmüş" kimi bazaya yazılır, lakin notification göndərilmir. Sonrakı run-larda yalnız bazada olmayan elanlar üçün notification göndərilir.

## Testlər

```bash
pytest tests/ -v
```

## Layihə Strukturu

```
app/
  main.py           # CLI giriş nöqtəsi
  config.py          # Konfiqurasiya
  models.py          # Data modelləri
  filters.py         # Filter logikası
  matcher.py         # Əsas monitoring engine
  state.py           # SQLite state idarəetməsi
  notifier.py        # ntfy notification
  utils.py           # Ümumi utility-lər
  normalization.py   # Mətn normalizasiyası
  adapters/
    base.py          # Baza adapter sinfi
    bina_az.py       # bina.az adapteri
    binatap_az.py    # binatap.az adapteri
    emlak_az.py      # emlak.az adapteri
data/
  state.db           # SQLite state bazası
tests/               # Testlər
.github/workflows/
  monitor.yml        # GitHub Actions workflow
```
