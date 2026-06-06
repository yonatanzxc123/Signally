import React, { createContext, useContext, useMemo, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiDevice, ApiSystemState } from '../api/client';
import { Device, DeviceStatus, formatTimestamp } from '../types';
import { useAuth } from './AuthContext';

interface DevicesContextValue {
  devices: Device[];
  isLoading: boolean;
  error: Error | null;
  approveDevice: (id: string, ownerRole: 'FAMILY' | 'GUEST') => void;
  approveAllUnknownDevices: (ownerRole: 'FAMILY' | 'GUEST') => void;
  blockDevice: (id: string) => void;
  canManageDevices: boolean;
}

const DevicesContext = createContext<DevicesContextValue | null>(null);
const OPTIMISTIC_STATUS_HOLD_MS = 8_000;

function getDeviceDisplayName(d: ApiDevice): string {
  if (d.owner_name) return d.owner_name;

  switch (d.owner_role) {
    case 'ADMIN':
      return 'Admin Device';
    case 'FAMILY':
      return 'Family Device';
    case 'GUEST':
      return 'Guest Device';
    default:
      return 'Unknown Device';
  }
}

function mapDevice(d: ApiDevice): Device {
  const statusMap: Record<string, DeviceStatus> = {
    PENDING: 'unknown',
    AUTHORIZED: 'approved',
    BLOCKED: 'blocked',
  };
  return {
    id: d.mac_address,
    mac: d.mac_address,
    name: getDeviceDisplayName(d),
    ip: d.ip_address,
    status: statusMap[d.status] ?? 'unknown',
    ownerRole: (d.owner_role as Device['ownerRole']) ?? null,
    lastSeen: formatTimestamp(new Date(d.last_seen)),
    connected: !!d.ip_address,
  };
}

export function DevicesProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const { role, isAdmin } = useAuth();
  type OptimisticPatch = { status: ApiDevice['status']; ownerRole?: ApiDevice['owner_role'] };
  const [optimisticStatuses, setOptimisticStatuses] = useState<Record<string, OptimisticPatch>>({});
  const optimisticTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const { data, isLoading, error } = useQuery({
    queryKey: ['devices'],
    queryFn: api.getDevices,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });

  function applyDeviceStatus(devices: ApiDevice[] | undefined, mac: string, newStatus: ApiDevice['status'], ownerRole?: ApiDevice['owner_role']) {
    return devices?.map((d) => d.mac_address === mac ? { ...d, status: newStatus, owner_role: ownerRole !== undefined ? ownerRole : d.owner_role } : d) ?? [];
  }

  function applyDeviceStatusToSystemState(
    state: ApiSystemState | undefined,
    mac: string,
    newStatus: ApiDevice['status'],
    ownerRole?: ApiDevice['owner_role'],
  ) {
    if (!state) return state;
    return {
      ...state,
      present_devices: applyDeviceStatus(state.present_devices, mac, newStatus, ownerRole),
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

  function setLocalOptimisticStatus(mac: string, newStatus: ApiDevice['status'], ownerRole?: ApiDevice['owner_role']) {
    const normalizedMac = mac.toUpperCase();
    if (optimisticTimers.current[normalizedMac]) {
      clearTimeout(optimisticTimers.current[normalizedMac]);
    }
    setOptimisticStatuses((old) => ({ ...old, [normalizedMac]: { status: newStatus, ownerRole } }));
    optimisticTimers.current[normalizedMac] = setTimeout(() => {
      clearLocalOptimisticStatus(normalizedMac);
      delete optimisticTimers.current[normalizedMac];
    }, OPTIMISTIC_STATUS_HOLD_MS);
  }

  function setManyLocalOptimisticStatuses(
    updates: Array<{ mac: string; status: ApiDevice['status']; ownerRole?: ApiDevice['owner_role'] }>,
  ) {
    for (const update of updates) {
      const normalizedMac = update.mac.toUpperCase();
      if (optimisticTimers.current[normalizedMac]) {
        clearTimeout(optimisticTimers.current[normalizedMac]);
      }
      optimisticTimers.current[normalizedMac] = setTimeout(() => {
        clearLocalOptimisticStatus(normalizedMac);
        delete optimisticTimers.current[normalizedMac];
      }, OPTIMISTIC_STATUS_HOLD_MS);
    }

    setOptimisticStatuses((old) => {
      const next = { ...old };
      for (const update of updates) {
        next[update.mac.toUpperCase()] = { status: update.status, ownerRole: update.ownerRole };
      }
      return next;
    });
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

  function optimisticallyUpdateStatus(mac: string, newStatus: ApiDevice['status'], ownerRole?: ApiDevice['owner_role']) {
    setLocalOptimisticStatus(mac, newStatus, ownerRole);
    queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
      applyDeviceStatus(old, mac, newStatus, ownerRole)
    );
    queryClient.setQueryData<ApiSystemState>(['system-state'], (old) =>
      applyDeviceStatusToSystemState(old, mac, newStatus, ownerRole)
    );
  }

  function patchDeviceInCache(updated: ApiDevice) {
    queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
      old?.map((d) => d.mac_address === updated.mac_address ? { ...d, ...updated } : d) ?? []
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
    mutationFn: ({ mac, ownerRole }: { mac: string; ownerRole: 'FAMILY' | 'GUEST' }) =>
      api.approveDevice(mac, ownerRole, role),
    onMutate: async ({ mac, ownerRole }) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ['devices'] }),
        queryClient.cancelQueries({ queryKey: ['system-state'] }),
      ]);
      const snapshot = {
        devices: queryClient.getQueryData<ApiDevice[]>(['devices']),
        systemState: queryClient.getQueryData<ApiSystemState>(['system-state']),
      };
      optimisticallyUpdateStatus(mac, 'AUTHORIZED', ownerRole as ApiDevice['owner_role']);
      return snapshot;
    },
    onSuccess: (updated) => patchDeviceInCache(updated),
    onError: (_error, { mac }, snapshot) => {
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
    mutationFn: (ownerRole: 'FAMILY' | 'GUEST') => api.approveAllPendingDevices(ownerRole, role),
    onMutate: async (ownerRole) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ['devices'] }),
        queryClient.cancelQueries({ queryKey: ['system-state'] }),
      ]);
      const snapshot = {
        devices: queryClient.getQueryData<ApiDevice[]>(['devices']),
        systemState: queryClient.getQueryData<ApiSystemState>(['system-state']),
      };
      queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
        old?.map((d) => d.status === 'PENDING' ? { ...d, status: 'AUTHORIZED', owner_role: ownerRole } : d) ?? []
      );
      setManyLocalOptimisticStatuses(
        (snapshot.devices ?? [])
          .filter((device) => device.status === 'PENDING')
          .map((device) => ({ mac: device.mac_address, status: 'AUTHORIZED', ownerRole }))
      );
      queryClient.setQueryData<ApiSystemState>(['system-state'], (old) => {
        if (!old) return old;
        return {
          ...old,
          present_devices: old.present_devices.map((d) =>
            d.status === 'PENDING' ? { ...d, status: 'AUTHORIZED', owner_role: ownerRole } : d
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
        .map((device) => {
          const patch = optimisticStatuses[device.mac_address.toUpperCase()];
          return mapDevice({
            ...device,
            status: patch?.status ?? device.status,
            owner_role: patch?.ownerRole !== undefined ? patch.ownerRole : device.owner_role,
          });
        }),
    [data, optimisticStatuses],
  );

  return (
    <DevicesContext.Provider
      value={{
        devices,
        isLoading,
        error: error as Error | null,
        approveDevice: (id, ownerRole) => {
          if (isAdmin) {
            optimisticallyUpdateStatus(id, 'AUTHORIZED', ownerRole as ApiDevice['owner_role']);
            approveMutation.mutate({ mac: id, ownerRole });
          }
        },
        approveAllUnknownDevices: (ownerRole) => {
          if (isAdmin) {
            setManyLocalOptimisticStatuses(
              (data ?? [])
                .filter(
                  (device) =>
                    (optimisticStatuses[device.mac_address.toUpperCase()]?.status ?? device.status) === 'PENDING'
                )
                .map((device) => ({
                  mac: device.mac_address,
                  status: 'AUTHORIZED',
                  ownerRole: ownerRole as ApiDevice['owner_role'],
                }))
            );
            approveAllMutation.mutate(ownerRole);
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
