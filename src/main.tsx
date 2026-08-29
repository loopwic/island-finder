import { StrictMode, useEffect, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  RouterProvider,
} from '@tanstack/react-router';
import { ConsoleProvider } from './app/console-context';
import { AppErrorBoundary } from './app/app-error-boundary';
import { RootLayout } from './app/root-layout';
import './styles.css';

const rootRoute = createRootRoute({
  component: () => (
    <ConsoleProvider>
      <RootLayout />
    </ConsoleProvider>
  ),
});
const workbenchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: lazyRouteComponent(() => import('./routes/workbench-page'), 'WorkbenchPage'),
});
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: lazyRouteComponent(() => import('./routes/settings-page'), 'SettingsPage'),
});
const auditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/audit',
  component: lazyRouteComponent(() => import('./routes/audit-page'), 'AuditPage'),
});

const routeTree = rootRoute.addChildren([workbenchRoute, auditRoute, settingsRoute]);
const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

function DesktopReloadBoundary({ children }: { children: ReactNode }) {
  useEffect(() => {
    const reloadWithShortcut = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'r') return;
      event.preventDefault();
      window.location.reload();
    };
    window.addEventListener('keydown', reloadWithShortcut);
    return () => window.removeEventListener('keydown', reloadWithShortcut);
  }, []);

  return children;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DesktopReloadBoundary>
      <AppErrorBoundary>
        <RouterProvider router={router} />
      </AppErrorBoundary>
    </DesktopReloadBoundary>
  </StrictMode>,
);
