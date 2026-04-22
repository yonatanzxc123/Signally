import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, font } from '../theme';
import { Device } from '../types';

interface Props {
  device: Device;
  onApprove: (id: string) => void;
  onBlock: (id: string) => void;
  onPress?: (id: string) => void;
}

type StatusConfig = {
  label: string;
  color: string;
  bg: string;
  icon: keyof typeof Ionicons.glyphMap;
};

const STATUS_CONFIG: Record<string, StatusConfig> = {
  approved: {
    label: 'Approved',
    color: colors.approved,
    bg: colors.approvedLight,
    icon: 'checkmark-circle',
  },
  unknown: {
    label: 'Unknown',
    color: colors.unknown,
    bg: colors.unknownLight,
    icon: 'help-circle',
  },
  blocked: {
    label: 'Blocked',
    color: colors.blocked,
    bg: colors.blockedLight,
    icon: 'ban',
  },
};

export default function DeviceItem({ device, onApprove, onBlock, onPress }: Props) {
  const cfg = STATUS_CONFIG[device.status];

  return (
    <TouchableOpacity style={styles.card} onPress={() => onPress?.(device.id)} activeOpacity={onPress ? 0.7 : 1}>
      <View style={styles.row}>
        <View style={[styles.iconWrap, { backgroundColor: cfg.bg }]}>
          <Ionicons name="phone-portrait-outline" size={20} color={cfg.color} />
        </View>
        <View style={styles.info}>
          <Text style={styles.name}>{device.name}</Text>
          <Text style={styles.mac}>{device.mac}</Text>
          <Text style={styles.meta}>{device.ip} · {device.lastSeen}</Text>
        </View>
        <View style={[styles.badge, { backgroundColor: cfg.bg }]}>
          <Ionicons name={cfg.icon} size={12} color={cfg.color} style={styles.badgeIcon} />
          <Text style={[styles.badgeText, { color: cfg.color }]}>{cfg.label}</Text>
        </View>
      </View>

      {device.status === 'unknown' && (
        <View style={styles.actions}>
          <TouchableOpacity
            style={[styles.btn, styles.btnApprove]}
            onPress={() => onApprove(device.id)}
          >
            <Ionicons name="checkmark" size={14} color={colors.approved} />
            <Text style={[styles.btnText, { color: colors.approved }]}>Approve</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnBlock]}
            onPress={() => onBlock(device.id)}
          >
            <Ionicons name="ban" size={14} color={colors.blocked} />
            <Text style={[styles.btnText, { color: colors.blocked }]}>Block</Text>
          </TouchableOpacity>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  info: { flex: 1 },
  name: {
    fontSize: font.md,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  mac: {
    fontSize: font.sm,
    color: colors.textSecondary,
    fontFamily: 'monospace',
    marginBottom: 2,
  },
  meta: {
    fontSize: font.sm,
    color: colors.textMuted,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
  },
  badgeIcon: { marginRight: 3 },
  badgeText: {
    fontSize: font.sm,
    fontWeight: '600',
  },
  actions: {
    flexDirection: 'row',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    gap: spacing.sm,
  },
  btn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    gap: 4,
  },
  btnApprove: { backgroundColor: colors.approvedLight },
  btnBlock: { backgroundColor: colors.blockedLight },
  btnText: {
    fontSize: font.sm,
    fontWeight: '600',
  },
});
