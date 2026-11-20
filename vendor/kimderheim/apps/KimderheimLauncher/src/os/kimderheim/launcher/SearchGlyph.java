package os.kimderheim.launcher;

import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;

/** Значок лупы, нарисованный кодом (без картинок). */
final class SearchGlyph extends Drawable {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final int size;

    SearchGlyph(int color, int sizePx) {
        size = sizePx;
        paint.setColor(color);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeCap(Paint.Cap.ROUND);
        paint.setStrokeWidth(Math.max(2f, sizePx * 0.13f));
        setBounds(0, 0, sizePx, sizePx);
    }

    @Override
    public void draw(Canvas canvas) {
        Rect b = getBounds();
        float s = Math.min(b.width(), b.height());
        float r = s * 0.32f;
        float cx = b.left + s * 0.42f;
        float cy = b.top + s * 0.42f;
        canvas.drawCircle(cx, cy, r, paint);
        float d = r * 0.72f;
        canvas.drawLine(cx + d, cy + d, b.left + s * 0.9f, b.top + s * 0.9f, paint);
    }

    @Override
    public int getIntrinsicWidth() {
        return size;
    }

    @Override
    public int getIntrinsicHeight() {
        return size;
    }

    @Override
    public void setAlpha(int alpha) {
        paint.setAlpha(alpha);
    }

    @Override
    public void setColorFilter(ColorFilter colorFilter) {
        paint.setColorFilter(colorFilter);
    }

    @Override
    public int getOpacity() {
        return PixelFormat.TRANSLUCENT;
    }
}
