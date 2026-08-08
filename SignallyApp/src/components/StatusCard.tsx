import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, font } from '../theme';

interface Props {
  hasUnknown: boolean;
  deviceCount: number;
  securityMode?: 'HOME' | 'AWAY';
  decision?: string;
}

export default function StatusCard({
  hasUnknown,
  deviceCount,
  securityMode = 'HOME',
  decision,
}: Props) {
  const normalizedDecision = decision ?? (hasUnknown ? 'ALERT' : 'SAFE');
  // CSI/probe evidence can produce a real decision without creating a device
  // record. Never let the empty-device placeholder hide REVIEW or ALERT.
  const noDevices = deviceCount === 0 && normalizedDecision === 'SAFE';
  const secure = normalizedDecision === 'SAFE' && !noDevices;
  const review = normalizedDecision === 'REVIEW';

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
        sub: 'No devices detected - start a scan to monitor your network',
      }
    : securityMode === 'AWAY' && secure
    ? {
        icon: 'shield-checkmark' as const,
        iconColor: colors.secure,
        iconBg: '#BBF7D0',
        cardBg: colors.secureLight,
        labelColor: colors.secure,
        label: 'AWAY MODE',
        statusText: 'ARMED',
        statusColor: colors.secure,
        sub: 'Home is armed and monitoring for unknown activity',
      }
    : securityMode === 'HOME' && secure
    ? {
        icon: 'home-outline' as const,
        iconColor: colors.accent,
        iconBg: '#DBEAFE',
        cardBg: colors.surface,
        labelColor: colors.accent,
        label: 'HOME MODE',
        statusText: 'RELAXED',
        statusColor: colors.accent,
        sub: 'Trusted household presence is expected',
      }
    : review
    ? {
        icon: 'help-circle' as const,
        iconColor: colors.unknown,
        iconBg: colors.unknownLight,
        cardBg: colors.unknownLight,
        labelColor: colors.unknown,
        label: securityMode === 'AWAY' ? 'AWAY MODE' : 'HOME MODE',
        statusText: 'REVIEW',
        statusColor: colors.unknown,
        sub:
          securityMode === 'AWAY'
            ? 'Suspicious activity is in the review window'
            : 'Unknown activity is queued for review',
      }
    : {
        icon: 'shield' as const,
        iconColor: colors.alert,
        iconBg: '#FECACA',
        cardBg: colors.alertLight,
        labelColor: colors.alert,
        label: securityMode === 'AWAY' ? 'AWAY MODE' : 'HOME MODE',
        statusText: securityMode === 'AWAY' ? 'ALERT' : 'REVIEW',
        statusColor: colors.alert,
        sub:
          securityMode === 'AWAY'
            ? 'Unknown device detected while armed'
            : 'Unknown device detected while Home mode is active',
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
