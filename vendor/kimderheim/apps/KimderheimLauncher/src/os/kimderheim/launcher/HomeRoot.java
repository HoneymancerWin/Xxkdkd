package os.kimderheim.launcher;

import android.content.Context;
import android.view.MotionEvent;
import android.view.ViewConfiguration;
import android.widget.FrameLayout;

/** Корневой контейнер: ловит свайп вниз по рабочему столу, чтобы открыть поиск (как в iOS). */
final class HomeRoot extends FrameLayout {
    private final int touchSlop;
    private Runnable onSwipeDown;
    private boolean swipeEnabled = true;
    private boolean tracking;
    private float downX;
    private float downY;

    HomeRoot(Context context) {
        super(context);
        touchSlop = ViewConfiguration.get(context).getScaledTouchSlop();
    }

    void setOnSwipeDown(Runnable r) {
        onSwipeDown = r;
    }

    void setSwipeEnabled(boolean enabled) {
        swipeEnabled = enabled;
    }

    @Override
    public boolean onInterceptTouchEvent(MotionEvent ev) {
        return detectSwipe(ev);
    }

    @Override
    public boolean onTouchEvent(MotionEvent ev) {
        // Сюда попадают касания пустых мест (например, подложки дока)
        detectSwipe(ev);
        return true;
    }

    /** @return true, если распознан свайп вниз */
    private boolean detectSwipe(MotionEvent ev) {
        if (!swipeEnabled || onSwipeDown == null) return false;
        switch (ev.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = ev.getX();
                downY = ev.getY();
                tracking = true;
                return false;
            case MotionEvent.ACTION_MOVE:
                if (!tracking) return false;
                float dx = ev.getX() - downX;
                float dy = ev.getY() - downY;
                if (dy > touchSlop * 2 && dy > Math.abs(dx) * 1.5f) {
                    tracking = false;
                    post(onSwipeDown);
                    return true;
                }
                if (Math.abs(dx) > touchSlop || dy < -touchSlop) tracking = false;
                return false;
            default:
                tracking = false;
                return false;
        }
    }
}
