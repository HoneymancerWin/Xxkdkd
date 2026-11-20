# KimderheimOS

Своя операционная система для Android на базе **GrapheneOS**: защищённое ядро системы и дизайн в стиле iOS.

<p align="center"><b>Версия 0.1.0</b> · только телефоны Google Pixel</p>

## Что уже есть

| Что | Где |
|---|---|
| Форма иконок «скруглённый квадрат» | `vendor/kimderheim/overlay/.../values/config.xml` |
| Жестовая навигация по умолчанию | там же |
| Крупные скругления диалогов и кнопок | `.../values/dimens.xml` |
| Системный шрифт Inter (свободный аналог SF Pro) | `vendor/kimderheim/fonts/` |
| Обои по умолчанию (мягкий градиент) | `.../drawable-nodpi/default_wallpaper.png` |
| Загрузочная анимация (белый логотип на чёрном) | `vendor/kimderheim/media/bootanimation.zip` |
| **Рабочий стол в стиле iOS** (страницы, док, поиск, редактирование) | `vendor/kimderheim/apps/KimderheimLauncher/` |
| Экран блокировки: фонарик и камера в углах, часы шрифтом Inter | `vendor/kimderheim/overlay/.../SystemUI/`, `fonts/` |
| Экспериментальный патч «большие часы всегда» | `patches/frameworks/base/` |
| Скрипты: зависимости, загрузка, сборка, ключи, релиз | `scripts/` |

## Быстрый старт

```bash
cp config.env.example config.env   # укажи модель Pixel и версию GrapheneOS
./scripts/setup-deps.sh            # зависимости (Ubuntu)
./scripts/sync.sh                  # исходники (~150+ ГБ, несколько часов)
./scripts/build.sh                 # сборка (несколько часов)
./scripts/make-keys.sh             # ключи подписи (один раз)
./scripts/release.sh               # подписанный образ для прошивки
```

Подробно:
- [docs/BUILD.md](docs/BUILD.md): требования и сборка
- [docs/FLASHING.md](docs/FLASHING.md): прошивка телефона
- [docs/DESIGN.md](docs/DESIGN.md): как устроен и как менять дизайн
- [docs/ROADMAP.md](docs/ROADMAP.md): план развития

## Структура

```
config.env.example        настройки сборки (скопировать в config.env)
scripts/                  сборка, подпись, загрузка исходников
tools/                    генераторы обоев и загрузочной анимации
vendor/kimderheim/
  config/kimderheim.mk    главный файл: что входит в KimderheimOS
  overlay/                изменения системных ресурсов (дизайн)
  fonts/                  шрифт Inter
  media/                  загрузочная анимация
  apps/KimderheimLauncher/ рабочий стол в стиле iOS
patches/                  экспериментальные правки кода GrapheneOS
docs/                     инструкции
```

Главный принцип: **наш код лежит отдельно** от GrapheneOS и подключается одной строкой. Поэтому обновление на новую версию GrapheneOS = поменять `GOS_TAG` и пересобрать.

## Правовое
См. [NOTICE.md](NOTICE.md). KimderheimOS не связана с проектом GrapheneOS и компанией Apple.
