package os.kimderheim.launcher;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;

/** Док внизу экрана: до 4 иконок без подписей на полупрозрачной подложке. */
final class Dock extends ViewGroup {
    private final int pad;
    private int slotW;
    private int startX;

    Dock(Context context) {
        super(context);
        pad = Ui.dp(context, 8);
        setBackground(Ui.roundRect(0x38FFFFFF, Ui.dp(context, 32)));
        setClipChildren(false);
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int w = MeasureSpec.getSize(widthMeasureSpec);
        int h = MeasureSpec.getSize(heightMeasureSpec);
        slotW = Math.max(1, (w - 2 * pad) / LayoutModel.DOCK_MAX);
        int cw = MeasureSpec.makeMeasureSpec(slotW, MeasureSpec.EXACTLY);
        int ch = MeasureSpec.makeMeasureSpec(h, MeasureSpec.AT_MOST);
        for (int i = 0; i < getChildCount(); i++) getChildAt(i).measure(cw, ch);
        setMeasuredDimension(w, h);
    }

    @Override
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        int n = getChildCount();
        int w = r - l;
        int h = b - t;
        startX = (w - n * slotW) / 2; // как в iOS: иконки по центру
        for (int i = 0; i < n; i++) {
            View c = getChildAt(i);
            int x = startX + i * slotW;
            // сдвигаем вверх на верхний отступ иконки, чтобы она была ровно по центру подложки
            int iconTop = c instanceof IconView ? ((IconView) c).iconTop() : 0;
            int y = (h - c.getMeasuredHeight() - iconTop) / 2;
            c.layout(x, y, x + slotW, y + c.getMeasuredHeight());
        }
    }

    /** Позиция в доке под точкой x (координаты дока). */
    int slotIndexAt(float x) {
        return LayoutModel.clamp((int) ((x - startX) / slotW), 0, getChildCount());
    }
}
