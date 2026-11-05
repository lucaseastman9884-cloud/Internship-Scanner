// Dark / light theme (P8). A visitor's own choice is kept in this browser under the app's namespaced
// key; without one, site.default_theme from site_config.json decides. Storage may be blocked, so
// every access is wrapped and the site works the same without it.
export const THEME_KEY = "internship-scanner:theme:v1";
export const THEMES = ["dark", "light"];

export function readStoredTheme(storage) {
  try {
    const v = storage && storage.getItem(THEME_KEY);
    return THEMES.includes(v) ? v : null;
  } catch {
    return null;
  }
}

export function storeTheme(storage, theme) {
  if (!THEMES.includes(theme)) return false;
  try {
    storage.setItem(THEME_KEY, theme);
    return true;
  } catch {
    return false;
  }
}

export function pickTheme(stored, siteDefault) {
  if (THEMES.includes(stored)) return stored;
  return THEMES.includes(siteDefault) ? siteDefault : "dark";
}
