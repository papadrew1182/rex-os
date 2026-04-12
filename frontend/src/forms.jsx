/**
 * Shared write-flow components.
 *
 * Used by every operational page that supports create/edit. Provides:
 *   - FormDrawer: slide-in panel with title, body, save/cancel/reset
 *   - Field: labeled input with error display
 *   - TextArea, Select, Checkbox, NumberField, DateField helpers
 *   - useFormState: dirty tracking, change handler, reset
 *   - WriteButton: permission-aware action button
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Spinner, Flash } from "./ui";
import { usePermissions } from "./permissions";

// ─────────────────────────────────────────────────────────────────────────
// useFormState — minimal form state with dirty tracking
// ─────────────────────────────────────────────────────────────────────────

export function useFormState(initial) {
  const [values, setValues] = useState(initial || {});
  const [dirty, setDirty] = useState(false);
  const initialRef = useRef(initial || {});

  // Reset internal state if a new initial object is passed (e.g. switching from create to edit)
  useEffect(() => {
    setValues(initial || {});
    initialRef.current = initial || {};
    setDirty(false);
  }, [initial]);

  const setField = useCallback((name, value) => {
    setValues((v) => ({ ...v, [name]: value }));
    setDirty(true);
  }, []);

  const reset = useCallback(() => {
    setValues(initialRef.current || {});
    setDirty(false);
  }, []);

  const setAll = useCallback((next) => {
    setValues(next || {});
    initialRef.current = next || {};
    setDirty(false);
  }, []);

  return { values, setField, reset, setAll, dirty };
}

// ─────────────────────────────────────────────────────────────────────────
// Form field primitives
// ─────────────────────────────────────────────────────────────────────────

export function Field({ label, name, value, onChange, type = "text", error, required, placeholder, autoFocus }) {
  return (
    <div className="rex-form-group">
      <label htmlFor={name}>
        {label}
        {required && <span style={{ color: "var(--rex-red)", marginLeft: 4 }}>*</span>}
      </label>
      <input
        id={name}
        type={type}
        className="rex-input"
        value={value ?? ""}
        onChange={(e) => onChange(name, e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
      />
      {error && <span style={{ fontSize: 11, color: "var(--rex-red)" }}>{error}</span>}
    </div>
  );
}

export function NumberField({ label, name, value, onChange, error, required, step = "any", placeholder }) {
  return (
    <div className="rex-form-group">
      <label htmlFor={name}>
        {label}
        {required && <span style={{ color: "var(--rex-red)", marginLeft: 4 }}>*</span>}
      </label>
      <input
        id={name}
        type="number"
        step={step}
        className="rex-input"
        value={value ?? ""}
        onChange={(e) => onChange(name, e.target.value === "" ? null : Number(e.target.value))}
        placeholder={placeholder}
      />
      {error && <span style={{ fontSize: 11, color: "var(--rex-red)" }}>{error}</span>}
    </div>
  );
}

export function DateField({ label, name, value, onChange, error, required }) {
  // Accept ISO date strings or Date — coerce to YYYY-MM-DD
  const v = value ? (typeof value === "string" ? value.slice(0, 10) : new Date(value).toISOString().slice(0, 10)) : "";
  return (
    <div className="rex-form-group">
      <label htmlFor={name}>
        {label}
        {required && <span style={{ color: "var(--rex-red)", marginLeft: 4 }}>*</span>}
      </label>
      <input
        id={name}
        type="date"
        className="rex-input"
        value={v}
        onChange={(e) => onChange(name, e.target.value || null)}
      />
      {error && <span style={{ fontSize: 11, color: "var(--rex-red)" }}>{error}</span>}
    </div>
  );
}

export function TimeField({ label, name, value, onChange, error }) {
  const v = value ? (typeof value === "string" ? value.slice(0, 5) : "") : "";
  return (
    <div className="rex-form-group">
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        type="time"
        className="rex-input"
        value={v}
        onChange={(e) => onChange(name, e.target.value || null)}
      />
      {error && <span style={{ fontSize: 11, color: "var(--rex-red)" }}>{error}</span>}
    </div>
  );
}

export function TextArea({ label, name, value, onChange, error, rows = 3, placeholder }) {
  return (
    <div className="rex-form-group">
      <label htmlFor={name}>{label}</label>
      <textarea
        id={name}
        className="rex-input"
        rows={rows}
        value={value ?? ""}
        onChange={(e) => onChange(name, e.target.value)}
        placeholder={placeholder}
        style={{ resize: "vertical", fontFamily: "inherit" }}
      />
      {error && <span style={{ fontSize: 11, color: "var(--rex-red)" }}>{error}</span>}
    </div>
  );
}

export function Select({ label, name, value, onChange, options, error, required, placeholder = "Select…" }) {
  return (
    <div className="rex-form-group">
      <label htmlFor={name}>
        {label}
        {required && <span style={{ color: "var(--rex-red)", marginLeft: 4 }}>*</span>}
      </label>
      <select
        id={name}
        className="rex-input"
        value={value ?? ""}
        onChange={(e) => onChange(name, e.target.value || null)}
      >
        <option value="">{placeholder}</option>
        {options.map((opt) => {
          const v = typeof opt === "string" ? opt : opt.value;
          const l = typeof opt === "string" ? opt.replace(/_/g, " ") : opt.label;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
      {error && <span style={{ fontSize: 11, color: "var(--rex-red)" }}>{error}</span>}
    </div>
  );
}

export function Checkbox({ label, name, value, onChange }) {
  return (
    <label className="rex-form-group" style={{ flexDirection: "row", alignItems: "center", gap: 8, cursor: "pointer" }}>
      <input
        type="checkbox"
        checked={!!value}
        onChange={(e) => onChange(name, e.target.checked)}
        style={{ width: 16, height: 16, cursor: "pointer" }}
      />
      <span style={{ fontSize: 13, fontWeight: 500, color: "var(--rex-text)", textTransform: "none", letterSpacing: "normal" }}>{label}</span>
    </label>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// FormDrawer — slide-in panel for create/edit
// ─────────────────────────────────────────────────────────────────────────

export function FormDrawer({ open, onClose, title, subtitle, children, onSubmit, onReset, dirty, submitting, error, success, mode = "create", canDelete, onDelete, width = 520 }) {
  // Block close if dirty unless user confirms
  const handleClose = useCallback(() => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    onClose();
  }, [dirty, onClose]);

  // ESC to close
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") handleClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, handleClose]);

  if (!open) return null;

  return (
    <div className="rex-drawer-overlay" onClick={handleClose}>
      <div className="rex-drawer" onClick={(e) => e.stopPropagation()} style={{ width }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid var(--rex-border)" }}>
          <div>
            <div className="rex-h3">{title}</div>
            {subtitle && <div className="rex-muted" style={{ fontSize: 12, marginTop: 2 }}>{subtitle}</div>}
          </div>
          <button className="rex-detail-panel-close" onClick={handleClose}>×</button>
        </div>

        <Flash type="error" message={error} />
        <Flash type="success" message={success} />

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!submitting) onSubmit();
          }}
          style={{ display: "flex", flexDirection: "column", gap: 12 }}
        >
          {children}

          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--rex-border)" }}>
            <div>
              {mode === "edit" && canDelete && onDelete && (
                <button
                  type="button"
                  className="rex-btn rex-btn-danger"
                  onClick={() => {
                    if (window.confirm("Delete this record? This cannot be undone.")) onDelete();
                  }}
                  disabled={submitting}
                >
                  Delete
                </button>
              )}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {onReset && dirty && (
                <button type="button" className="rex-btn rex-btn-outline" onClick={onReset} disabled={submitting}>
                  Reset
                </button>
              )}
              <button type="button" className="rex-btn rex-btn-outline" onClick={handleClose} disabled={submitting}>
                Cancel
              </button>
              <button type="submit" className="rex-btn rex-btn-primary" disabled={submitting || !dirty}>
                {submitting ? <Spinner size={12} /> : (mode === "edit" ? "Save" : "Create")}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// WriteButton — permission-aware
// ─────────────────────────────────────────────────────────────────────────

export function WriteButton({ children, onClick, variant = "primary", disabled, title, style }) {
  const { canWrite } = usePermissions();
  if (!canWrite) {
    return (
      <button
        className={`rex-btn rex-btn-${variant}`}
        disabled
        title="You do not have write access on this project"
        style={style}
      >
        {children}
      </button>
    );
  }
  return (
    <button className={`rex-btn rex-btn-${variant}`} onClick={onClick} disabled={disabled} title={title} style={style}>
      {children}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Strip null/empty fields from a payload before send
// ─────────────────────────────────────────────────────────────────────────

export function cleanPayload(values, allowEmpty = []) {
  const out = {};
  for (const [k, v] of Object.entries(values)) {
    if (v === undefined) continue;
    if (v === "" && !allowEmpty.includes(k)) continue;
    if (v === null) continue;
    out[k] = v;
  }
  return out;
}
