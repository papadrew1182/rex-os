import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: "2rem", maxWidth: 500, margin: "4rem auto", textAlign: "center",
          background: "#fff", border: "1px solid #e0e0e0", borderRadius: 8,
        }}>
          <h3 style={{ color: "#c0392b" }}>Something went wrong</h3>
          <p style={{ color: "#666", fontSize: "0.9rem" }}>{this.state.error?.message || "Unexpected error"}</p>
          <button
            onClick={() => { this.setState({ error: null }); window.location.reload(); }}
            style={{
              padding: "0.5rem 1.25rem", background: "#1a1a2e", color: "#fff",
              border: "none", borderRadius: 4, cursor: "pointer", marginTop: "0.5rem",
            }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
