package os.kimderheim.launcher;

import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Point;
import android.graphics.drawable.Drawable;
import android.text.TextPaint;
import android.text.TextUtils;
import android.view.MotionEvent;
import android.view.View;

import java.util.Random;

/**
 * Иконка приложения с подписью.
 * В режиме редактирования «покачивается» и показывает кнопку «−» для удаления.
 */
final class IconView extends View {
    interface OnRemoveListener {
        void onRemove(IconView view);
    }

    private static final Random RANDOM = new Random();

    final AppInfo app;
    private final boolean showLabel;
    private final int iconSize;
    private final int topInset;
    private final int labelGap;
    private final TextPaint textPaint = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint badgePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint minusPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float badgeRadius;
    private CharSequence ellipsized = "";
    private boolean editing;
    private boolean downOnBadge;
    private ObjectAnimator jiggle;
    private OnRemoveListener onRemoveListener;

    IconView(Context context, AppInfo app, boolean showLabel, int iconSizeDp) {
        super(context);
        this.app = app;
        this.showLabel = showLabel;
        iconSize = Ui.dp(context, iconSizeDp);
        topInset = Ui.dp(context, 8);
        labelGap = Ui.dp(context, 6);
        badgeRadius = Ui.dp(context, 11);

        textPaint.setColor(Color.WHITE);
        textPaint.setTextSize(Ui.sp(context, 12));
        textPaint.setTypeface(Ui.font(500));
        textPaint.setTextAlign(Paint.Align.CENTER);
        textPaint.setShadowLayer(Ui.dp(context, 3), 0, Ui.dp(context, 1), 0x66000000);

        badgePaint.setColor(0xF0E5E5EA);
        minusPaint.setColor(0xFF3A3A3C);
        minusPaint.setStrokeWidth(Ui.dp(context, 2.5f));
        minusPaint.setStrokeCap(Paint.Cap.ROUND);

        setContentDescription(app.label);
        setFocusable(true);
        setClickable(true);
        setLongClickable(true);
    }

    void setOnRemoveListener(OnRemoveListener l) {
        onRemoveListener = l;
    }

    int iconSize() {
        return iconSize;
    }

    int iconLeft() {
        return (getWidth() - iconSize) / 2;
    }

    int iconTop() {
        return topInset;
    }

    void setEditing(boolean editing) {
        if (this.editing == editing) return;
        this.editing = editing;
        if (editing) {
            setPivotX(getWidth() / 2f);
            setPivotY(topInset + iconSize / 2f);
            jiggle = ObjectAnimator.ofFloat(this, View.ROTATION, -1.6f, 1.6f);
            jiggle.setDuration(120 + RANDOM.nextInt(40));
            jiggle.setRepeatMode(ValueAnimator.REVERSE);
            jiggle.setRepeatCount(ValueAnimator.INFINITE);
            jiggle.setCurrentPlayTime(RANDOM.nextInt(120));
            jiggle.start();
        } else {
            if (jiggle != null) jiggle.cancel();
            jiggle = null;
            setRotation(0);
        }
        invalidate();
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int w = MeasureSpec.getSize(widthMeasureSpec);
        if (MeasureSpec.getMode(widthMeasureSpec) == MeasureSpec.UNSPECIFIED) {
            w = iconSize + Ui.dp(getContext(), 24);
        }
        int h = topInset + iconSize;
        if (showLabel) {
            Paint.FontMetricsInt fm = textPaint.getFontMetricsInt();
            h += labelGap + (fm.descent - fm.ascent) + Ui.dp(getContext(), 2);
        }
        setMeasuredDimension(w, h);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        ellipsized = TextUtils.ellipsize(app.label, textPaint, w - Ui.dp(getContext(), 4),
                TextUtils.TruncateAt.END);
        setPivotX(w / 2f);
        setPivotY(topInset + iconSize / 2f);
    }

    @Override
    protected void drawableStateChanged() {
        super.drawableStateChanged();
        invalidate(); // затемнение при нажатии
    }

    @Override
    protected void onDraw(Canvas canvas) {
        int left = iconLeft();
        Drawable icon = app.icon;
        icon.setBounds(left, topInset, left + iconSize, topInset + iconSize);
        icon.setAlpha(isPressed() && !editing ? 150 : 255);
        icon.draw(canvas);
        icon.setAlpha(255);

        if (showLabel) {
            Paint.FontMetricsInt fm = textPaint.getFontMetricsInt();
            float baseline = topInset + iconSize + labelGap - fm.ascent;
            canvas.drawText(ellipsized, 0, ellipsized.length(), getWidth() / 2f, baseline, textPaint);
        }

        if (editing && app.removable) {
            float cx = badgeCenterX();
            float cy = badgeCenterY();
            canvas.drawCircle(cx, cy, badgeRadius, badgePaint);
            float half = badgeRadius * 0.45f;
            canvas.drawLine(cx - half, cy, cx + half, cy, minusPaint);
        }
    }

    private float badgeCenterX() {
        return iconLeft() + badgeRadius * 0.35f;
    }

    private float badgeCenterY() {
        return topInset + badgeRadius * 0.35f;
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (editing && app.removable) {
            float dx = event.getX() - badgeCenterX();
            float dy = event.getY() - badgeCenterY();
            boolean onBadge = dx * dx + dy * dy <= (badgeRadius * 1.8f) * (badgeRadius * 1.8f);
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    downOnBadge = onBadge;
                    if (onBadge) return true;
                    break;
                case MotionEvent.ACTION_UP:
                    if (downOnBadge) {
                        downOnBadge = false;
                        if (onBadge && onRemoveListener != null) onRemoveListener.onRemove(this);
                        return true;
                    }
                    break;
                case MotionEvent.ACTION_CANCEL:
                    downOnBadge = false;
                    break;
                default:
                    if (downOnBadge) return true;
            }
        }
        return super.onTouchEvent(event);
    }

    /** Тень при перетаскивании — только сама иконка, чуть крупнее. */
    View.DragShadowBuilder createDragShadow() {
        final int size = Math.round(iconSize * 1.1f);
        return new View.DragShadowBuilder(this) {
            @Override
            public void onProvideShadowMetrics(Point outSize, Point outTouch) {
                outSize.set(size, size);
                outTouch.set(size / 2, size / 2);
            }

            @Override
            public void onDrawShadow(Canvas canvas) {
                app.icon.setBounds(0, 0, size, size);
                app.icon.draw(canvas);
            }
        };
    }
}
