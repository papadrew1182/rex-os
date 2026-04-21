// Thin fetch wrappers for the Phase 6 action queue endpoints.
//
// Retry after a failure = call approveAction again (re-runs the
// handler with the same semantics as initial approval).

import { apiUrl, getToken } from "../api";

/**
 * Approve an action.
 *
 * @param {string} action_id
 * @returns {Promise<object>} response body as JSON
 * @throws {Error} on non-2xx status
 */
export async function approveAction(action_id) {
  const token = getToken();
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(apiUrl(`/actions/${action_id}/approve`), {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`approve failed: ${res.status} ${body}`);
  }
  return res.json();
}

/**
 * Discard an action.
 *
 * @param {string} action_id
 * @returns {Promise<object>} response body as JSON
 * @throws {Error} on non-2xx status
 */
export async function discardAction(action_id) {
  const token = getToken();
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(apiUrl(`/actions/${action_id}/discard`), {
    method: "POST",
    headers,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`discard failed: ${res.status} ${body}`);
  }
  return res.json();
}

/**
 * Undo an action.
 *
 * Returns { status, body } instead of throwing, so the caller can
 * distinguish 400 (window expired) from 500 (compensator failed)
 * without error handling.
 *
 * @param {string} action_id
 * @returns {Promise<{status: number, body: object}>}
 */
export async function undoAction(action_id) {
  const token = getToken();
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(apiUrl(`/actions/${action_id}/undo`), {
    method: "POST",
    headers,
  });
  let body = {};
  try {
    body = await res.json();
  } catch {
    // noop — body remains empty on parse failure
  }
  return { status: res.status, body };
}
