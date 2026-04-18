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
import LogItem from '../components/LogItem';
import { MOCK_EVENTS, NetworkEvent, EventType } from '../mock/data';
import { colors, spacing, radius, font } from '../theme';

type Filter = 'all' | EventType;

const FILTERS: { key: Filter; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: 'all', label: 'All', icon: 'list' },
  { key: 'unknown_detected', label: 'Alerts', icon: 'warning' },
  { key: 'device_approved', label: 'Approved', icon: 'checkmark-circle' },
  { key: 'device_blocked', label: 'Blocked', icon: 'ban' },
  { key: 'scan_complete', label: 'Scans', icon: 'scan' },
];

export default function LogsScreen() {
  const [events] = useState<NetworkEvent[]>(MOCK_EVENTS);
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = filter === 'all' ? events : events.filter((e) => e.type === filter);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Activity Logs</Text>
        <View style={styles.headerCount}>
          <Text style={styles.headerCountText}>{events.length}</Text>
        </View>
      </View>

      <ScrollView
        horizontal
        style={styles.filterScroll}
        contentContainerStyle={styles.filterBar}
        showsHorizontalScrollIndicator={false}
      >
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterChip, filter === f.key && styles.filterChipActive]}
            onPress={() => setFilter(f.key)}
          >
            <Ionicons
              name={f.icon}
              size={13}
              color={filter === f.key ? colors.surface : colors.textSecondary}
            />
            <Text style={[styles.filterText, filter === f.key && styles.filterTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.card}>
          {filtered.length === 0 ? (
            <View style={styles.empty}>
              <Ionicons name="document-text-outline" size={40} color={colors.textMuted} />
              <Text style={styles.emptyText}>No events found</Text>
            </View>
          ) : (
            filtered.map((event) => (
              <LogItem key={event.id} event={event} />
            ))
          )}
        </View>
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
  filterScroll: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    maxHeight: 52,
  },
  filterBar: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radius.full,
    backgroundColor: colors.background,
    gap: 4,
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
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  empty: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
    gap: spacing.md,
  },
  emptyText: {
    fontSize: font.lg,
    color: colors.textMuted,
  },
});
