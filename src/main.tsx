import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  RouterProvider,
} from '@tanstack/react-router';
import { ConsoleProvider } from './app/console-context';
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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
