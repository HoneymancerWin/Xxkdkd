# Сборка KimderheimOS

## 1. Что нужно

**Компьютер**
- Linux x86_64, лучше Ubuntu 24.04 LTS (WSL2 на Windows возможен, но медленнее)
- 32 ГБ RAM или больше (с 16 ГБ нужен swap 32+ ГБ, сборка будет медленной)
- 400 ГБ свободного места на **SSD**
- Чем больше ядер процессора, тем лучше: первая сборка занимает 2–8 часов

**Телефон**: Google Pixel, который поддерживает GrapheneOS.
Актуальный список: https://grapheneos.org/faq#supported-devices

## 2. Кодовые имена устройств

| Модель | `DEVICE` | Модель | `DEVICE` |
|---|---|---|---|
| Pixel 10 Pro Fold | `rango` | Pixel 8a | `akita` |
| Pixel 10 Pro XL | `mustang` | Pixel 8 Pro | `husky` |
| Pixel 10 Pro | `blazer` | Pixel 8 | `shiba` |
| Pixel 10 | `frankel` | Pixel Fold | `felix` |
| Pixel 9a | `tegu` | Pixel Tablet | `tangorpro` |
| Pixel 9 Pro Fold | `comet` | Pixel 7a | `lynx` |
| Pixel 9 Pro XL | `komodo` | Pixel 7 Pro | `cheetah` |
| Pixel 9 Pro | `caiman` | Pixel 7 | `panther` |
| Pixel 9 | `tokay` | Pixel 6 / 6 Pro / 6a | `oriole` / `raven` / `bluejay` |

## 3. Настройка

```bash
git clone <этот репозиторий> kimderheim && cd kimderheim
cp config.env.example config.env
nano config.env
```
- `DEVICE`: кодовое имя из таблицы
- `GOS_TAG`: последний релиз GrapheneOS со страницы https://grapheneos.org/releases
  (номер вида `2025112000`). Бери тег, где есть твоё устройство.

## 4. Сборка

```bash
./scripts/setup-deps.sh    # один раз
./scripts/sync.sh          # скачать исходники
./scripts/build.sh         # собрать
```

Что делает `build.sh`:
1. Скачивает шрифт Inter (`fetch-fonts.sh`).
2. Копирует `vendor/kimderheim` в дерево исходников.
3. Запускает **adevtool**: извлекает закрытые файлы Pixel (драйверы камеры, модема и т.д.).
4. Добавляет в makefile продукта устройства строку
   `$(call inherit-product, vendor/kimderheim/config/kimderheim.mk)`.
5. Собирает образы.

Повторная сборка после изменения дизайна:
```bash
SKIP_ADEVTOOL=1 ./scripts/build.sh
```

## 5. Подпись и образ для прошивки

```bash
./scripts/make-keys.sh     # один раз на устройство. СДЕЛАЙ РЕЗЕРВНУЮ КОПИЮ КЛЮЧЕЙ!
./scripts/release.sh
```
Готовый factory-образ появится в `$SRC_DIR/releases/<номер>/`. Дальше [FLASHING.md](FLASHING.md).

## 6. Обновление на новую версию GrapheneOS

1. Поменяй `GOS_TAG` в `config.env`.
2. `./scripts/sync.sh`. Скрипт сам откатит наши правки в исходниках GrapheneOS
   (строку подключения и патчи), а `build.sh` применит их заново.
3. `./scripts/build.sh && ./scripts/release.sh`

## Если что-то пошло не так

- **Команды сборки изменились.** GrapheneOS иногда меняет процесс. Сверь шаги в
  `scripts/build.sh` с https://grapheneos.org/build.
- **`Не нашёл makefile продукта`.** Найди файл вручную:
  `grep -rl "PRODUCT_DEVICE := $DEVICE" device/google/`, затем
  `PRODUCT_MK=путь ./scripts/build.sh`.
- **Ошибка сборки.** Скопируй последние ~50 строк вывода и пришли их, разберёмся.
