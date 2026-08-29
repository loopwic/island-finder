import { Button } from '@heroui/react';
import { RefreshCw, TriangleAlert } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';

type AppErrorBoundaryState = {
  error: Error | null;
};

export class AppErrorBoundary extends Component<{ children: ReactNode }, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Island Finder 界面渲染中断', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="bg-background text-foreground grid min-h-screen place-items-center p-6">
        <section className="border-border bg-surface w-full max-w-md rounded-3xl border p-6 shadow-sm">
          <div className="bg-danger-soft text-danger mb-5 grid size-11 place-items-center rounded-2xl">
            <TriangleAlert aria-hidden="true" size={21} />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">界面意外中断</h1>
          <p className="text-muted mt-2 text-sm leading-6">
            后端和选岛进程不会因此被直接强杀。重新加载界面后会自动重连当前运行状态。
          </p>
          <p className="bg-surface-secondary text-muted mt-4 max-h-28 overflow-auto rounded-2xl px-3 py-2 font-mono text-xs">
            {this.state.error.message || '未知界面错误'}
          </p>
          <Button className="mt-5" variant="primary" onPress={() => window.location.reload()}>
            <RefreshCw aria-hidden="true" size={17} />
            重新加载界面
          </Button>
        </section>
      </main>
    );
  }
}
