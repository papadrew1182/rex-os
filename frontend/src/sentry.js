// Frontend Sentry integration.
//
// Gated entirely on VITE_SENTRY_DSN. With no DSN set we return stub functions
// so callers never need to know whether Sentry is live — this keeps dev and
// preview builds zero-cost. Release identity (GIT_SHA / BUILD_TIME) is pulled
// from version.js so the dashboard can correlate an event with the exact
// deployed build.

import * as Sentry from "@sentry/react";
import { GIT_SHA, BUILD_TIME } from "./version";

const DSN = import.meta.env?.VITE_SENTRY_DSN || "";
const ENV = import.meta.env?.VITE_SENTRY_ENV || import.meta.env?.MODE || "production";

let initialized = false;

export function initSentry() {
  if (initialized || !DSN) return;
  try {
    Sentry.init({
      dsn: DSN,
      release: `rex-os-frontend@${GIT_SHA}`,
      environment: ENV,
      tracesSampleRate: 0, // no perf tracing by default — cheap
      // Default integrations are fine; we only need error capture for this sprint.
      beforeSend(event) {
        // Drop auth noise — /login 401s are normal flow, not bugs.
        const msg = event?.exception?.values?.[0]?.value || "";
        if (msg === "Unauthorized") return null;
        return event;
      },
    });
    Sentry.setTag("build.commit", GIT_SHA);
    Sentry.setTag("build.time", BUILD_TIME);
    initialized = true;
  } catch (e) {
    // Sentry init should never break the app shell.
    // eslint-disable-next-line no-console
    console.warn("Sentry init failed:", e?.message || e);
  }
}

export function captureError(error, context) {
  if (!initialized) return;
  try {
    Sentry.captureException(error, context ? { extra: context } : undefined);
  } catch {
    /* swallow */
  }
}

export const isSentryEnabled = () => initialized;
