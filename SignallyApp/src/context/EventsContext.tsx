import React, { createContext, useContext } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiEvent } from '../api/client';
import { NetworkEvent, EventType } from '../types';

interface EventsContextValue {
  events: NetworkEvent[];
  isLoading: boolean;
  error: Error | null;
}

const EventsContext = createContext<EventsContextValue | null>(null);

const EVENT_TYPE_MAP: Record<string, EventType> = {
  DEVICE_DISCOVERED_NEW: 'unknown_detected',
  DEVICE_SEEN_AGAIN: 'scan_complete',
  DEVICE_APPROVED: 'device_approved',
  DEVICE_BLOCKED: 'device_blocked',
  APPROVED_USER_PRESENT: 'system',
  NO_APPROVED_USER_PRESENT: 'system',
  UNAUTHORIZED_PRESENCE_ALERT: 'unknown_detected',
  BLOCKED_DEVICE_ALERT: 'device_blocked',
  MONITORING_CYCLE_COMPLETED: 'scan_complete',
  WIFI_PROBE_DEVICE_DISCOVERED_NEW: 'unknown_detected',
  WIFI_PROBE_DEVICE_SEEN_AGAIN: 'scan_complete',
};

const EVENT_MESSAGE_MAP: Record<string, string> = {
  DEVICE_DISCOVERED_NEW: 'Unknown device detected on network',
  DEVICE_SEEN_AGAIN: 'Known device seen again',
  DEVICE_APPROVED: 'Device approved',
  DEVICE_BLOCKED: 'Device blocked',
  APPROVED_USER_PRESENT: 'Authorized user identified',
  NO_APPROVED_USER_PRESENT: 'No authorized user present',
  UNAUTHORIZED_PRESENCE_ALERT: 'Unauthorized presence alert',
  BLOCKED_DEVICE_ALERT: 'Blocked device detected',
  MONITORING_CYCLE_COMPLETED: 'Network scan completed',
  WIFI_PROBE_DEVICE_DISCOVERED_NEW: 'Nearby device detected via probe request',
  WIFI_PROBE_DEVICE_SEEN_AGAIN: 'Nearby device seen again via probe',
};

const PROBE_EVENT_TYPES = new Set([
  'WIFI_PROBE_DEVICE_DISCOVERED_NEW',
  'WIFI_PROBE_DEVICE_SEEN_AGAIN',
]);

function parseProbeDetails(details: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const part of details.split('; ')) {
    const idx = part.indexOf('=');
    if (idx !== -1) result[part.slice(0, idx).trim()] = part.slice(idx + 1).trim();
  }
  return result;
}

function signalLabel(rssi: number): string {
  if (rssi >= -60) return `Strong (${rssi} dBm)`;
  if (rssi >= -75) return `Medium (${rssi} dBm)`;
  return `Weak (${rssi} dBm)`;
}

function formatProbeDetail(mac: string | null, details: string): string {
  const parsed = parseProbeDetails(details);
  const ssid = parsed['ssid']?.trim();
  const rssi = parsed['rssi'] ? parseInt(parsed['rssi']) : null;
  const ssidPart = ssid ? `"${ssid}"` : 'Unknown network';
  const signalPart = rssi != null ? ` · ${signalLabel(rssi)}` : '';
  return `${ssidPart}${signalPart}`;
}

function mapEvent(e: ApiEvent): NetworkEvent {
  const isProbe = PROBE_EVENT_TYPES.has(e.event_type);
  const detail = isProbe
    ? formatProbeDetail(e.device_mac, e.details)
    : e.device_mac ? `${e.device_mac} — ${e.details}` : e.details;

  return {
    id: String(e.id),
    type: EVENT_TYPE_MAP[e.event_type] ?? 'system',
    message: EVENT_MESSAGE_MAP[e.event_type] ?? e.event_type,
    detail,
    timestamp: new Date(e.created_at),
  };
}

export function EventsProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['events'],
    queryFn: () => api.getEvents(100),
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });

  const events = (data ?? []).map(mapEvent);

  return (
    <EventsContext.Provider value={{ events, isLoading, error: error as Error | null }}>
      {children}
    </EventsContext.Provider>
  );
}

export function useEvents() {
  const ctx = useContext(EventsContext);
  if (!ctx) throw new Error('useEvents must be used inside EventsProvider');
  return ctx;
}
