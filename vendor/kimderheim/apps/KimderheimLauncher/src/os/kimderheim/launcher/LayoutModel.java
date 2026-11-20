package os.kimderheim.launcher;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Расположение иконок на рабочем столе.
 *
 * Как в iOS, иконки идут сплошным потоком: страница N — это просто кусок списка
 * {@link #apps} размером pageSize. Плюс отдельный док до {@link #DOCK_MAX} иконок.
 * Класс не зависит от Android, поэтому его легко тестировать.
 */
final class LayoutModel {
    static final int DOCK_MAX = 4;

    final List<String> dock = new ArrayList<>();
    final List<String> apps = new ArrayList<>();

    /**
     * Синхронизирует расположение с реально установленными приложениями:
     * удалённые убирает, новые добавляет в конец (на последнюю страницу).
     *
     * @param installed   ключи установленных приложений в желаемом порядке (по алфавиту)
     * @param defaultDock ключи для дока при самом первом запуске
     * @return true, если расположение изменилось и его нужно сохранить
     */
    boolean reconcile(Collection<String> installed, List<String> defaultDock) {
        Set<String> inst = new LinkedHashSet<>(installed);
        boolean firstRun = dock.isEmpty() && apps.isEmpty();
        boolean changed = dock.retainAll(inst);
        changed |= apps.retainAll(inst);

        Set<String> seen = new HashSet<>();
        changed |= removeDuplicates(dock, seen);
        changed |= removeDuplicates(apps, seen);
        while (dock.size() > DOCK_MAX) {
            apps.add(0, dock.remove(dock.size() - 1));
            changed = true;
        }

        if (firstRun) {
            for (String k : defaultDock) {
                if (inst.contains(k) && !seen.contains(k) && dock.size() < DOCK_MAX) {
                    dock.add(k);
                    seen.add(k);
                    changed = true;
                }
            }
        }
        for (String k : inst) {
            if (seen.add(k)) {
                apps.add(k);
                changed = true;
            }
        }
        return changed;
    }

    /**
     * Перемещает иконку так, чтобы она оказалась в позиции index
     * в доке (toDock = true) или в общем списке.
     * Если док полон и иконка приходит со страницы, она меняется местами с иконкой дока.
     */
    void move(String key, boolean toDock, int index) {
        boolean inDock = dock.contains(key);
        boolean inApps = apps.contains(key);
        if (!inDock && !inApps) return;

        if (toDock && !inDock && dock.size() >= DOCK_MAX) {
            int i = clamp(index, 0, dock.size() - 1);
            int a = apps.indexOf(key);
            String out = dock.set(i, key);
            apps.set(a, out);
            return;
        }
        dock.remove(key);
        apps.remove(key);
        List<String> target = toDock ? dock : apps;
        target.add(clamp(index, 0, target.size()), key);
    }

    int pageCount(int pageSize) {
        if (pageSize <= 0) return 1;
        return Math.max(1, (apps.size() + pageSize - 1) / pageSize);
    }

    List<String> page(int page, int pageSize) {
        int from = Math.min(apps.size(), page * pageSize);
        int to = Math.min(apps.size(), from + pageSize);
        return new ArrayList<>(apps.subList(from, to));
    }

    static int clamp(int v, int min, int max) {
        return Math.max(min, Math.min(max, v));
    }

    private static boolean removeDuplicates(List<String> list, Set<String> seen) {
        boolean changed = false;
        for (Iterator<String> it = list.iterator(); it.hasNext(); ) {
            if (!seen.add(it.next())) {
                it.remove();
                changed = true;
            }
        }
        return changed;
    }
}
