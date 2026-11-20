#
# KimderheimOS — продуктовая конфигурация.
#
# Этот файл подключается к продукту устройства GrapheneOS скриптом
# scripts/build.sh (строкой inherit-product). Всё, что делает систему
# «KimderheimOS», подключается отсюда — код GrapheneOS почти не трогаем,
# чтобы обновления переносились без конфликтов.
#

KIMDERHEIM_VERSION := 0.1.0

# --- Дизайн: оверлеи ресурсов (форма иконок, скругления, обои, шрифт) ---
PRODUCT_PACKAGE_OVERLAYS += vendor/kimderheim/overlay

# --- Информация о системе ---
PRODUCT_PRODUCT_PROPERTIES += \
    ro.kimderheim.name=KimderheimOS \
    ro.kimderheim.version=$(KIMDERHEIM_VERSION)

# --- Загрузочная анимация ---
PRODUCT_COPY_FILES += \
    vendor/kimderheim/media/bootanimation.zip:$(TARGET_COPY_OUT_PRODUCT)/media/bootanimation.zip

# --- Шрифт Inter (скачивается scripts/fetch-fonts.sh) ---
ifneq ($(wildcard vendor/kimderheim/fonts/Android.bp),)
PRODUCT_PACKAGES += \
    kimderheim_fonts_customization.xml \
    kimderheim_Inter-Regular.ttf \
    kimderheim_Inter-Medium.ttf \
    kimderheim_Inter-SemiBold.ttf \
    kimderheim_Inter-Bold.ttf
endif
