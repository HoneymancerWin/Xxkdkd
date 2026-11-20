package os.kimderheim.launcher;

import android.content.Context;
import android.graphics.Color;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Поиск приложений поверх рабочего стола (открывается свайпом вниз или кнопкой «Поиск»). */
final class SearchOverlay extends FrameLayout {
    interface Host {
        IconView createSearchIcon(AppInfo app);

        void launch(IconView view);

        void closeSearch();
    }

    private static final int SUGGESTIONS = 8;

    private final Host host;
    private final EditText field;
    private final CellGrid results;
    private final TextView empty;
    private List<AppInfo> all = new ArrayList<>();
    private List<AppInfo> suggestions = new ArrayList<>();
    private final List<AppInfo> shown = new ArrayList<>();

    SearchOverlay(Context context, Host host) {
        super(context);
        this.host = host;
        setBackgroundColor(0x99000000);
        setClickable(true); // не пропускаем касания на рабочий стол

        LinearLayout column = new LinearLayout(context);
        column.setOrientation(LinearLayout.VERTICAL);
        addView(column, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));

        // Строка поиска + «Отменить»
        LinearLayout bar = new LinearLayout(context);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        int p = Ui.dp(context, 16);
        bar.setPadding(p, Ui.dp(context, 12), p, Ui.dp(context, 8));

        field = new EditText(context);
        field.setSingleLine(true);
        field.setHint("Поиск");
        field.setHintTextColor(0x99FFFFFF);
        field.setTextColor(Color.WHITE);
        field.setTextSize(17);
        field.setTypeface(Ui.font(400));
        field.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        field.setImeOptions(EditorInfo.IME_ACTION_GO);
        field.setBackground(Ui.roundRect(0x33FFFFFF, Ui.dp(context, 12)));
        field.setPadding(Ui.dp(context, 10), Ui.dp(context, 9), Ui.dp(context, 10), Ui.dp(context, 9));
        field.setCompoundDrawablePadding(Ui.dp(context, 8));
        field.setCompoundDrawablesRelative(new SearchGlyph(0x99FFFFFF, Ui.dp(context, 16)), null, null, null);
        bar.addView(field, new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f));

        TextView cancel = new TextView(context);
        cancel.setText("Отменить");
        cancel.setTextColor(Color.WHITE);
        cancel.setTextSize(16);
        cancel.setTypeface(Ui.font(500));
        cancel.setPadding(Ui.dp(context, 14), Ui.dp(context, 8), 0, Ui.dp(context, 8));
        cancel.setOnClickListener(v -> host.closeSearch());
        bar.addView(cancel);
        column.addView(bar);

        // Результаты
        ScrollView scroll = new ScrollView(context);
        scroll.setClipToPadding(false);
        results = new CellGrid(context, 4, 0, 100);
        scroll.addView(results, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
        column.addView(scroll, new LinearLayout.LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f));

        empty = new TextView(context);
        empty.setText("Ничего не найдено");
        empty.setTextColor(0xB3FFFFFF);
        empty.setTextSize(15);
        empty.setGravity(Gravity.CENTER);
        empty.setVisibility(GONE);
        LayoutParams lp = new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT);
        lp.topMargin = Ui.dp(context, 120);
        addView(empty, lp);

        field.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {}

            @Override
            public void afterTextChanged(Editable s) {
                filter(s.toString());
            }
        });
        field.setOnEditorActionListener((v, actionId, event) -> {
            boolean go = actionId == EditorInfo.IME_ACTION_GO
                    || (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER);
            if (go && results.getChildCount() > 0) {
                host.launch((IconView) results.getChildAt(0));
                return true;
            }
            return false;
        });
    }

    boolean isOpen() {
        return getVisibility() == VISIBLE;
    }

    void open(List<AppInfo> apps, List<AppInfo> suggestions) {
        this.all = apps;
        this.suggestions = suggestions;
        field.setText("");
        filter("");
        setVisibility(VISIBLE);
        setAlpha(0f);
        animate().alpha(1f).setDuration(180).start();
        field.requestFocus();
        postDelayed(() -> {
            InputMethodManager imm = getContext().getSystemService(InputMethodManager.class);
            if (imm != null) imm.showSoftInput(field, InputMethodManager.SHOW_IMPLICIT);
        }, 120);
    }

    void close() {
        InputMethodManager imm = getContext().getSystemService(InputMethodManager.class);
        if (imm != null) imm.hideSoftInputFromWindow(field.getWindowToken(), 0);
        field.clearFocus();
        animate().alpha(0f).setDuration(150).withEndAction(() -> setVisibility(GONE)).start();
    }

    private void filter(String query) {
        String q = normalize(query.trim());
        shown.clear();
        if (q.isEmpty()) {
            for (int i = 0; i < Math.min(SUGGESTIONS, suggestions.size()); i++) shown.add(suggestions.get(i));
        } else {
            // сначала названия, которые начинаются с запроса, потом — содержащие его
            List<AppInfo> contains = new ArrayList<>();
            for (AppInfo a : all) {
                String label = normalize(a.label);
                if (label.startsWith(q)) shown.add(a);
                else if (label.contains(q)) contains.add(a);
            }
            shown.addAll(contains);
        }
        results.removeAllViews();
        for (AppInfo a : shown) results.addView(host.createSearchIcon(a));
        empty.setVisibility(shown.isEmpty() && !q.isEmpty() ? VISIBLE : GONE);
    }

    private static String normalize(String s) {
        return s.toLowerCase(Locale.ROOT).replace('ё', 'е');
    }
}
