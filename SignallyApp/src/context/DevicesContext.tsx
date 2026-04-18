import React, { createContext, useContext, useState } from 'react';
import { MOCK_DEVICES, Device, DeviceStatus } from '../mock/data';

interface DevicesContextValue {
  devices: Device[];
  approveDevice: (id: string) => void;
  blockDevice: (id: string) => void;
}

const DevicesContext = createContext<DevicesContextValue | null>(null);

export function DevicesProvider({ children }: { children: React.ReactNode }) {
  // TODO: replace with GET /devices — poll or websocket for live updates
  const [devices, setDevices] = useState<Device[]>(MOCK_DEVICES);

  function approveDevice(id: string) {
    // TODO: replace with PATCH /devices/:id { status: 'approved' }
    setDevices((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: 'approved' as DeviceStatus } : d))
    );
  }

  function blockDevice(id: string) {
    // TODO: replace with PATCH /devices/:id { status: 'blocked' } — backend should also enforce network block
    setDevices((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: 'blocked' as DeviceStatus } : d))
    );
  }

  return (
    <DevicesContext.Provider value={{ devices, approveDevice, blockDevice }}>
      {children}
    </DevicesContext.Provider>
  );
}

export function useDevices() {
  const ctx = useContext(DevicesContext);
  if (!ctx) throw new Error('useDevices must be used inside DevicesProvider');
  return ctx;
}
