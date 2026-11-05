import { useEffect, useLayoutEffect, useState } from 'react';

type Theme = 'light' | 'dark';

const themeStorageKey = 'matchob-theme';

function readTheme(defaultTheme: Theme): Theme {
  try {
    const savedTheme = localStorage.getItem(themeStorageKey);
    return savedTheme === 'light' || savedTheme === 'dark' ? savedTheme : defaultTheme;
  } catch {
    return defaultTheme;
  }
}

export function ThemeToggle({ defaultTheme }: { defaultTheme: Theme }) {
  const [theme, setTheme] = useState<Theme>(() => readTheme(defaultTheme));

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    function syncTheme(event: StorageEvent) {
      if (event.key === themeStorageKey) setTheme(readTheme(defaultTheme));
    }

    window.addEventListener('storage', syncTheme);
    return () => window.removeEventListener('storage', syncTheme);
  }, [defaultTheme]);

  function toggleTheme() {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);

    try {
      localStorage.setItem(themeStorageKey, nextTheme);
    } catch {
      // The theme still changes for this open view if storage is unavailable.
    }
  }

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
    >
      <span aria-hidden="true">{theme === 'light' ? '☾' : '☀'}</span>
      {theme === 'light' ? 'Dark' : 'Light'}
    </button>
  );
}
