import type { PropsWithChildren } from 'react';
import { ThemeToggle } from './ThemeToggle';

type AppLayoutProps = PropsWithChildren<{
  defaultTheme: 'light' | 'dark';
  surface?: 'popup' | 'sidepanel';
}>;

export function AppLayout({ children, defaultTheme, surface = 'popup' }: AppLayoutProps) {
  return (
    <main className={surface === 'sidepanel' ? 'popup sidepanel' : 'popup'}>
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">M</span>
        <span>Matchob</span>
        <ThemeToggle defaultTheme={defaultTheme} />
      </header>
      {children}
    </main>
  );
}
