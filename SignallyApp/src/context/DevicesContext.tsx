import React, { createContext, useContext } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiDevice } from '../api/client';
import { Device, DeviceStatus, formatTimestamp } from '../types';

interface DevicesContextValue {
  devices: Device[];
  isLoading: boolean;
  error: Error | null;
  approveDevice: (id: string) => void;
  blockDevice: (id: string) => void;
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
    name: 'Unknown Device',
    ip: d.ip_address,
    status: statusMap[d.status] ?? 'unknown',
    lastSeen: formatTimestamp(new Date(d.last_seen)),
    vendor: 'Unknown',
  };
}

export function DevicesProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['devices'],
    queryFn: api.getDevices,
    refetchInterval: 15_000,
    refetchIntervalInBackground: true,
    retry: 2,
    retryDelay: 3_000,
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
    mutationFn: (mac: string) => api.approveDevice(mac),
    onMutate: (mac) => optimisticallyUpdateStatus(mac, 'AUTHORIZED'),
    onSuccess: (updated) => patchDeviceInCache(updated),
    onError: () => queryClient.invalidateQueries({ queryKey: ['devices'] }),
  });

  const blockMutation = useMutation({
    mutationFn: (mac: string) => api.blockDevice(mac),
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
        approveDevice: (id) => approveMutation.mutate(id),
        blockDevice: (id) => blockMutation.mutate(id),
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
