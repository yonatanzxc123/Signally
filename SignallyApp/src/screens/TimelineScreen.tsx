import React from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { api, ApiTimelineEvent } from '../api/client';
import { colors, font, radius, spacing } from '../theme';

function dayLabel(value: string): string {
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return 'Today';
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return date.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
}

function TimelineItem({ event, last }: { event: ApiTimelineEvent; last: boolean }) {
  const entered = event.event_type === 'FAMILY_MEMBER_ENTERED';
  const name = event.details.replace(/ (entered|left) home$/, '');
  return (
    <View style={styles.item}>
      <View style={styles.rail}>
        <View style={[styles.marker, { backgroundColor: entered ? colors.approved : colors.accent }]}>
          <Ionicons name={entered ? 'log-in-outline' : 'log-out-outline'} size={15} color={colors.surface} />
        </View>
        {!last && <View style={styles.line} />}
      </View>
      <View style={styles.itemBody}>
        <View style={styles.itemTitleRow}>
          <Text style={styles.memberName}>{name}</Text>
          <Text style={styles.time}>
            {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Text>
        </View>
        <Text style={[styles.action, { color: entered ? colors.approved : colors.accent }]}>
          {entered ? 'Arrived home' : 'Left home'}
        </Text>
      </View>
    </View>
  );
}

export default function TimelineScreen() {
  const query = useQuery({
    queryKey: ['timeline'],
    queryFn: () => api.getTimeline(200),
    refetchInterval: 10_000,
    refetchIntervalInBackground: true,
    retry: false,
  });
  const events = query.data ?? [];
  const groups = events.reduce<Array<{ label: string; events: ApiTimelineEvent[] }>>((all, event) => {
    const label = dayLabel(event.created_at);
    const current = all[all.length - 1];
    if (current?.label === label) current.events.push(event);
    else all.push({ label, events: [event] });
    return all;
  }, []);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Family Timeline</Text>
        <View style={styles.headerCount}><Text style={styles.headerCountText}>{events.length}</Text></View>
      </View>
      {query.isLoading ? (
        <View style={styles.center}><ActivityIndicator color={colors.primary} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={() => query.refetch()} />}
        >
          {query.error ? (
            <View style={styles.empty}>
              <Ionicons name="cloud-offline-outline" size={44} color={colors.textMuted} />
              <Text style={styles.emptyTitle}>Timeline unavailable</Text>
              <Text style={styles.emptyText}>{(query.error as Error).message}</Text>
            </View>
          ) : groups.length === 0 ? (
            <View style={styles.empty}>
              <Ionicons name="time-outline" size={48} color={colors.textMuted} />
              <Text style={styles.emptyTitle}>No presence history yet</Text>
              <Text style={styles.emptyText}>Name an approved family device to begin tracking arrivals and departures.</Text>
            </View>
          ) : groups.map((group) => (
            <View key={group.label} style={styles.group}>
              <Text style={styles.day}>{group.label}</Text>
              <View style={styles.groupBody}>
                {group.events.map((event, index) => (
                  <TimelineItem key={event.id} event={event} last={index === group.events.length - 1} />
                ))}
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.md, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  title: { fontSize: font.xxl, fontWeight: '800', color: colors.primary },
  headerCount: { backgroundColor: colors.primary, borderRadius: radius.full, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  headerCountText: { color: colors.surface, fontSize: font.sm, fontWeight: '700' },
  content: { padding: spacing.md, paddingBottom: spacing.xl },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  group: { marginBottom: spacing.lg },
  day: { fontSize: font.sm, fontWeight: '700', color: colors.textSecondary, marginBottom: spacing.sm, textTransform: 'uppercase' },
  groupBody: { backgroundColor: colors.surface, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingTop: spacing.md },
  item: { flexDirection: 'row', minHeight: 72 },
  rail: { width: 36, alignItems: 'center' },
  marker: { width: 30, height: 30, borderRadius: radius.full, alignItems: 'center', justifyContent: 'center', zIndex: 1 },
  line: { width: 2, flex: 1, backgroundColor: colors.border },
  itemBody: { flex: 1, paddingLeft: spacing.sm, paddingBottom: spacing.md },
  itemTitleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  memberName: { flex: 1, fontSize: font.lg, fontWeight: '700', color: colors.textPrimary },
  time: { fontSize: font.sm, color: colors.textMuted },
  action: { fontSize: font.md, fontWeight: '600', marginTop: 4 },
  empty: { alignItems: 'center', paddingTop: spacing.xl * 2, gap: spacing.md },
  emptyTitle: { fontSize: font.lg, fontWeight: '600', color: colors.textSecondary },
  emptyText: { fontSize: font.md, color: colors.textMuted, textAlign: 'center', paddingHorizontal: spacing.lg },
});
