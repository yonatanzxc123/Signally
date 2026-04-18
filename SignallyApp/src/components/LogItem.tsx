import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, font } from '../theme';
import { NetworkEvent, EventType, formatTimestamp } from '../mock/data';

interface Props {
  event: NetworkEvent;
}

type EventConfig = {
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  bg: string;
};

const EVENT_CONFIG: Record<EventType, EventConfig> = {
  unknown_detected: { icon: 'warning', color: colors.unknown, bg: colors.unknownLight },
  device_approved: { icon: 'checkmark-circle', color: colors.approved, bg: colors.approvedLight },
  device_blocked: { icon: 'ban', color: colors.blocked, bg: colors.blockedLight },
  scan_complete: { icon: 'scan', color: colors.accent, bg: '#DBEAFE' },
  system: { icon: 'shield', color: colors.textSecondary, bg: colors.divider },
};

export default function LogItem({ event }: Props) {
  const cfg = EVENT_CONFIG[event.type];

  return (
    <View style={styles.row}>
      <View style={[styles.iconWrap, { backgroundColor: cfg.bg }]}>
        <Ionicons name={cfg.icon} size={16} color={cfg.color} />
      </View>
      <View style={styles.content}>
        <Text style={styles.message}>{event.message}</Text>
        <Text style={styles.detail}>{event.detail}</Text>
      </View>
      <Text style={styles.time}>{formatTimestamp(event.timestamp)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
    marginTop: 2,
  },
  content: { flex: 1 },
  message: {
    fontSize: font.md,
    fontWeight: '500',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  detail: {
    fontSize: font.sm,
    color: colors.textSecondary,
    fontFamily: 'monospace',
  },
  time: {
    fontSize: font.sm,
    color: colors.textMuted,
    marginLeft: spacing.sm,
    marginTop: 2,
  },
});
