// API client for the FastAPI CVD service. Session cookie is httpOnly;
// the separate CSRF cookie is echoed on state-changing requests.
const API_URL = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(message, status, details = []) {
    super(message);
    this.status = status;
    this.details = details;
  }
}
export class PredictionError extends ApiError {}

function readCsrfCookie() {
  const match = document.cookie.match(/(?:^|;\s*)cvd_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function apiFetch(path, { method = "GET", body, ErrorClass = ApiError } = {}) {
  const headers = {};
  let payload;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (method !== "GET") {
    const csrf = readCsrfCookie();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method, headers, credentials: "include", body: payload,
    });
  } catch {
    throw new ErrorClass("Could not reach the CVD server. Check that Docker services are running.", 0);
  }
  let data = null;
  try { data = await response.json(); } catch { /* no JSON response */ }
  if (!response.ok) {
    const detail = data?.detail;
    const details = Array.isArray(detail) ? detail.map(x => x.msg || String(x)) :
      Array.isArray(data?.details) ? data.details : [];
    const message = typeof detail === "string" ? detail :
      data?.error || details[0] || "The server returned an error.";
    throw new ErrorClass(message, response.status, details);
  }
  return data;
}

export function apiSignUp({ name, email, password, acceptTerms }) {
  return apiFetch("/api/auth/signup", { method: "POST", body: { name, email, password, accept_terms: acceptTerms === true } });
}
export function apiForgotPassword(email) {
  return apiFetch("/api/auth/forgot-password", { method: "POST", body: { email } });
}
export function apiResetPassword(token, password) {
  return apiFetch("/api/auth/reset-password", { method: "POST", body: { token, password } });
}
export function apiSignIn({ email, password }) {
  return apiFetch("/api/auth/login", { method: "POST", body: { email, password } });
}
export function apiSignOut() { return apiFetch("/api/auth/logout", { method: "POST" }); }
export function apiCurrentUser() { return apiFetch("/api/auth/me"); }
export function apiGetPatient() { return apiFetch("/api/patient"); }
export function apiClearPatient() { return apiFetch("/api/patient", { method: "DELETE" }); }
export function apiSchema() { return apiFetch("/api/schema"); }
export function apiAssessments() { return apiFetch("/api/assessments"); }
export function apiAssessment(id) { return apiFetch(`/api/assessments/${id}`); }
export function apiReliability() { return apiFetch("/api/reliability"); }
export function apiAuditTrail() { return apiFetch("/api/audit"); }
export function apiDeleteAccount() { return apiFetch("/api/account", { method: "DELETE" }); }
export function predictRisk(record) {
  return apiFetch("/api/predict", { method: "POST", body: record, ErrorClass: PredictionError });
}
export async function downloadReport(id) {
  const res = await fetch(`${API_URL}/api/report/${id}.pdf`, { credentials: "include" });
  if (!res.ok) throw new ApiError("Could not generate the report.", res.status);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `BRISK2_report_${id}.pdf`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
