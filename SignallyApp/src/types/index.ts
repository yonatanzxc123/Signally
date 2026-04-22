export type DeviceStatus = 'approved' | 'unknown' | 'blocked';

export type EventType =
  | 'unknown_detected'
  | 'device_approved'
  | 'device_blocked'
  | 'scan_complete'
  | 'system';

export interface Device {
  id: string;
  mac: string;
  name: string;
  ip: string;
  status: DeviceStatus;
  lastSeen: string;
  vendor: string;
}

export interface NetworkEvent {
  id: string;
  type: EventType;
  message: string;
  detail: string;
  timestamp: Date;
}

export function formatTimestamp(date: Date): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
}
