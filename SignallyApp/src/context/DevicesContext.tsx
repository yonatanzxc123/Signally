import React, { createContext, useContext } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiDevice } from '../api/client';
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

function mapDevice(d: ApiDevice): Device {
  const statusMap: Record<string, DeviceStatus> = {
    PENDING: 'unknown',
    AUTHORIZED: 'approved',
    BLOCKED: 'blocked',
  };
  return {
    id: d.mac_address,
    mac: d.mac_address,
    name: d.owner_name ?? d.fingerprint?.display_name ?? 'Unknown Device',
    ip: d.ip_address,
    status: statusMap[d.status] ?? 'unknown',
    lastSeen: formatTimestamp(new Date(d.last_seen)),
    vendor: d.fingerprint?.manufacturer ?? 'Unknown',
    category: d.fingerprint?.device_category ?? 'UNKNOWN',
    confidence: d.fingerprint?.confidence ?? 0,
    randomizedMac: d.fingerprint?.randomized_mac ?? false,
    primaryLayer: d.fingerprint?.primary_layer ?? (d.ip_address ? 'ARP' : 'PROBING'),
    connected: d.fingerprint?.connected ?? !!d.ip_address,
    fingerprintSignals: d.fingerprint?.signals ?? [],
  };
}

export function DevicesProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const { role, isAdmin } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ['devices'],
    queryFn: api.getDevices,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    retry: false,
  });

  function optimisticallyUpdateStatus(mac: string, newStatus: ApiDevice['status']) {
    queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
      old?.map((d) => d.mac_address === mac ? { ...d, status: newStatus } : d) ?? []
    );
  }

  function patchDeviceInCache(updated: ApiDevice) {
    queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
      old?.map((d) => d.mac_address === updated.mac_address ? { ...d, status: updated.status } : d) ?? []
    );
  }

  const approveMutation = useMutation({
    mutationFn: (mac: string) => api.approveDevice(mac, role),
    onMutate: (mac) => optimisticallyUpdateStatus(mac, 'AUTHORIZED'),
    onSuccess: (updated) => patchDeviceInCache(updated),
    onError: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  });

  const approveAllMutation = useMutation({
    mutationFn: () => api.approveAllPendingDevices(role),
    onMutate: () => {
      queryClient.setQueryData<ApiDevice[]>(['devices'], (old) =>
        old?.map((d) => d.status === 'PENDING' ? { ...d, status: 'AUTHORIZED' } : d) ?? []
      );
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<ApiDevice[]>(['devices'], (old) => {
        const updates = new Map(updated.map((d) => [d.mac_address, d]));
        return old?.map((d) => updates.get(d.mac_address) ?? d) ?? updated;
      });
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  });

  const blockMutation = useMutation({
    mutationFn: (mac: string) => api.blockDevice(mac, role),
    onMutate: (mac) => optimisticallyUpdateStatus(mac, 'BLOCKED'),
    onSuccess: (updated) => patchDeviceInCache(updated),
    onError: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  });

  const devices = (data ?? []).map(mapDevice);

  return (
    <DevicesContext.Provider
      value={{
        devices,
        isLoading,
        error: error as Error | null,
        approveDevice: (id) => {
          if (isAdmin) approveMutation.mutate(id);
        },
        approveAllUnknownDevices: () => {
          if (isAdmin) approveAllMutation.mutate();
        },
        blockDevice: (id) => {
          if (isAdmin) blockMutation.mutate(id);
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
