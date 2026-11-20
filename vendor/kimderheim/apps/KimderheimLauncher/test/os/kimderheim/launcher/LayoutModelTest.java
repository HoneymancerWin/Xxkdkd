package os.kimderheim.launcher;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/**
 * Простые тесты логики расположения иконок (без Android).
 * Запуск: vendor/kimderheim/apps/KimderheimLauncher/test/run.sh
 */
public final class LayoutModelTest {
    private static int failures;

    public static void main(String[] args) {
        firstRunFillsDockAndApps();
        newAppsGoToEnd();
        removedAppsDisappear();
        moveWithinPage();
        moveToFullDockSwaps();
        moveFromDockToPage();
        paging();
        if (failures > 0) {
            System.out.println(failures + " тест(ов) не прошли");
            System.exit(1);
        }
        System.out.println("Все тесты прошли");
    }

    static void firstRunFillsDockAndApps() {
        LayoutModel m = new LayoutModel();
        boolean changed = m.reconcile(Arrays.asList("a", "b", "c", "phone", "web"), Arrays.asList("phone", "web", "missing"));
        check("first run changed", changed);
        eq("first run dock", Arrays.asList("phone", "web"), m.dock);
        eq("first run apps", Arrays.asList("a", "b", "c"), m.apps);
        check("second reconcile unchanged", !m.reconcile(Arrays.asList("a", "b", "c", "phone", "web"), Arrays.asList("x")));
    }

    static void newAppsGoToEnd() {
        LayoutModel m = model(List.of("d"), List.of("c", "a"));
        m.reconcile(Arrays.asList("a", "b", "c", "d"), Collections.emptyList());
        eq("new app appended", Arrays.asList("c", "a", "b"), m.apps);
    }

    static void removedAppsDisappear() {
        LayoutModel m = model(List.of("d", "x"), List.of("c", "y", "a"));
        m.reconcile(Arrays.asList("a", "c", "d"), Collections.emptyList());
        eq("dock cleaned", List.of("d"), m.dock);
        eq("apps cleaned", Arrays.asList("c", "a"), m.apps);
    }

    static void moveWithinPage() {
        LayoutModel m = model(List.of(), List.of("a", "b", "c", "d"));
        m.move("a", false, 2);
        eq("move forward", Arrays.asList("b", "c", "a", "d"), m.apps);
        m.move("d", false, 0);
        eq("move back", Arrays.asList("d", "b", "c", "a"), m.apps);
        m.move("b", false, 99);
        eq("move past end", Arrays.asList("d", "c", "a", "b"), m.apps);
    }

    static void moveToFullDockSwaps() {
        LayoutModel m = model(List.of("1", "2", "3", "4"), List.of("a", "b"));
        m.move("b", true, 1);
        eq("dock after swap", Arrays.asList("1", "b", "3", "4"), m.dock);
        eq("apps after swap", Arrays.asList("a", "2"), m.apps);
    }

    static void moveFromDockToPage() {
        LayoutModel m = model(List.of("1", "2"), List.of("a", "b"));
        m.move("1", false, 1);
        eq("dock shrinks", List.of("2"), m.dock);
        eq("apps grow", Arrays.asList("a", "1", "b"), m.apps);
        m.move("a", true, 0);
        eq("dock grows", Arrays.asList("a", "2"), m.dock);
    }

    static void paging() {
        LayoutModel m = model(List.of(), List.of("a", "b", "c", "d", "e"));
        eq("page count", 3, m.pageCount(2));
        eq("last page", List.of("e"), m.page(2, 2));
        eq("empty model has one page", 1, new LayoutModel().pageCount(24));
    }

    private static LayoutModel model(List<String> dock, List<String> apps) {
        LayoutModel m = new LayoutModel();
        m.dock.addAll(dock);
        m.apps.addAll(apps);
        return m;
    }

    private static void check(String name, boolean ok) {
        if (!ok) {
            failures++;
            System.out.println("FAIL " + name);
        }
    }

    private static void eq(String name, Object expected, Object actual) {
        if (!expected.equals(actual)) {
            failures++;
            System.out.println("FAIL " + name + ": ожидалось " + expected + ", получено " + actual);
        }
    }
}
