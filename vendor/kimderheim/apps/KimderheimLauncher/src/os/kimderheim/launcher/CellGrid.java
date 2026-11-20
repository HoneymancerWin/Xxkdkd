package os.kimderheim.launcher;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;

/**
 * Сетка иконок: columns x rows. Если rows <= 0 — высота растёт по содержимому
 * (используется в результатах поиска).
 */
final class CellGrid extends ViewGroup {
    private final int columns;
    private final int rows;
    private final int fixedCellHeight;
    private final int padH;
    private final int padTop;
    private int cellW;
    private int cellH;

    CellGrid(Context context, int columns, int rows, int fixedCellHeightDp) {
        super(context);
        this.columns = columns;
        this.rows = rows;
        this.fixedCellHeight = Ui.dp(context, fixedCellHeightDp);
        padH = Ui.dp(context, 12);
        padTop = Ui.dp(context, 8);
        setClipChildren(false);
        setClipToPadding(false);
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int w = MeasureSpec.getSize(widthMeasureSpec);
        cellW = Math.max(1, (w - 2 * padH) / columns);
        int h;
        if (rows > 0) {
            h = MeasureSpec.getSize(heightMeasureSpec);
            cellH = Math.max(1, (h - padTop) / rows);
        } else {
            cellH = fixedCellHeight;
            int rowCount = (getChildCount() + columns - 1) / columns;
            h = padTop + rowCount * cellH;
        }
        int childW = MeasureSpec.makeMeasureSpec(cellW, MeasureSpec.EXACTLY);
        int childH = MeasureSpec.makeMeasureSpec(cellH, MeasureSpec.AT_MOST);
        for (int i = 0; i < getChildCount(); i++) {
            getChildAt(i).measure(childW, childH);
        }
        setMeasuredDimension(w, h);
    }

    @Override
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        for (int i = 0; i < getChildCount(); i++) {
            View child = getChildAt(i);
            int col = i % columns;
            int row = i / columns;
            int x = padH + col * cellW;
            int y = padTop + row * cellH;
            child.layout(x, y, x + cellW, y + child.getMeasuredHeight());
        }
    }

    /** Номер ячейки под точкой (x, y) в координатах этой сетки. */
    int cellIndexAt(float x, float y) {
        int col = LayoutModel.clamp((int) ((x - padH) / cellW), 0, columns - 1);
        int maxRow = rows > 0 ? rows - 1 : Integer.MAX_VALUE;
        int row = LayoutModel.clamp((int) ((y - padTop) / cellH), 0, maxRow);
        return row * columns + col;
    }
}
