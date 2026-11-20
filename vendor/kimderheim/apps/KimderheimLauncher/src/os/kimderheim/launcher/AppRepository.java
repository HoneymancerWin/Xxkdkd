package os.kimderheim.launcher;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.LauncherActivityInfo;
import android.content.pm.LauncherApps;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.drawable.AdaptiveIconDrawable;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.InsetDrawable;
import android.net.Uri;
import android.os.Process;
import android.os.UserHandle;
import android.os.UserManager;
import android.provider.MediaStore;

import java.text.Collator;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Загружает список приложений и их иконки. Вызывать НЕ из главного потока. */
final class AppRepository {
    private final Context context;
    private final LauncherApps launcherApps;
    private final UserManager userManager;

    AppRepository(Context context) {
        this.context = context;
        this.launcherApps = context.getSystemService(LauncherApps.class);
        this.userManager = context.getSystemService(UserManager.class);
    }

    /** Все приложения всех профилей, отсортированные по названию. */
    List<AppInfo> loadAll() {
        List<AppInfo> result = new ArrayList<>();
        PackageManager pm = context.getPackageManager();
        UserHandle me = Process.myUserHandle();
        for (UserHandle user : userManager.getUserProfiles()) {
            long serial = userManager.getSerialNumberForUser(user);
            for (LauncherActivityInfo info : launcherApps.getActivityList(null, user)) {
                if (info.getComponentName().getPackageName().equals(context.getPackageName())) {
                    continue; // себя не показываем
                }
                Drawable icon = normalizeIcon(info.getIcon(0));
                if (!user.equals(me)) {
                    icon = pm.getUserBadgedIcon(icon, user); // значок рабочего профиля
                }
                ApplicationInfo ai = info.getApplicationInfo();
                boolean removable = (ai.flags & ApplicationInfo.FLAG_SYSTEM) == 0;
                String key = info.getComponentName().flattenToShortString() + "#" + serial;
                CharSequence label = info.getLabel();
                result.add(new AppInfo(key, label == null ? "" : label.toString(), icon,
                        info.getComponentName(), user, removable));
            }
        }
        Collator collator = Collator.getInstance(Locale.getDefault());
        result.sort((a, b) -> collator.compare(a.label, b.label));
        return result;
    }

    /** Ключи приложений для дока при первом запуске: Телефон, Браузер, Сообщения, Камера. */
    List<String> defaultDock(List<AppInfo> apps) {
        Intent[] intents = {
                new Intent(Intent.ACTION_DIAL),
                new Intent(Intent.ACTION_VIEW, Uri.parse("https://example.com")),
                Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, Intent.CATEGORY_APP_MESSAGING),
                new Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA),
        };
        List<String> keys = new ArrayList<>();
        for (Intent intent : intents) {
            String pkg = resolvePackage(intent);
            if (pkg == null) continue;
            for (AppInfo a : apps) {
                if (a.packageName().equals(pkg) && a.user.equals(Process.myUserHandle())) {
                    keys.add(a.key);
                    break;
                }
            }
        }
        return keys;
    }

    private String resolvePackage(Intent intent) {
        PackageManager pm = context.getPackageManager();
        ResolveInfo ri = pm.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);
        if (ri != null && ri.activityInfo != null && !"android".equals(ri.activityInfo.packageName)) {
            return ri.activityInfo.packageName;
        }
        // Нет приложения по умолчанию — берём первое подходящее системное
        for (ResolveInfo r : pm.queryIntentActivities(intent, PackageManager.MATCH_SYSTEM_ONLY)) {
            if (r.activityInfo != null) return r.activityInfo.packageName;
        }
        return null;
    }

    /**
     * Адаптивные иконки система сама обрезает по форме из config_icon_mask
     * (у нас — скруглённый квадрат). Старые «квадратные» иконки кладём на белую подложку.
     */
    private static Drawable normalizeIcon(Drawable d) {
        if (d == null) return new ColorDrawable(Color.GRAY);
        if (d instanceof AdaptiveIconDrawable) return d;
        return new AdaptiveIconDrawable(new ColorDrawable(Color.WHITE), new InsetDrawable(d, 0.25f));
    }
}
