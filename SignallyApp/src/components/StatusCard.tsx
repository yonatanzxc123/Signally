import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, font } from '../theme';

interface Props {
  hasUnknown: boolean;
}

export default function StatusCard({ hasUnknown }: Props) {
  const secure = !hasUnknown;

  return (
    <View style={[styles.card, secure ? styles.cardSecure : styles.cardAlert]}>
      <View style={[styles.iconWrap, secure ? styles.iconWrapSecure : styles.iconWrapAlert]}>
        <Ionicons
          name={secure ? 'shield-checkmark' : 'shield'}
          size={48}
          color={secure ? colors.secure : colors.alert}
        />
      </View>
      <Text style={[styles.label, secure ? styles.labelSecure : styles.labelAlert]}>
        STATUS
      </Text>
      <Text style={[styles.status, secure ? styles.statusSecure : styles.statusAlert]}>
        {secure ? 'SECURE' : 'ALERT'}
      </Text>
      <Text style={styles.sub}>
        {secure
          ? 'All devices on network are recognized'
          : 'Unknown device detected on your network'}
      </Text>
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
  cardSecure: { backgroundColor: colors.secureLight },
  cardAlert: { backgroundColor: colors.alertLight },
  iconWrap: {
    width: 88,
    height: 88,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  iconWrapSecure: { backgroundColor: '#BBF7D0' },
  iconWrapAlert: { backgroundColor: '#FECACA' },
  label: {
    fontSize: font.sm,
    fontWeight: '600',
    letterSpacing: 2,
    marginBottom: spacing.xs,
  },
  labelSecure: { color: colors.secure },
  labelAlert: { color: colors.alert },
  status: {
    fontSize: font.xxxl,
    fontWeight: '800',
    letterSpacing: 3,
    marginBottom: spacing.sm,
  },
  statusSecure: { color: colors.secure },
  statusAlert: { color: colors.alert },
  sub: {
    fontSize: font.md,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});
