// Lisans durumu: program açılırken ve anahtar girilince yenilenir.

import * as api from "./api.js";

let current = null;

export async function refresh() {
  current = await api.get("/license");
  return current;
}

export function status() {
  return current;
}

export function set(value) {
  current = value;
}

export function formatDate(iso) {
  if (!iso) return "";
  const [year, month, day] = iso.split("-");
  return `${day}.${month}.${year}`;
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
