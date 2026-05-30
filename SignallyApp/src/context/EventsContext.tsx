import React, { createContext, useContext } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiEvent } from '../api/client';
import { NetworkEvent, EventType } from '../types';

interface EventsContextValue {
  events: NetworkEvent[];
  isLoading: boolean;
  error: Error | null;
  ssidsByMac: Record<string, string[]>;
}

const EventsContext = createContext<EventsContextValue | null>(null);

const EVENT_TYPE_MAP: Record<string, EventType> = {
  DEVICE_DISCOVERED_NEW: 'unknown_detected',
  WIFI_PROBE_DEVICE_DISCOVERED_NEW: 'unknown_detected',
  DEVICE_APPROVED: 'device_approved',
  DEVICE_BLOCKED: 'device_blocked',
  APPROVED_USER_PRESENT: 'system',
  NO_APPROVED_USER_PRESENT: 'system',
  UNAUTHORIZED_PRESENCE_ALERT: 'unknown_detected',
  BLOCKED_DEVICE_ALERT: 'device_blocked',
};

const EVENT_MESSAGE_MAP: Record<string, string> = {
  DEVICE_DISCOVERED_NEW: 'New device on network',
  WIFI_PROBE_DEVICE_DISCOVERED_NEW: 'Strong nearby device detected',
  DEVICE_APPROVED: 'Device approved',
  DEVICE_BLOCKED: 'Device blocked',
  APPROVED_USER_PRESENT: 'Authorized user identified',
  NO_APPROVED_USER_PRESENT: 'No authorized user present',
  UNAUTHORIZED_PRESENCE_ALERT: 'Unauthorized presence alert',
  BLOCKED_DEVICE_ALERT: 'Blocked device detected',
};

const LOG_EVENT_TYPES = new Set(Object.keys(EVENT_TYPE_MAP));

function buildSsidMap(events: ApiEvent[]): Record<string, string[]> {
  const map: Record<string, string[]> = {};
  for (const e of events) {
    if (!e.device_mac) continue;
    if (e.event_type !== 'WIFI_PROBE_DEVICE_DISCOVERED_NEW' && e.event_type !== 'WIFI_PROBE_DEVICE_SEEN_AGAIN') continue;
    const match = e.details.match(/ssid=([^;]*)/);
    const ssid = match?.[1]?.trim();
    if (!ssid) continue;
    const mac = e.device_mac.toUpperCase();
    if (!map[mac]) map[mac] = [];
    if (!map[mac].includes(ssid)) map[mac].push(ssid);
  }
  return map;
}

function mapEvent(e: ApiEvent): NetworkEvent {
  return {
    id: String(e.id),
    type: EVENT_TYPE_MAP[e.event_type] ?? 'system',
    message: EVENT_MESSAGE_MAP[e.event_type] ?? e.event_type,
    detail: e.device_mac ? `${e.device_mac} — ${e.details}` : e.details,
    timestamp: new Date(e.created_at),
  };
}

export function EventsProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['events'],
    queryFn: () => api.getEvents(500),
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });

  const raw = data ?? [];
  const events = raw.filter((e) => LOG_EVENT_TYPES.has(e.event_type)).map(mapEvent);
  const ssidsByMac = buildSsidMap(raw);

  return (
    <EventsContext.Provider value={{ events, isLoading, error: error as Error | null, ssidsByMac }}>
      {children}
    </EventsContext.Provider>
  );
}

export function useEvents() {
  const ctx = useContext(EventsContext);
  if (!ctx) throw new Error('useEvents must be used inside EventsProvider');
  return ctx;
}
