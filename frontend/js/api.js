/*
 * Hàm gọi API dùng chung cho app du khách và admin.
 * Backend luôn trả {success, data, message} hoặc {success:false, error:{code, message}}.
 */
const API_BASE = "/api/v1";

class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function apiRequest(path, { method = "GET", body, token, headers = {} } = {}) {
  const opts = { method, headers: { ...headers } };
  if (token) opts.headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(API_BASE + path, opts);
  } catch (e) {
    throw new ApiError(0, "NETWORK_ERROR", "Không kết nối được máy chủ");
  }
  if (res.status === 304) return { notModified: true, headers: res.headers };
  let json = null;
  try {
    json = await res.json();
  } catch (_) {
    /* phản hồi rỗng */
  }
  if (!res.ok || (json && json.success === false)) {
    const err = (json && json.error) || {};
    throw new ApiError(res.status, err.code || "HTTP_" + res.status, err.message || res.statusText, err.details);
  }
  return { data: json ? json.data : null, message: json ? json.message : null, headers: res.headers };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

const storage = {
  get(key, fallback = null) {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch (_) {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (_) {
      /* hết dung lượng / chế độ riêng tư */
    }
  },
  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch (_) {}
  },
};
