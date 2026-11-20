package os.kimderheim.launcher;

import android.app.Activity;
import android.app.ActivityOptions;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.LauncherApps;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Rect;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.UserHandle;
import android.view.DragEvent;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.PopupWindow;
import android.widget.TextView;
import android.widget.Toast;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

/**
 * Рабочий стол KimderheimOS в стиле iOS.
 *
 *  - все приложения лежат на страницах (без отдельного меню приложений);
 *  - новые приложения появляются в конце последней страницы;
 *  - док на 4 приложения;
 *  - свайп вниз или кнопка «Поиск» — поиск приложений;
 *  - долгое нажатие на иконку — меню; «Изменить экран» — режим покачивания,
 *    в котором иконки перетаскиваются и удаляются кнопкой «−».
 */
public final class LauncherActivity extends Activity implements SearchOverlay.Host {
    private static final int COLUMNS = 4;
    private static final int ICON_DP = 60;
    private static final int CELL_DP = 100;
    private static final int MIN_ROWS = 4;
    private static final int MAX_ROWS = 7;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService loader = Executors.newSingleThreadExecutor();
    private final LayoutModel model = new LayoutModel();
    private final Map<String, AppInfo> apps = new HashMap<>();
    private List<AppInfo> sortedApps = new ArrayList<>();

    private LauncherApps launcherApps;
    private AppRepository repository;
    private LayoutStore store;

    private HomeRoot root;
    private LinearLayout content;
    private PagedView pager;
    private PageIndicator indicator;
    private Dock dock;
    private TextView doneButton;
    private SearchOverlay search;
    private PopupWindow menu;

    private int rows = 6;
    private boolean loaded;
    private boolean editing;
    private boolean searchOpen;
    private boolean backRegistered;
    private String draggingKey;
    private View draggingView;
    private int flipDirection;

    private final Runnable reloadRunnable = this::reloadApps;

    private final Runnable flipRunnable = () -> {
        if (flipDirection != 0) {
            pager.snapToPage(pager.getCurrentPage() + flipDirection, true);
            flipDirection = 0;
        }
    };

    private final OnBackInvokedCallback backCallback = () -> {
        if (searchOpen) closeSearch();
        else if (editing) setEditing(false);
    };

    private final LauncherApps.Callback appsCallback = new LauncherApps.Callback() {
        @Override
        public void onPackageRemoved(String packageName, UserHandle user) {
            scheduleReload();
        }

        @Override
        public void onPackageAdded(String packageName, UserHandle user) {
            scheduleReload();
        }

        @Override
        public void onPackageChanged(String packageName, UserHandle user) {
            scheduleReload();
        }

        @Override
        public void onPackagesAvailable(String[] packageNames, UserHandle user, boolean replacing) {
            scheduleReload();
        }

        @Override
        public void onPackagesUnavailable(String[] packageNames, UserHandle user, boolean replacing) {
            scheduleReload();
        }
    };

    // ------------------------------------------------------------------ жизненный цикл

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        window.setDecorFitsSystemWindows(false);
        window.setNavigationBarContrastEnforced(false);

        launcherApps = getSystemService(LauncherApps.class);
        repository = new AppRepository(this);
        store = new LayoutStore(this);
        store.load(model);

        buildViews();
        setContentView(root);

        WindowInsetsController controller = window.getInsetsController();
        if (controller != null) {
            // светлые значки строки состояния поверх обоев
            controller.setSystemBarsAppearance(0, WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                    | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
        }

        launcherApps.registerCallback(appsCallback, handler);
        reloadApps();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        // Нажали «Домой», уже находясь на рабочем столе
        boolean alreadyOnHome = hasWindowFocus();
        dismissMenu();
        if (searchOpen) closeSearch();
        else if (editing) setEditing(false);
        else if (alreadyOnHome) pager.snapToPage(0, true);
    }

    @Override
    protected void onPause() {
        super.onPause();
        dismissMenu();
    }

    @Override
    protected void onDestroy() {
        launcherApps.unregisterCallback(appsCallback);
        handler.removeCallbacksAndMessages(null);
        loader.shutdownNow();
        super.onDestroy();
    }

    // ------------------------------------------------------------------ интерфейс

    private void buildViews() {
        root = new HomeRoot(this);
        root.setOnSwipeDown(this::openSearch);
        root.setOnDragListener(this::onDrag);

        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setClipChildren(false);
        content.setClipToPadding(false);

        pager = new PagedView(this);
        pager.setListener(new PagedView.Listener() {
            @Override
            public void onPageScroll(float position) {
                indicator.setPosition(position);
            }

            @Override
            public void onScrollStateChanged(boolean scrolling) {
                indicator.setScrolling(scrolling);
            }
        });
        pager.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> {
            if (b - t != ob - ot) updateRows(b - t);
        });
        content.addView(pager, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        indicator = new PageIndicator(this);
        indicator.setOnClickListener(v -> {
            if (!editing && indicator.isSearchVisible()) openSearch();
        });
        content.addView(indicator, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(36)));

        dock = new Dock(this);
        LinearLayout.LayoutParams dockLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(92));
        dockLp.setMargins(dp(10), dp(4), dp(10), dp(8));
        content.addView(dock, dockLp);

        root.addView(content, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        doneButton = new TextView(this);
        doneButton.setText("Готово");
        doneButton.setTextColor(Color.WHITE);
        doneButton.setTextSize(15);
        doneButton.setTypeface(Ui.font(600));
        doneButton.setBackground(Ui.roundRect(0x38FFFFFF, dp(16)));
        doneButton.setPadding(dp(16), dp(7), dp(16), dp(7));
        doneButton.setVisibility(View.GONE);
        doneButton.setOnClickListener(v -> setEditing(false));
        root.addView(doneButton, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP | Gravity.END));

        search = new SearchOverlay(this, this);
        search.setVisibility(View.GONE);
        root.addView(search, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        root.setOnApplyWindowInsetsListener((v, insets) -> {
            Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            Insets ime = insets.getInsets(WindowInsets.Type.ime());
            content.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            search.setPadding(bars.left, bars.top, bars.right, Math.max(bars.bottom, ime.bottom));
            FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) doneButton.getLayoutParams();
            lp.topMargin = bars.top + dp(8);
            lp.rightMargin = bars.right + dp(16);
            doneButton.setLayoutParams(lp);
            return WindowInsets.CONSUMED;
        });
    }

    private void updateRows(int pagerHeight) {
        int r = LayoutModel.clamp(pagerHeight / dp(CELL_DP), MIN_ROWS, MAX_ROWS);
        if (r != rows) {
            rows = r;
            handler.post(this::rebuild); // не перестраиваем прямо во время layout
        }
    }

    private int pageSize() {
        return COLUMNS * rows;
    }

    private void rebuild() {
        int keepPage = pager.getCurrentPage();
        int ps = pageSize();
        int pages = model.pageCount(ps);

        pager.removeAllViews();
        for (int p = 0; p < pages; p++) {
            CellGrid grid = new CellGrid(this, COLUMNS, rows, CELL_DP);
            grid.setLongClickable(true);
            grid.setOnLongClickListener(v -> {
                // долгое нажатие на пустое место — режим редактирования, как в iOS
                if (!editing) {
                    v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
                    setEditing(true);
                }
                return true;
            });
            for (String key : model.page(p, ps)) {
                AppInfo a = apps.get(key);
                if (a != null) grid.addView(createHomeIcon(a, true));
            }
            pager.addView(grid);
        }
        pager.snapToPage(keepPage, false);
        indicator.setPageCount(pages);
        indicator.setPosition(pager.getCurrentPage());

        dock.removeAllViews();
        for (String key : model.dock) {
            AppInfo a = apps.get(key);
            if (a != null) dock.addView(createHomeIcon(a, false));
        }
    }

    private IconView createHomeIcon(AppInfo app, boolean label) {
        IconView v = new IconView(this, app, label, ICON_DP);
        v.setOnClickListener(x -> launch(v));
        v.setOnLongClickListener(x -> {
            if (editing) startDrag(v);
            else showMenu(v);
            return true;
        });
        v.setOnRemoveListener(this::uninstall);
        v.setEditing(editing);
        return v;
    }

    private void forEachIcon(Consumer<IconView> action) {
        for (int p = 0; p < pager.getChildCount(); p++) {
            ViewGroup grid = (ViewGroup) pager.getChildAt(p);
            for (int i = 0; i < grid.getChildCount(); i++) action.accept((IconView) grid.getChildAt(i));
        }
        for (int i = 0; i < dock.getChildCount(); i++) action.accept((IconView) dock.getChildAt(i));
    }

    // ------------------------------------------------------------------ загрузка приложений

    private void scheduleReload() {
        handler.removeCallbacks(reloadRunnable);
        handler.postDelayed(reloadRunnable, 300);
    }

    private void reloadApps() {
        handler.removeCallbacks(reloadRunnable);
        loader.execute(() -> {
            List<AppInfo> list = repository.loadAll();
            List<String> defaultDock = repository.defaultDock(list);
            handler.post(() -> onAppsLoaded(list, defaultDock));
        });
    }

    private void onAppsLoaded(List<AppInfo> list, List<String> defaultDock) {
        if (isDestroyed()) return;
        if (draggingKey != null) { // не перестраиваем экран посреди перетаскивания
            scheduleReload();
            return;
        }
        apps.clear();
        List<String> keys = new ArrayList<>();
        for (AppInfo a : list) {
            apps.put(a.key, a);
            keys.add(a.key);
        }
        sortedApps = list;
        if (model.reconcile(keys, defaultDock)) store.save(model);
        loaded = true;
        rebuild();
    }

    // ------------------------------------------------------------------ действия

    @Override
    public IconView createSearchIcon(AppInfo app) {
        IconView v = new IconView(this, app, true, ICON_DP);
        v.setOnClickListener(x -> launch(v));
        return v;
    }

    @Override
    public void launch(IconView v) {
        if (editing) return;
        AppInfo a = v.app;
        int[] loc = new int[2];
        v.getLocationOnScreen(loc);
        Rect bounds = new Rect(loc[0] + v.iconLeft(), loc[1] + v.iconTop(),
                loc[0] + v.iconLeft() + v.iconSize(), loc[1] + v.iconTop() + v.iconSize());
        ActivityOptions options = ActivityOptions.makeScaleUpAnimation(v, v.iconLeft(), v.iconTop(),
                v.iconSize(), v.iconSize());
        try {
            launcherApps.startMainActivity(a.component, a.user, bounds, options.toBundle());
        } catch (RuntimeException e) {
            Toast.makeText(this, "Не удалось открыть «" + a.label + "»", Toast.LENGTH_SHORT).show();
        }
        if (searchOpen) closeSearch();
    }

    private void uninstall(IconView v) {
        AppInfo a = v.app;
        if (!a.removable) return;
        Intent intent = new Intent(Intent.ACTION_DELETE, Uri.fromParts("package", a.packageName(), null));
        intent.putExtra(Intent.EXTRA_USER, a.user);
        try {
            startActivity(intent);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Не удалось удалить приложение", Toast.LENGTH_SHORT).show();
        }
    }

    private void showMenu(IconView v) {
        v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
        dismissMenu();
        AppInfo a = v.app;
        boolean dark = Ui.isDark(this);
        int fg = dark ? Color.WHITE : Color.BLACK;
        int bg = dark ? 0xF22C2C2E : 0xF7F9F9F9;
        int separator = dark ? 0x33FFFFFF : 0x22000000;

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setMinimumWidth(dp(230));
        PopupWindow popup = new PopupWindow(box, ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, true);

        addMenuItem(box, popup, "Изменить экран «Домой»", fg, () -> setEditing(true));
        addSeparator(box, separator);
        addMenuItem(box, popup, "О приложении", fg,
                () -> launcherApps.startAppDetailsActivity(a.component, a.user, null, null));
        if (a.removable) {
            addSeparator(box, separator);
            addMenuItem(box, popup, "Удалить приложение", 0xFFFF3B30, () -> uninstall(v));
        }

        popup.setBackgroundDrawable(Ui.roundRect(bg, dp(14)));
        popup.setElevation(dp(16));
        popup.setOutsideTouchable(true);
        popup.showAsDropDown(v, 0, dp(4));
        menu = popup;
    }

    private void addMenuItem(LinearLayout box, PopupWindow popup, String text, int color, Runnable action) {
        TextView item = new TextView(this);
        item.setText(text);
        item.setTextColor(color);
        item.setTextSize(16);
        item.setTypeface(Ui.font(400));
        item.setPadding(dp(16), dp(13), dp(16), dp(13));
        item.setBackground(new RippleDrawable(ColorStateList.valueOf(0x33888888), null,
                new ColorDrawable(Color.WHITE)));
        item.setOnClickListener(x -> {
            popup.dismiss();
            action.run();
        });
        box.addView(item, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private void addSeparator(LinearLayout box, int color) {
        View line = new View(this);
        line.setBackgroundColor(color);
        box.addView(line, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1));
    }

    private void dismissMenu() {
        if (menu != null) {
            menu.dismiss();
            menu = null;
        }
    }

    private void setEditing(boolean on) {
        if (editing == on) return;
        editing = on;
        doneButton.setVisibility(on ? View.VISIBLE : View.GONE);
        indicator.setForceDots(on);
        root.setSwipeEnabled(!on);
        forEachIcon(icon -> icon.setEditing(on));
        if (!on) store.save(model);
        updateBackCallback();
    }

    private void openSearch() {
        if (editing || searchOpen || !loaded) return;
        searchOpen = true;
        // Подсказки при пустом запросе: приложения из дока и с текущей страницы
        List<AppInfo> suggestions = new ArrayList<>();
        List<String> keys = new ArrayList<>(model.dock);
        keys.addAll(model.page(pager.getCurrentPage(), pageSize()));
        for (String k : keys) {
            AppInfo a = apps.get(k);
            if (a != null) suggestions.add(a);
        }
        search.open(sortedApps, suggestions);
        content.animate().alpha(0f).setDuration(180).start();
        root.setSwipeEnabled(false);
        updateBackCallback();
    }

    @Override
    public void closeSearch() {
        if (!searchOpen) return;
        searchOpen = false;
        search.close();
        content.animate().alpha(1f).setDuration(180).start();
        root.setSwipeEnabled(!editing);
        updateBackCallback();
    }

    /** Жест/кнопка «Назад» закрывает поиск или режим редактирования. */
    private void updateBackCallback() {
        boolean need = editing || searchOpen;
        OnBackInvokedDispatcher dispatcher = getOnBackInvokedDispatcher();
        if (need && !backRegistered) {
            dispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, backCallback);
            backRegistered = true;
        } else if (!need && backRegistered) {
            dispatcher.unregisterOnBackInvokedCallback(backCallback);
            backRegistered = false;
        }
    }

    // ------------------------------------------------------------------ перетаскивание

    private void startDrag(IconView v) {
        v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
        draggingKey = v.app.key;
        draggingView = v;
        ClipData data = ClipData.newPlainText("app", v.app.key);
        if (v.startDragAndDrop(data, v.createDragShadow(), v.app.key, 0)) {
            v.setVisibility(View.INVISIBLE);
        } else {
            draggingKey = null;
            draggingView = null;
        }
    }

    private boolean onDrag(View target, DragEvent event) {
        switch (event.getAction()) {
            case DragEvent.ACTION_DRAG_STARTED:
                return draggingKey != null && draggingKey.equals(event.getLocalState());
            case DragEvent.ACTION_DRAG_LOCATION:
                updateEdgeFlip(event.getX());
                return true;
            case DragEvent.ACTION_DROP:
                handleDrop(event.getX(), event.getY());
                return true;
            case DragEvent.ACTION_DRAG_ENDED:
                handler.removeCallbacks(flipRunnable);
                flipDirection = 0;
                if (draggingView != null) draggingView.setVisibility(View.VISIBLE);
                draggingKey = null;
                draggingView = null;
                store.save(model);
                rebuild();
                return true;
            default:
                return true;
        }
    }

    /** Держишь иконку у края экрана — страница перелистывается. */
    private void updateEdgeFlip(float x) {
        int edge = dp(28);
        int dir = x < edge ? -1 : (x > root.getWidth() - edge ? 1 : 0);
        int targetPage = pager.getCurrentPage() + dir;
        if (dir != 0 && targetPage >= 0 && targetPage < pager.getChildCount()) {
            if (flipDirection != dir) {
                flipDirection = dir;
                handler.removeCallbacks(flipRunnable);
                handler.postDelayed(flipRunnable, 600);
            }
        } else {
            flipDirection = 0;
            handler.removeCallbacks(flipRunnable);
        }
    }

    private void handleDrop(float x, float y) {
        String key = draggingKey;
        if (key == null) return;

        Rect dockRect = new Rect();
        dock.getDrawingRect(dockRect);
        root.offsetDescendantRectToMyCoords(dock, dockRect);
        dockRect.inset(0, -dp(12));
        if (dockRect.contains((int) x, (int) y)) {
            model.move(key, true, dock.slotIndexAt(x - dockRect.left));
            return;
        }

        View page = pager.getCurrentPageView();
        if (!(page instanceof CellGrid)) return;
        Rect gridRect = new Rect();
        page.getDrawingRect(gridRect);
        root.offsetDescendantRectToMyCoords(page, gridRect);
        int cell = ((CellGrid) page).cellIndexAt(x - gridRect.left, y - gridRect.top);
        model.move(key, false, pager.getCurrentPage() * pageSize() + cell);
    }

    private int dp(float v) {
        return Ui.dp(this, v);
    }
}
