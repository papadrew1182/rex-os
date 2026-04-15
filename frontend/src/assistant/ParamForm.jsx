// ParamForm — renders an action parameter form from `params_schema`.
//
// Supported types (from the Session 3 contract):
//   project   — project picker (backed by useProject's available projects)
//   project_opt — project picker (optional; allows blank)
//   date      — <input type="date">
//   month     — <input type="month">
//   quarter   — select Q1/Q2/Q3/Q4
//   year      — select current±3
//   text      — <input type="text">
//   select    — <select> from param.options [{value, label}]
//   role      — select from canonical role keys
//
// The form collects values, validates `required` params, and hands
// back a normalized `{ PARAM_NAME: value, ... }` object to `onSubmit`.
// Defaults: `project` params prefill with the currently selected project.

import { useState, useMemo, useCallback } from "react";
import { useProject } from "../project";

const CANONICAL_ROLES = [
  { value: "VP", label: "VP" },
  { value: "PM", label: "PM" },
  { value: "GENERAL_SUPER", label: "General Super" },
  { value: "LEAD_SUPER", label: "Lead Super" },
  { value: "ASSISTANT_SUPER", label: "Assistant Super" },
  { value: "ACCOUNTANT", label: "Accountant" },
];

function currentYear() {
  return new Date().getFullYear();
}

function yearOptions() {
  const y = currentYear();
  return [y - 2, y - 1, y, y + 1, y + 2].map((n) => ({ value: String(n), label: String(n) }));
}

const QUARTER_OPTIONS = [
  { value: "Q1", label: "Q1" },
  { value: "Q2", label: "Q2" },
  { value: "Q3", label: "Q3" },
  { value: "Q4", label: "Q4" },
];

export default function ParamForm({ schema, currentContext, disabled, onSubmit, submitLabel }) {
  const { projects, selectedId } = useProject();

  // Seed initial values from context + sensible defaults.
  const initial = useMemo(() => {
    const v = {};
    for (const param of schema || []) {
      if (param.type === "project" || param.type === "project_opt") {
        v[param.name] = currentContext.project?.id || selectedId || "";
      } else if (param.type === "date") {
        v[param.name] = new Date().toISOString().slice(0, 10);
      } else if (param.type === "month") {
        v[param.name] = new Date().toISOString().slice(0, 7);
      } else if (param.type === "quarter") {
        const m = new Date().getMonth();
        v[param.name] = `Q${Math.floor(m / 3) + 1}`;
      } else if (param.type === "year") {
        v[param.name] = String(currentYear());
      } else {
        v[param.name] = "";
      }
    }
    return v;
  }, [schema, currentContext.project?.id, selectedId]);

  const [values, setValues] = useState(initial);
  const [touched, setTouched] = useState({});

  const setField = useCallback((name, value) => {
    setValues((v) => ({ ...v, [name]: value }));
    setTouched((t) => ({ ...t, [name]: true }));
  }, []);

  const missingRequired = useMemo(() => {
    return (schema || [])
      .filter((p) => p.required && !String(values[p.name] || "").trim())
      .map((p) => p.name);
  }, [schema, values]);

  const handleSubmit = useCallback(() => {
    if (disabled) return;
    if (missingRequired.length > 0) {
      const allTouched = {};
      missingRequired.forEach((n) => { allTouched[n] = true; });
      setTouched((t) => ({ ...t, ...allTouched }));
      return;
    }
    // Strip empty values so the payload is clean
    const clean = {};
    for (const [k, v] of Object.entries(values)) {
      if (v !== "" && v != null) clean[k] = v;
    }
    onSubmit(clean);
  }, [disabled, missingRequired, values, onSubmit]);

  return (
    <div className="rex-param-form" role="group" aria-label="Action parameters">
      {(schema || []).map((param) => {
        const value = values[param.name] ?? "";
        const isMissing = param.required && touched[param.name] && !String(value).trim();
        return (
          <div key={param.name} className={`rex-param-form__field${isMissing ? " rex-param-form__field--error" : ""}`}>
            <label className="rex-param-form__label" htmlFor={`param-${param.name}`}>
              {param.label || param.name}
              {param.required && <span className="rex-param-form__required" aria-hidden="true"> *</span>}
            </label>
            <FieldInput
              id={`param-${param.name}`}
              param={param}
              value={value}
              onChange={(v) => setField(param.name, v)}
              projects={projects}
              disabled={disabled}
            />
            {isMissing && <span className="rex-param-form__error">Required</span>}
          </div>
        );
      })}
      {/* type="button" per the Playwright collision rationale in ChatComposer.jsx */}
      <button
        type="button"
        className="rex-param-form__submit"
        disabled={disabled}
        onClick={handleSubmit}
      >
        {submitLabel || "Run"}
      </button>
    </div>
  );
}

function FieldInput({ id, param, value, onChange, projects, disabled }) {
  const common = { id, disabled, className: "rex-param-form__input" };

  switch (param.type) {
    case "project":
    case "project_opt":
      return (
        <select {...common} value={value || ""} onChange={(e) => onChange(e.target.value)}>
          {param.type === "project_opt" && <option value="">(Any project)</option>}
          {param.type === "project" && !value && <option value="" disabled>Pick a project…</option>}
          {(projects || []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}{p.project_number ? ` (${p.project_number})` : ""}
            </option>
          ))}
        </select>
      );
    case "date":
      return <input {...common} type="date" value={value || ""} onChange={(e) => onChange(e.target.value)} />;
    case "month":
      return <input {...common} type="month" value={value || ""} onChange={(e) => onChange(e.target.value)} />;
    case "quarter":
      return (
        <select {...common} value={value || ""} onChange={(e) => onChange(e.target.value)}>
          {QUARTER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      );
    case "year":
      return (
        <select {...common} value={value || ""} onChange={(e) => onChange(e.target.value)}>
          {yearOptions().map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      );
    case "role":
      return (
        <select {...common} value={value || ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select role…</option>
          {CANONICAL_ROLES.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      );
    case "select":
      return (
        <select {...common} value={value || ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select…</option>
          {(param.options || []).map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label || opt.value}</option>
          ))}
        </select>
      );
    case "text":
    default:
      return (
        <input
          {...common}
          type="text"
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={param.placeholder || ""}
        />
      );
  }
}
