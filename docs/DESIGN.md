# Дизайн KimderheimOS

Стиль вдохновлён iOS: чистый, светлый, с крупными скруглениями. Все элементы
собственные (см. [NOTICE.md](../NOTICE.md)).

## Как это работает
Android берёт внешний вид из **ресурсов** (цвета, размеры, строки, картинки).
Папка `vendor/kimderheim/overlay/` повторяет пути исходников Android, и наши значения
**подменяют** стандартные при сборке. Код GrapheneOS при этом не меняется.

```
overlay/frameworks/base/core/res/res/   ← ресурсы системы (framework-res)
    values/config.xml                   ← настройки
    values/dimens.xml                   ← размеры и скругления
    drawable-nodpi/default_wallpaper.png
```
Чтобы изменить другое приложение (например, SystemUI), создай
`overlay/frameworks/base/packages/SystemUI/res/values/...` с теми же именами ресурсов,
что в оригинале.

## Что настроено

| Параметр | Значение | Эффект |
|---|---|---|
| `config_icon_mask` | скруглённый квадрат | форма всех адаптивных иконок |
| `config_navBarInteractionMode` | `2` | навигация жестами |
| `config_dialogCornerRadius` | 28dp | диалоги |
| `config_buttonCornerRadius` | 24dp | кнопки-капсулы |
| `config_*FontFamily` | `inter` | шрифт интерфейса |
| `default_wallpaper` | градиент | обои по умолчанию |
| `bootanimation.zip` | логотип K | экран загрузки |

## Как поменять
- **Обои**: поправь цвета в `tools/generate_wallpaper.py` → `python3 tools/generate_wallpaper.py`.
  Или просто положи свою картинку `default_wallpaper.png` (1440×3200).
- **Загрузочная анимация**: `tools/generate_bootanimation.py` → запусти скрипт.
- **Форма иконок**: строка SVG-контура в `config_icon_mask` (координаты 0–100).
- **Шрифт**: замени файлы и `fonts_customization.xml` в `vendor/kimderheim/fonts/`.
  Используй только шрифты со свободной лицензией (OFL, Apache). SF Pro нельзя.

После изменений: `SKIP_ADEVTOOL=1 ./scripts/build.sh`.
