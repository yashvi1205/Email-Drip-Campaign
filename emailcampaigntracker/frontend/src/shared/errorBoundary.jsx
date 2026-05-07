import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    const { hasError, error } = this.state;
    if (!hasError) return this.props.children;

    return (
      <div style={{ padding: '2rem', color: '#f87171' }}>
        <h2>Something went wrong</h2>
        <pre style={{ whiteSpace: 'pre-wrap' }}>
          {error?.message || String(error)}
        </pre>
      </div>
    );
  }
}

