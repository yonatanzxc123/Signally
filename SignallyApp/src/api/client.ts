import { Platform } from 'react-native';
// 10.0.2.2 = Android emulator host alias; real devices need the server's LAN IP.
const BASE_URL =
  Platform.OS === 'web'
    ? 'http://127.0.0.1:8000'
    : 'http://10.100.102.9:8000';

// ── Types ──────────────────────────────────────────────────────────────────

export type BackendDeviceStatus = 'PENDING' | 'AUTHORIZED' | 'BLOCKED';

export interface ApiDevice {
  mac_address: string;
  ip_address: string;
  status: BackendDeviceStatus;
  first_seen: string;
  last_seen: string;
}

export interface ApiEvent {
  id: number;
  event_type: string;
  device_mac: string | null;
  details: string;
  created_at: string;
}

export interface ApiSystemState {
  csi_presence_detected: boolean;
  approved_user_present: boolean;
  decision: string;
  reason: string;
  present_devices: ApiDevice[];
}

export interface ApiMonitoringCycle {
  csi_presence_detected: boolean;
  approved_user_present: boolean;
  decision: string;
  reason: string;
  processed_devices_count: number;
  present_devices_count: number;
  authorized_devices_count: number;
  pending_devices_count: number;
  blocked_devices_count: number;
}

export interface ApiMessage {
  message: string;
}

// ── Core fetch helper ──────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ── API ────────────────────────────────────────────────────────────────────

export const api = {
  // Devices
  getDevices: () => request<ApiDevice[]>('/devices'),
  getPendingDevices: () => request<ApiDevice[]>('/devices/pending'),
  approveDevice: (mac: string) =>
    request<ApiDevice>(`/devices/${encodeURIComponent(mac)}/approve`, { method: 'POST' }),
  blockDevice: (mac: string) =>
    request<ApiDevice>(`/devices/${encodeURIComponent(mac)}/block`, { method: 'POST' }),
  deleteDevice: (mac: string) =>
    request<ApiMessage>(`/devices/${encodeURIComponent(mac)}`, { method: 'DELETE' }),

  // TEMPORARY: calls direct ARP scan endpoint. Replace with runMonitoringCycle once Raspberry Pi is integrated.
  scanNetwork: () => request<ApiDevice[]>('/scan', { method: 'POST' }),

  // Events
  getEvents: (limit = 50) => request<ApiEvent[]>(`/events?limit=${limit}`),

  // System
  getSystemState: () => request<ApiSystemState>('/system/state'),
  runMonitoringCycle: () =>
    request<ApiMonitoringCycle>('/monitoring/run-cycle', { method: 'POST' }),

  // Admin
  clearAllDevices: () => request<ApiMessage>('/admin/devices', { method: 'DELETE' }),
  clearAllEvents: () => request<ApiMessage>('/admin/events', { method: 'DELETE' }),
  resetDatabase: () => request<ApiMessage>('/admin/reset', { method: 'DELETE' }),
};
