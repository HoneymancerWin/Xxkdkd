package os.kimderheim.launcher;

import android.content.ComponentName;
import android.graphics.drawable.Drawable;
import android.os.UserHandle;

/** Одно приложение на рабочем столе. */
final class AppInfo {
    /** Уникальный ключ: компонент + номер профиля пользователя (для рабочего профиля). */
    final String key;
    final String label;
    final Drawable icon;
    final ComponentName component;
    final UserHandle user;
    /** Можно ли удалить (системные приложения удалить нельзя). */
    final boolean removable;

    AppInfo(String key, String label, Drawable icon, ComponentName component, UserHandle user,
            boolean removable) {
        this.key = key;
        this.label = label;
        this.icon = icon;
        this.component = component;
        this.user = user;
        this.removable = removable;
    }

    String packageName() {
        return component.getPackageName();
    }
}
