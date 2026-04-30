import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { DevicesStackParamList } from '../navigation/DevicesStack';
import { useDevices } from '../context/DevicesContext';
import { api } from '../api/client';
import { colors, font, radius, spacing } from '../theme';

type Props = NativeStackScreenProps<DevicesStackParamList, 'DeviceDetail'>;

const STATUS_CONFIG = {
  approved: { label: 'Approved', color: colors.approved, bg: colors.approvedLight, icon: 'checkmark-circle' as const },
  unknown:  { label: 'Unknown',  color: colors.unknown,  bg: colors.unknownLight,  icon: 'help-circle' as const },
  blocked:  { label: 'Blocked',  color: colors.blocked,  bg: colors.blockedLight,  icon: 'ban' as const },
};

export default function DeviceDetailScreen({ route, navigation }: Props) {
  const { deviceId } = route.params;
  const { devices, approveDevice, blockDevice } = useDevices();
  const device = devices.find((d) => d.id === deviceId);

  const { data: probeInfo } = useQuery({
    queryKey: ['probeInfo', deviceId],
    queryFn: () => api.getDeviceProbeInfo(deviceId),
    retry: false,
    enabled: !!device,
  });

  if (!device) {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <Text style={styles.notFound}>Device not found.</Text>
      </SafeAreaView>
    );
  }

  const cfg = STATUS_CONFIG[device.status];

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color={colors.primary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Device Detail</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        <View style={styles.heroCard}>
          <View style={[styles.heroIcon, { backgroundColor: cfg.bg }]}>
            <Ionicons name="phone-portrait-outline" size={36} color={cfg.color} />
          </View>
          <Text style={styles.heroName}>{device.name}</Text>
          <Text style={styles.heroVendor}>{probeInfo?.vendor ?? device.vendor}</Text>
          <View style={[styles.badge, { backgroundColor: cfg.bg }]}>
            <Ionicons name={cfg.icon} size={13} color={cfg.color} />
            <Text style={[styles.badgeText, { color: cfg.color }]}>{cfg.label}</Text>
          </View>
          {!device.ip && (
            <View style={[styles.badge, { backgroundColor: '#EFF6FF', marginTop: 0 }]}>
              <Ionicons name="radio-outline" size={13} color={colors.accent} />
              <Text style={[styles.badgeText, { color: colors.accent }]}>Nearby · Not Connected</Text>
            </View>
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Network Info</Text>
          <InfoRow icon="hardware-chip-outline" label="MAC Address" value={device.mac} mono />
          <InfoRow icon="globe-outline" label="IP Address" value={device.ip || '—'} mono />
          <InfoRow icon="business-outline" label="Manufacturer" value={probeInfo?.vendor ?? device.vendor} />
          <InfoRow icon="time-outline" label="Last Seen" value={device.lastSeen} />
        </View>

        {probeInfo && (probeInfo.known_ssids.length > 0 || probeInfo.latest_rssi != null) && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Probe Details</Text>
            {probeInfo.latest_rssi != null && (
              <InfoRow
                icon="wifi-outline"
                label="Signal Strength"
                value={
                  probeInfo.latest_rssi >= -60
                    ? `Strong (${probeInfo.latest_rssi} dBm)`
                    : probeInfo.latest_rssi >= -75
                    ? `Medium (${probeInfo.latest_rssi} dBm)`
                    : `Weak (${probeInfo.latest_rssi} dBm)`
                }
              />
            )}
            {probeInfo.known_ssids.length > 0 && (
              <View style={styles.ssidsContainer}>
                <Text style={styles.ssidsLabel}>Known Networks</Text>
                <View style={styles.ssidsList}>
                  {probeInfo.known_ssids.map((ssid) => (
                    <View key={ssid} style={styles.ssidChip}>
                      <Ionicons name="wifi" size={12} color={colors.accent} />
                      <Text style={styles.ssidChipText}>{ssid}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
          </View>
        )}

        {device.status !== 'approved' && (
          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: colors.approvedLight }]}
            onPress={() => { approveDevice(device.id); navigation.goBack(); }}
          >
            <Ionicons name="checkmark-circle-outline" size={20} color={colors.approved} />
            <Text style={[styles.actionBtnText, { color: colors.approved }]}>Approve Device</Text>
          </TouchableOpacity>
        )}

        {device.status !== 'blocked' && (
          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: colors.blockedLight }]}
            onPress={() => { blockDevice(device.id); navigation.goBack(); }}
          >
            <Ionicons name="ban-outline" size={20} color={colors.blocked} />
            <Text style={[styles.actionBtnText, { color: colors.blocked }]}>Block Device</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function InfoRow({
  icon,
  label,
  value,
  mono = false,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <View style={styles.infoRow}>
      <Ionicons name={icon} size={18} color={colors.textSecondary} style={styles.infoIcon} />
      <View style={styles.infoText}>
        <Text style={styles.infoLabel}>{label}</Text>
        <Text style={[styles.infoValue, mono && styles.mono]}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: font.lg,
    fontWeight: '700',
    color: colors.primary,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
    gap: spacing.md,
  },
  heroCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    gap: spacing.sm,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  heroIcon: {
    width: 72,
    height: 72,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.xs,
  },
  heroName: {
    fontSize: font.xl,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  heroVendor: {
    fontSize: font.md,
    color: colors.textSecondary,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    marginTop: spacing.xs,
  },
  badgeText: {
    fontSize: font.sm,
    fontWeight: '600',
  },
  section: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  sectionTitle: {
    fontSize: font.md,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  infoIcon: {
    marginRight: spacing.md,
    marginTop: 2,
  },
  infoText: { flex: 1 },
  infoLabel: {
    fontSize: font.sm,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  infoValue: {
    fontSize: font.md,
    color: colors.textPrimary,
    fontWeight: '500',
  },
  mono: {
    fontFamily: 'monospace',
    fontSize: font.sm,
  },
  emptyHistory: {
    alignItems: 'center',
    paddingVertical: spacing.lg,
    gap: spacing.sm,
  },
  emptyText: {
    fontSize: font.sm,
    color: colors.textMuted,
    textAlign: 'center',
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  actionBtnText: {
    fontSize: font.lg,
    fontWeight: '600',
  },
  notFound: {
    textAlign: 'center',
    marginTop: spacing.xl,
    color: colors.textMuted,
    fontSize: font.lg,
  },
  ssidsContainer: {
    paddingVertical: spacing.sm,
  },
  ssidsLabel: {
    fontSize: font.sm,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  ssidsList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  ssidChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#EFF6FF',
    borderRadius: radius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  ssidChipText: {
    fontSize: font.sm,
    color: colors.accent,
    fontWeight: '500',
  },
});
