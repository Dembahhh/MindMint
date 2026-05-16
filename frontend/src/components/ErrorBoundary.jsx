import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-base flex items-center justify-center text-center px-6">
          <div>
            <div className="text-5xl mb-4" aria-hidden="true">&#9888;&#65039;</div>
            <h1 className="text-xl font-bold text-ink-primary mb-2">Something went wrong</h1>
            <p className="text-ink-secondary text-sm mb-6">Please refresh the page.</p>
            <button
              onClick={() => window.location.reload()}
              className="bg-accent hover:bg-accent-hover text-ink-primary px-6 py-2 rounded-lg text-sm transition-colors"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}