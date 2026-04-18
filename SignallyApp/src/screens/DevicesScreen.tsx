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
import { DeviceStatus } from '../mock/data';
import { colors, spacing, radius, font } from '../theme';
import { useDevices } from '../context/DevicesContext';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { DevicesStackParamList } from '../navigation/DevicesStack';

type Props = NativeStackScreenProps<DevicesStackParamList, 'DevicesList'>;

type Filter = 'all' | DeviceStatus;

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'approved', label: 'Approved' },
  { key: 'unknown', label: 'Unknown' },
  { key: 'blocked', label: 'Blocked' },
];

export default function DevicesScreen({ navigation }: Props) {
  const { devices, approveDevice, blockDevice } = useDevices();
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = filter === 'all' ? devices : devices.filter((d) => d.status === filter);

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
        bounces={false}
      >
        {filtered.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons
              name={devices.length === 0 ? 'radio-outline' : 'phone-portrait-outline'}
              size={48}
              color={colors.textMuted}
            />
            <Text style={styles.emptyTitle}>
              {devices.length === 0 ? 'No devices detected' : `No ${filter} devices`}
            </Text>
            <Text style={styles.emptyText}>
              {devices.length === 0
                ? 'Run a scan from the Home tab to discover devices on your network.'
                : `You have no devices with ${filter} status.`}
            </Text>
          </View>
        ) : (
          filtered.map((device) => (
            <DeviceItem
              key={device.id}
              device={device}
              onApprove={approveDevice}
              onBlock={blockDevice}
              onPress={(id) => navigation.navigate('DeviceDetail', { deviceId: id })}
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
  emptyTitle: {
    fontSize: font.lg,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  emptyText: {
    fontSize: font.md,
    color: colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: spacing.lg,
  },
});
