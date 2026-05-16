import React, { createContext, useContext, useMemo, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiDevice, ApiSystemState } from '../api/client';
import { Device, DeviceStatus, formatTimestamp } from '../types';
import { useAuth } from './AuthContext';

interface DevicesContextValue {
  devices: Device[];
  isLoading: boolean;
  error: Error | null;
  approveDevice: (id: string) => void;
  approveAllUnknownDevices: () => void;
  blockDevice: (id: string) => void;
  canManageDevices: boolean;
}

const DevicesContext = createContext<DevicesContextValue | null>(null);
const OPTIMISTIC_STATUS_HOLD_MS = 8_000;

function mapDevice(d: ApiDevice): Device {
  const statusMap: Record<string, DeviceStatus> = {
    PENDING: 'unknown',
    AUTHORIZED: 'approved',
    BLOCKED: 'blocked',
  };
  const category = d.fingerprint?.device_category ?? 'UNKNOWN';
  return {
    id: d.mac_address,
    mac: d.mac_address,
    name: d.owner_name ?? formatDeviceType(category),
    ip: d.ip_address,
    status: statusMap[d.status] ?? 'unknown',
    lastSeen: formatTimestamp(new Date(d.last_seen)),
    vendor: d.fingerprint?.manufacturer ?? 'Unknown',
    category,
    confidence: d.fingerprint?.confidence ?? 0,
    randomizedMac: d.fingerprint?.randomized_mac ?? false,
    primaryLayer: d.fingerprint?.primary_layer ?? (d.ip_address ? 'ARP' : 'PROBING'),
    connected: d.fingerprint?.connected ?? !!d.ip_address,
    fingerprintSignals: d.fingerprint?.signals ?? [],
  };
}

function formatDeviceType(category: string): string {
  const labels: Record<string, string> = {
    PHONE: 'Phone',
    TV: 'Smart TV',
    IOT: 'Smart Device',
    COMPUTER: 'Computer',
    UNKNOWN: 'Unknown Device',
  };
  return labels[category] ?? 'Unknown Device';
}

export function DevicesProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const { role, isAdmin } = useAuth();
  const [optimisticStatuses, setOptimisticStatuses] = useState<Record<string, ApiDevice['status']>>({});
  const optimisticTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const { data, isLoading, error } = useQuery({
    queryKey: ['devices'],
    queryFn: api.getDevices,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });

  function applyDeviceStatus(devices: ApiDevice[] | undefined, mac: string, newStatus: ApiDevice['status']) {
    return devices?.map((d) => d.mac_address === mac ? { ...d, status: newStatus } : d) ?? [];
  }

  function applyDeviceStatusToSystemState(
    state: ApiSystemState | undefined,
    mac: string,
    newStatus: ApiDevice['status'],
  ) {
    if (!state) return state;
    return {
      ...state,
      present_devices: applyDeviceStatus(state.present_devices, mac, newStatus),
      current_unknown_devices:
        newStatus === 'PENDING'
          ? state.current_unknown_devices
          : state.current_unknown_devices.filter((d) => d.mac_address !== mac),
      current_intruder_count:
        newStatus === 'PENDING'
          ? state.current_intruder_count
          : Math.max(0, state.current_intruder_count - 1),
    };
  }

  function setLocalOptimisticStatus(mac: string, newStatus: ApiDevice['status']) {
    const normalizedMac = mac.toUpperCase();
    if (optimisticTimers.current[normalizedMac]) {
      clearTimeout(optimisticTimers.current[normalizedMac]);
    }
    setOptimisticStatuses((old) => ({ ...old, [normalizedMac]: newStatus }));
    optimisticTimers.current[normalizedMac] = setTimeout(() => {
      clearLocalOptimisticStatus(normalizedMac);
      delete optimisticTimers.current[normalizedMac];
    }, OPTIMISTIC_STATUS_HOLD_MS);
  }

  function clearLocalOptimisticStatus(mac: string) {
    const normalizedMac = mac.toUpperCase();
    if (optimisticTimers.current[normalizedMac]) {
      clearTimeout(optimisticTimers.current[normalizedMac]);
      delete optimisticTimers.current[normalizedMac];
    }
    setOptimisticStatuses((old) => {
      const next = { ...old };
      delete next[normalizedMac];
      return next;
    });
  }

  function clearAllLocalOptimisticStatuses() {
    for (const timer of Object.values(optimisticTimers.current)) {
      clearTimeout(timer);
    }
    optimisticTimers.current = {};
    setOptimisticStatuses({});
  }

  function optimisticallyUpdateStatus(mac: string, newStatus: ApiDevice['status']) {
    setLocalOptimisticStatus(mac, newStatus);
    queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
      applyDeviceStatus(old, mac, newStatus)
    );
    queryClient.setQueryData<ApiSystemState>(['system-state'], (old) =>
      applyDeviceStatusToSystemState(old, mac, newStatus)
    );
  }

  function patchDeviceInCache(updated: ApiDevice) {
    queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
      old?.map((d) => d.mac_address === updated.mac_address ? { ...d, status: updated.status } : d) ?? []
    );
    queryClient.setQueryData<ApiSystemState>(['system-state'], (old) =>
      applyDeviceStatusToSystemState(old, updated.mac_address, updated.status)
    );
  }

  function restoreOptimisticSnapshot(snapshot?: {
    devices?: ApiDevice[];
    systemState?: ApiSystemState;
  }) {
    queryClient.setQueryData(['devices'], snapshot?.devices);
    queryClient.setQueryData(['system-state'], snapshot?.systemState);
  }

  const approveMutation = useMutation({
    mutationFn: (mac: string) => api.approveDevice(mac, role),
    onMutate: async (mac) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ['devices'] }),
        queryClient.cancelQueries({ queryKey: ['system-state'] }),
      ]);
      const snapshot = {
        devices: queryClient.getQueryData<ApiDevice[]>(['devices']),
        systemState: queryClient.getQueryData<ApiSystemState>(['system-state']),
      };
      optimisticallyUpdateStatus(mac, 'AUTHORIZED');
      return snapshot;
    },
    onSuccess: (updated) => patchDeviceInCache(updated),
    onError: (_error, mac, snapshot) => {
      clearLocalOptimisticStatus(mac);
      restoreOptimisticSnapshot(snapshot);
    },
    onSettled: async (_data, error, mac) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['devices'] }),
        queryClient.invalidateQueries({ queryKey: ['system-state'] }),
        queryClient.invalidateQueries({ queryKey: ['events'] }),
      ]);
      // Keep the local optimistic status briefly so stale polling cannot flicker back.
    },
  });

  const approveAllMutation = useMutation({
    mutationFn: () => api.approveAllPendingDevices(role),
    onMutate: async () => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ['devices'] }),
        queryClient.cancelQueries({ queryKey: ['system-state'] }),
      ]);
      const snapshot = {
        devices: queryClient.getQueryData<ApiDevice[]>(['devices']),
        systemState: queryClient.getQueryData<ApiSystemState>(['system-state']),
      };
      queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
        old?.map((d) => d.status === 'PENDING' ? { ...d, status: 'AUTHORIZED' } : d) ?? []
      );
      setOptimisticStatuses((old) => {
        const next = { ...old };
        for (const device of snapshot.devices ?? []) {
          if (device.status === 'PENDING') {
            next[device.mac_address.toUpperCase()] = 'AUTHORIZED';
          }
        }
        return next;
      });
      queryClient.setQueryData<ApiSystemState>(['system-state'], (old) => {
        if (!old) return old;
        return {
          ...old,
          present_devices: old.present_devices.map((d) =>
            d.status === 'PENDING' ? { ...d, status: 'AUTHORIZED' } : d
          ),
          current_unknown_devices: [],
          current_intruder_count: 0,
        };
      });
      return snapshot;
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<ApiDevice[]>(['devices'], (old) => {
        const updates = new Map(updated.map((d) => [d.mac_address, d]));
        return old?.map((d) => updates.get(d.mac_address) ?? d) ?? updated;
      });
    },
    onError: (_error, _variables, snapshot) => {
      clearAllLocalOptimisticStatuses();
      restoreOptimisticSnapshot(snapshot);
    },
    onSettled: () => {
      clearAllLocalOptimisticStatuses();
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      queryClient.invalidateQueries({ queryKey: ['system-state'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });

  const blockMutation = useMutation({
    mutationFn: (mac: string) => api.blockDevice(mac, role),
    onMutate: async (mac) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ['devices'] }),
        queryClient.cancelQueries({ queryKey: ['system-state'] }),
      ]);
      const snapshot = {
        devices: queryClient.getQueryData<ApiDevice[]>(['devices']),
        systemState: queryClient.getQueryData<ApiSystemState>(['system-state']),
      };
      optimisticallyUpdateStatus(mac, 'BLOCKED');
      return snapshot;
    },
    onSuccess: (updated) => patchDeviceInCache(updated),
    onError: (_error, mac, snapshot) => {
      clearLocalOptimisticStatus(mac);
      restoreOptimisticSnapshot(snapshot);
    },
    onSettled: async (_data, error, mac) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['devices'] }),
        queryClient.invalidateQueries({ queryKey: ['system-state'] }),
        queryClient.invalidateQueries({ queryKey: ['events'] }),
      ]);
      // Keep the local optimistic status briefly so stale polling cannot flicker back.
    },
  });

  const devices = useMemo(
    () =>
      [...(data ?? [])]
        .sort((a, b) => {
          const firstSeenDiff =
            new Date(a.first_seen).getTime() - new Date(b.first_seen).getTime();
          if (firstSeenDiff !== 0) return firstSeenDiff;
          return a.mac_address.localeCompare(b.mac_address);
        })
        .map((device) =>
          mapDevice({
            ...device,
            status: optimisticStatuses[device.mac_address.toUpperCase()] ?? device.status,
          })
        ),
    [data, optimisticStatuses],
  );

  return (
    <DevicesContext.Provider
      value={{
        devices,
        isLoading,
        error: error as Error | null,
        approveDevice: (id) => {
          if (isAdmin) {
            setLocalOptimisticStatus(id, 'AUTHORIZED');
            approveMutation.mutate(id);
          }
        },
        approveAllUnknownDevices: () => {
          if (isAdmin) {
            setOptimisticStatuses((old) => {
              const next = { ...old };
              for (const device of data ?? []) {
                if ((optimisticStatuses[device.mac_address.toUpperCase()] ?? device.status) === 'PENDING') {
                  next[device.mac_address.toUpperCase()] = 'AUTHORIZED';
                }
              }
              return next;
            });
            approveAllMutation.mutate();
          }
        },
        blockDevice: (id) => {
          if (isAdmin) {
            setLocalOptimisticStatus(id, 'BLOCKED');
            blockMutation.mutate(id);
          }
        },
        canManageDevices: isAdmin,
      }}
    >
      {children}
    </DevicesContext.Provider>
  );
}

export function useDevices() {
  const ctx = useContext(DevicesContext);
  if (!ctx) throw new Error('useDevices must be used inside DevicesProvider');
  return ctx;
}
