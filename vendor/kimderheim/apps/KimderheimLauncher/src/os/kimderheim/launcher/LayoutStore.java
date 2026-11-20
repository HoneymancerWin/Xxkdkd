package os.kimderheim.launcher;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.List;

/** Сохраняет расположение иконок между перезапусками. */
final class LayoutStore {
    private static final String PREFS = "layout";
    private static final String KEY = "layout_v1";

    private final SharedPreferences prefs;

    LayoutStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    void load(LayoutModel model) {
        model.dock.clear();
        model.apps.clear();
        String raw = prefs.getString(KEY, null);
        if (raw == null) return;
        try {
            JSONObject o = new JSONObject(raw);
            read(o.optJSONArray("dock"), model.dock);
            read(o.optJSONArray("apps"), model.apps);
        } catch (JSONException e) {
            model.dock.clear();
            model.apps.clear();
        }
    }

    void save(LayoutModel model) {
        try {
            JSONObject o = new JSONObject();
            o.put("dock", new JSONArray(model.dock));
            o.put("apps", new JSONArray(model.apps));
            prefs.edit().putString(KEY, o.toString()).apply();
        } catch (JSONException ignored) {
            // не может произойти для списка строк
        }
    }

    private static void read(JSONArray array, List<String> out) {
        if (array == null) return;
        for (int i = 0; i < array.length(); i++) {
            String s = array.optString(i, null);
            if (s != null) out.add(s);
        }
    }
}
