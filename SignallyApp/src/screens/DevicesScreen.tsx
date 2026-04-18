import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import DeviceItem from '../components/DeviceItem';
import { MOCK_DEVICES, Device, DeviceStatus } from '../mock/data';
import { colors, spacing, radius, font } from '../theme';

type Filter = 'all' | DeviceStatus;

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'approved', label: 'Approved' },
  { key: 'unknown', label: 'Unknown' },
  { key: 'blocked', label: 'Blocked' },
];

export default function DevicesScreen() {
  const [devices, setDevices] = useState<Device[]>(MOCK_DEVICES);
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = filter === 'all' ? devices : devices.filter((d) => d.status === filter);

  function handleApprove(id: string) {
    setDevices((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: 'approved' as DeviceStatus } : d))
    );
  }

  function handleBlock(id: string) {
    setDevices((prev) =>
      prev.map((d) => (d.id === id ? { ...d, status: 'blocked' as DeviceStatus } : d))
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Devices</Text>
        <View style={styles.headerCount}>
          <Text style={styles.headerCountText}>{devices.length}</Text>
        </View>
      </View>

      <View style={styles.filterBar}>
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterChip, filter === f.key && styles.filterChipActive]}
            onPress={() => setFilter(f.key)}
          >
            <Text style={[styles.filterText, filter === f.key && styles.filterTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {filtered.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="phone-portrait-outline" size={40} color={colors.textMuted} />
            <Text style={styles.emptyText}>No devices found</Text>
          </View>
        ) : (
          filtered.map((device) => (
            <DeviceItem
              key={device.id}
              device={device}
              onApprove={handleApprove}
              onBlock={handleBlock}
            />
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  title: {
    fontSize: font.xxl,
    fontWeight: '800',
    color: colors.primary,
  },
  headerCount: {
    backgroundColor: colors.primary,
    borderRadius: radius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  headerCountText: {
    color: colors.surface,
    fontSize: font.sm,
    fontWeight: '700',
  },
  filterBar: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: spacing.sm,
  },
  filterChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radius.full,
    backgroundColor: colors.background,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
  },
  filterText: {
    fontSize: font.sm,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  filterTextActive: {
    color: colors.surface,
  },
  scroll: { flex: 1 },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  empty: {
    alignItems: 'center',
    paddingTop: spacing.xl * 2,
    gap: spacing.md,
  },
  emptyText: {
    fontSize: font.lg,
    color: colors.textMuted,
  },
});
