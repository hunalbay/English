// Backend ile iletişim. Tüm istekler aynı kaynağa (127.0.0.1) gider.

const API = "/api/v1";
let tokenPromise = null;

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    /* gövde yok ya da JSON değil */
  }
  if (!response.ok) {
    const error = body && body.error;
    throw new ApiError(
      (error && error.message) || "Sunucu beklenmeyen bir yanıt verdi.",
      response.status,
      error && error.code,
    );
  }
  return body;
}

async function request(path, options) {
  let response;
  try {
    response = await fetch(API + path, options);
  } catch {
    throw new ApiError("Programa ulaşılamıyor. English Master kapatılmış olabilir.", 0, "unreachable");
  }
  return parse(response);
}

function sessionToken() {
  if (!tokenPromise) {
    tokenPromise = request("/session").then((data) => data.token);
    tokenPromise.catch(() => { tokenPromise = null; });
  }
  return tokenPromise;
}

export function get(path) {
  return request(path);
}

export async function send(method, path, payload) {
  const attempt = async () =>
    request(path, {
      method,
      headers: { "Content-Type": "application/json", "X-EM-Token": await sessionToken() },
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
  try {
    return await attempt();
  } catch (error) {
    // Program yeniden başlatıldıysa belirteç değişmiştir; bir kez yenileyip tekrar dene.
    if (error instanceof ApiError && error.code === "invalid_token") {
      tokenPromise = null;
      return attempt();
    }
    throw error;
  }
}

export const put = (path, payload) => send("PUT", path, payload);
export const post = (path, payload) => send("POST", path, payload);
