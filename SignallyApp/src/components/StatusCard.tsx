import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, font } from '../theme';

interface Props {
  hasUnknown: boolean;
  deviceCount: number;
}

export default function StatusCard({ hasUnknown, deviceCount }: Props) {
  const noDevices = deviceCount === 0;
  const secure = !hasUnknown && !noDevices;

  const config = noDevices
    ? {
        icon: 'radio-outline' as const,
        iconColor: colors.textMuted,
        iconBg: colors.divider,
        cardBg: colors.surface,
        labelColor: colors.textMuted,
        label: 'STATUS',
        statusText: 'OFFLINE',
        statusColor: colors.textMuted,
        sub: 'No devices detected — start a scan to monitor your network',
      }
    : secure
    ? {
        icon: 'shield-checkmark' as const,
        iconColor: colors.secure,
        iconBg: '#BBF7D0',
        cardBg: colors.secureLight,
        labelColor: colors.secure,
        label: 'STATUS',
        statusText: 'SECURE',
        statusColor: colors.secure,
        sub: 'All devices on network are recognized',
      }
    : {
        icon: 'shield' as const,
        iconColor: colors.alert,
        iconBg: '#FECACA',
        cardBg: colors.alertLight,
        labelColor: colors.alert,
        label: 'STATUS',
        statusText: 'ALERT',
        statusColor: colors.alert,
        sub: 'Unknown device detected on your network',
      };

  return (
    <View style={[styles.card, { backgroundColor: config.cardBg }]}>
      <View style={[styles.iconWrap, { backgroundColor: config.iconBg }]}>
        <Ionicons name={config.icon} size={48} color={config.iconColor} />
      </View>
      <Text style={[styles.label, { color: config.labelColor }]}>{config.label}</Text>
      <Text style={[styles.status, { color: config.statusColor }]}>{config.statusText}</Text>
      <Text style={styles.sub}>{config.sub}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  iconWrap: {
    width: 88,
    height: 88,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  label: {
    fontSize: font.sm,
    fontWeight: '600',
    letterSpacing: 2,
    marginBottom: spacing.xs,
  },
  status: {
    fontSize: font.xxxl,
    fontWeight: '800',
    letterSpacing: 3,
    marginBottom: spacing.sm,
  },
  sub: {
    fontSize: font.md,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});
