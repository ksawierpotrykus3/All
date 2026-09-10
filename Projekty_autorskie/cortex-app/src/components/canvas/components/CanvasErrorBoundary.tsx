import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class CanvasErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[CanvasErrorBoundary] Błąd wyrenderowania elementu płótna:', error, errorInfo);
  }

  public handleReset = (): void => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="absolute inset-4 z-50 flex items-center justify-center pointer-events-auto">
          <div className="bg-[#1a1414] border border-[#ff5555]/50 rounded-2xl p-6 max-w-md shadow-2xl text-center space-y-4">
            <div className="w-12 h-12 mx-auto rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400 text-xl font-bold">
              ✕
            </div>
            <div>
              <h3 className="text-lg font-bold text-white mb-1">
                {this.props.fallbackTitle || 'Wystąpił błąd widoku'}
              </h3>
              <p className="text-xs text-neutral-400 font-mono break-words line-clamp-3">
                {this.state.error?.message || 'Nieznany błąd renderowania'}
              </p>
            </div>
            <button
              onClick={this.handleReset}
              className="px-4 py-2 bg-[#ff5555]/20 hover:bg-[#ff5555]/30 border border-[#ff5555]/40 text-red-200 text-sm font-semibold rounded-xl transition-all"
            >
              Odśwież element
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
