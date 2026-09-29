import { Button } from '@astryxdesign/core/Button';
import { Component, type ErrorInfo, type ReactNode } from 'react';
import * as stylex from '@stylexjs/stylex';
import { EmptyView } from '../components/core/panel';
import { ui } from '../components/core/ui.stylex';

export class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Island Finder 界面渲染中断', error, info.componentStack);
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main {...stylex.props(ui.page)}>
        <EmptyView
          title="界面意外中断"
          description="后端任务仍独立运行。重新加载界面后会重连当前状态，不会重复启动任务。"
          action={
            <Button
              label="重新加载界面"
              variant="primary"
              onClick={() => window.location.reload()}
            />
          }
        />
        <pre {...stylex.props(ui.code)}>{this.state.error.message}</pre>
      </main>
    );
  }
}
