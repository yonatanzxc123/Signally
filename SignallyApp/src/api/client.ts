import { Platform } from 'react-native';
// 10.0.2.2 = Android emulator host alias; real devices need the server's LAN IP.
const BASE_URL =
  Platform.OS === 'web'
    ? 'http://127.0.0.1:8000'
    : 'http://10.100.102.9:8000';

// ── Types ──────────────────────────────────────────────────────────────────

export type BackendDeviceStatus = 'PENDING' | 'AUTHORIZED' | 'BLOCKED';
export type ApiUserRole = 'ADMIN' | 'FAMILY' | 'GUEST';

export interface ApiDevice {
  mac_address: string;
  ip_address: string | null;
  status: BackendDeviceStatus;
  first_seen: string;
  last_seen: string;
  owner_user_id?: number | null;
  owner_name?: string | null;
  owner_role?: ApiUserRole | null;
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
  admin_present: boolean;
  family_present: boolean;
  guest_present: boolean;
  decision: string;
  reason: string;
  present_devices: ApiDevice[];
  current_intruder_count: number;
  current_unknown_devices: ApiDevice[];
  ignored_authorized_duplicate_count: number;
  admin_review_grace_active: boolean;
  notification_audience: ApiUserRole[];
}

export interface ApiMonitoringCycle {
  csi_presence_detected: boolean;
  approved_user_present: boolean;
  admin_present: boolean;
  family_present: boolean;
  guest_present: boolean;
  decision: string;
  reason: string;
  processed_devices_count: number;
  present_devices_count: number;
  authorized_devices_count: number;
  pending_devices_count: number;
  blocked_devices_count: number;
  current_intruder_count: number;
  ignored_authorized_duplicate_count: number;
  admin_review_grace_active: boolean;
  notification_audience: ApiUserRole[];
}

export interface ApiMessage {
  message: string;
}

export interface ApiProbeInfo {
  mac_address: string;
  vendor: string | null;
  known_ssids: string[];
  latest_rssi: number | null;
  is_nearby_only: boolean;
}

// ── Core fetch helper ──────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const headers = {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    };
    const res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API ${res.status}: ${body}`);
    }
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

function roleHeaders(role: ApiUserRole): HeadersInit {
  return { 'X-Signally-User-Role': role };
}

// ── API ────────────────────────────────────────────────────────────────────

export const api = {
  // Devices
  getDevices: () => request<ApiDevice[]>('/devices'),
  getPendingDevices: () => request<ApiDevice[]>('/devices/pending'),
  approveDevice: (mac: string, role: ApiUserRole = 'ADMIN') =>
    request<ApiDevice>(`/devices/${encodeURIComponent(mac)}/approve`, {
      method: 'POST',
      headers: roleHeaders(role),
    }),
  approveAllPendingDevices: (role: ApiUserRole = 'ADMIN') =>
    request<ApiDevice[]>('/devices/approve-all', {
      method: 'POST',
      headers: roleHeaders(role),
    }),
  blockDevice: (mac: string, role: ApiUserRole = 'ADMIN') =>
    request<ApiDevice>(`/devices/${encodeURIComponent(mac)}/block`, {
      method: 'POST',
      headers: roleHeaders(role),
    }),
  deleteDevice: (mac: string) =>
    request<ApiMessage>(`/devices/${encodeURIComponent(mac)}`, { method: 'DELETE' }),

  scanNetwork: () => request<ApiDevice[]>('/scan', { method: 'POST' }),

  getDeviceProbeInfo: (mac: string) =>
    request<ApiProbeInfo>(`/probe-info/${encodeURIComponent(mac)}`),

  // Wifi Probing
  startWifiProbing: () => request<ApiMessage>('/wifi_probing/start', { method: 'POST' }),
  stopWifiProbing: () => request<ApiMessage>('/wifi_probing/stop', { method: 'POST' }),
  getWifiProbingStatus: () => request<{ running: boolean; interface: string | null }>('/wifi_probing/status'),
  getWifiProbingDevices: () => request<ApiDevice[]>('/wifi_probing/devices'),

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
