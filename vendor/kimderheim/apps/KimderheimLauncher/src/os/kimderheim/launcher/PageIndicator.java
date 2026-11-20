package os.kimderheim.launcher;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.View;

/**
 * Как в iOS: в покое — кнопка «Поиск», при листании — точки страниц.
 */
final class PageIndicator extends View {
    private final Paint dotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint pillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final SearchGlyph glyph;
    private final RectF pill = new RectF();
    private final String label = "Поиск";
    private final float dotRadius;
    private final float dotSpacing;
    private int count = 1;
    private float position;
    private float dotsAlpha; // 0 = видна кнопка «Поиск», 1 = видны точки
    private boolean scrolling;
    private boolean forceDots;
    private ValueAnimator anim;
    private final Runnable backToSearch = () -> animateDots(0f);

    PageIndicator(Context context) {
        super(context);
        dotRadius = Ui.dp(context, 3.5f);
        dotSpacing = Ui.dp(context, 15);
        pillPaint.setColor(0x38FFFFFF);
        textPaint.setColor(Color.WHITE);
        textPaint.setTextSize(Ui.sp(context, 12));
        textPaint.setTypeface(Ui.font(600));
        glyph = new SearchGlyph(Color.WHITE, Ui.dp(context, 11));
        setContentDescription(label);
    }

    void setPageCount(int count) {
        this.count = Math.max(1, count);
        invalidate();
    }

    void setPosition(float position) {
        this.position = position;
        invalidate();
    }

    void setScrolling(boolean scrolling) {
        this.scrolling = scrolling;
        removeCallbacks(backToSearch);
        if (scrolling) animateDots(1f);
        else if (!forceDots) postDelayed(backToSearch, 900);
    }

    /** В режиме редактирования всегда показываем точки. */
    void setForceDots(boolean force) {
        forceDots = force;
        removeCallbacks(backToSearch);
        animateDots(force || scrolling ? 1f : 0f);
    }

    boolean isSearchVisible() {
        return dotsAlpha < 0.5f;
    }

    private void animateDots(float target) {
        if (anim != null) anim.cancel();
        anim = ValueAnimator.ofFloat(dotsAlpha, target);
        anim.setDuration(200);
        anim.addUpdateListener(a -> {
            dotsAlpha = (float) a.getAnimatedValue();
            invalidate();
        });
        anim.start();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        float cx = getWidth() / 2f;
        float cy = getHeight() / 2f;

        float searchAlpha = 1f - dotsAlpha;
        if (searchAlpha > 0.01f) {
            float textW = textPaint.measureText(label);
            float g = glyph.getIntrinsicWidth();
            float gap = Ui.dp(getContext(), 5);
            float padX = Ui.dp(getContext(), 11);
            float w = padX * 2 + g + gap + textW;
            float h = Ui.dp(getContext(), 26);
            pill.set(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2);
            int a = Math.round(255 * searchAlpha);
            pillPaint.setAlpha(Math.round(0x38 * searchAlpha));
            canvas.drawRoundRect(pill, h / 2, h / 2, pillPaint);
            int gx = Math.round(pill.left + padX);
            int gy = Math.round(cy - g / 2);
            glyph.setBounds(gx, gy, gx + (int) g, gy + (int) g);
            glyph.setAlpha(a);
            glyph.draw(canvas);
            textPaint.setAlpha(a);
            Paint.FontMetrics fm = textPaint.getFontMetrics();
            canvas.drawText(label, pill.left + padX + g + gap, cy - (fm.ascent + fm.descent) / 2, textPaint);
        }

        if (dotsAlpha > 0.01f && count > 1) {
            float total = (count - 1) * dotSpacing;
            for (int i = 0; i < count; i++) {
                float active = Math.max(0f, 1f - Math.abs(position - i));
                float alpha = (0.35f + 0.65f * active) * dotsAlpha;
                dotPaint.setColor(Color.WHITE);
                dotPaint.setAlpha(Math.round(255 * alpha));
                canvas.drawCircle(cx - total / 2 + i * dotSpacing, cy, dotRadius, dotPaint);
            }
        }
    }
}
