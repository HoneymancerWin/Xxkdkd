package os.kimderheim.launcher;

import android.content.Context;
import android.view.MotionEvent;
import android.view.VelocityTracker;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.view.animation.DecelerateInterpolator;
import android.widget.OverScroller;

/** Горизонтальное листание страниц рабочего стола с «прилипанием» к странице. */
final class PagedView extends ViewGroup {
    interface Listener {
        /** position: 0 = первая страница, 1.5 = между второй и третьей. */
        void onPageScroll(float position);

        void onScrollStateChanged(boolean scrolling);
    }

    private final OverScroller scroller;
    private final int touchSlop;
    private final int minFling;
    private VelocityTracker velocity;
    private Listener listener;
    private float downX;
    private float downY;
    private float lastX;
    private boolean dragging;
    private boolean settling;
    private int current;

    PagedView(Context context) {
        super(context);
        scroller = new OverScroller(context, new DecelerateInterpolator(1.6f));
        ViewConfiguration vc = ViewConfiguration.get(context);
        touchSlop = vc.getScaledTouchSlop();
        minFling = vc.getScaledMinimumFlingVelocity() * 4;
        setClipChildren(false);
    }

    void setListener(Listener l) {
        listener = l;
    }

    int getCurrentPage() {
        return current;
    }

    View getCurrentPageView() {
        return getChildAt(current);
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int w = MeasureSpec.getSize(widthMeasureSpec);
        int h = MeasureSpec.getSize(heightMeasureSpec);
        int cw = MeasureSpec.makeMeasureSpec(w, MeasureSpec.EXACTLY);
        int ch = MeasureSpec.makeMeasureSpec(h, MeasureSpec.EXACTLY);
        for (int i = 0; i < getChildCount(); i++) getChildAt(i).measure(cw, ch);
        setMeasuredDimension(w, h);
    }

    @Override
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        int w = r - l;
        int h = b - t;
        for (int i = 0; i < getChildCount(); i++) {
            getChildAt(i).layout(i * w, 0, (i + 1) * w, h);
        }
        current = LayoutModel.clamp(current, 0, Math.max(0, getChildCount() - 1));
        if (scroller.isFinished() && !dragging) scrollTo(current * w, 0);
    }

    void snapToPage(int page, boolean animate) {
        int w = getWidth();
        current = LayoutModel.clamp(page, 0, Math.max(0, getChildCount() - 1));
        int dx = current * w - getScrollX();
        if (!animate || w == 0) {
            scroller.abortAnimation();
            scrollTo(current * w, 0);
            return;
        }
        int duration = Math.min(450, 220 + Math.abs(dx) * 200 / Math.max(1, w));
        scroller.startScroll(getScrollX(), 0, dx, 0, duration);
        settling = true;
        postInvalidateOnAnimation();
    }

    @Override
    public void computeScroll() {
        if (scroller.computeScrollOffset()) {
            scrollTo(scroller.getCurrX(), 0);
            postInvalidateOnAnimation();
        } else if (settling) {
            settling = false;
            if (listener != null) listener.onScrollStateChanged(false);
        }
    }

    @Override
    protected void onScrollChanged(int l, int t, int oldl, int oldt) {
        super.onScrollChanged(l, t, oldl, oldt);
        if (listener != null && getWidth() > 0) listener.onPageScroll(l / (float) getWidth());
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent ev) {
        if (ev.getActionMasked() == MotionEvent.ACTION_DOWN) {
            if (velocity == null) velocity = VelocityTracker.obtain();
            velocity.clear();
        }
        if (velocity != null) velocity.addMovement(ev);
        return super.dispatchTouchEvent(ev);
    }

    @Override
    public boolean onInterceptTouchEvent(MotionEvent ev) {
        switch (ev.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = lastX = ev.getX();
                downY = ev.getY();
                if (!scroller.isFinished()) {
                    // палец поймал анимацию — продолжаем листать
                    scroller.abortAnimation();
                    startDrag();
                }
                return dragging;
            case MotionEvent.ACTION_MOVE:
                if (!dragging) maybeStartDrag(ev);
                return dragging;
            default:
                return dragging;
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent ev) {
        switch (ev.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = lastX = ev.getX();
                downY = ev.getY();
                return true;
            case MotionEvent.ACTION_MOVE:
                if (!dragging) maybeStartDrag(ev);
                if (dragging) {
                    float dx = lastX - ev.getX();
                    lastX = ev.getX();
                    int max = Math.max(0, (getChildCount() - 1) * getWidth());
                    float next = getScrollX() + dx;
                    if (next < 0 || next > max) dx *= 0.35f; // «резинка» на краях
                    scrollBy(Math.round(dx), 0);
                }
                return true;
            case MotionEvent.ACTION_UP:
                if (dragging) {
                    velocity.computeCurrentVelocity(1000);
                    float v = velocity.getXVelocity();
                    float pos = getScrollX() / (float) Math.max(1, getWidth());
                    int target;
                    if (v < -minFling) target = (int) Math.floor(pos) + 1;
                    else if (v > minFling) target = (int) Math.ceil(pos) - 1;
                    else target = Math.round(pos);
                    dragging = false;
                    snapToPage(target, true);
                }
                return true;
            case MotionEvent.ACTION_CANCEL:
                if (dragging) {
                    dragging = false;
                    snapToPage(current, true);
                }
                return true;
            default:
                return true;
        }
    }

    private void maybeStartDrag(MotionEvent ev) {
        float dx = ev.getX() - downX;
        float dy = ev.getY() - downY;
        if (Math.abs(dx) > touchSlop && Math.abs(dx) > Math.abs(dy)) {
            lastX = ev.getX();
            startDrag();
        }
    }

    private void startDrag() {
        dragging = true;
        ViewParent parent = getParent();
        if (parent != null) parent.requestDisallowInterceptTouchEvent(true);
        cancelLongPress();
        for (int i = 0; i < getChildCount(); i++) getChildAt(i).cancelLongPress();
        if (listener != null) listener.onScrollStateChanged(true);
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        if (velocity != null) {
            velocity.recycle();
            velocity = null;
        }
    }
}
