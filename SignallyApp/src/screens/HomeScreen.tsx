import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
  Pressable,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import StatusCard from '../components/StatusCard';
import LogItem from '../components/LogItem';
import { colors, spacing, radius, font } from '../theme';
import { useAuth } from '../context/AuthContext';
import { useDevices } from '../context/DevicesContext';
import { useEvents } from '../context/EventsContext';
import { api } from '../api/client';

export default function HomeScreen() {
  const { logout } = useAuth();
  const { devices } = useDevices();
  const { events } = useEvents();
  const queryClient = useQueryClient();
  const [menuVisible, setMenuVisible] = useState(false);

  // TEMPORARY: replace api.scanNetwork with api.runMonitoringCycle once Raspberry Pi is integrated.
  const scanMutation = useMutation({
    mutationFn: api.scanNetwork,
    onSuccess: () => {
      queryClient.refetchQueries({ queryKey: ['devices'] });
      queryClient.refetchQueries({ queryKey: ['events'] });
    },
  });

  const hasUnknown = devices.some((d) => d.status === 'unknown');
  const recentEvents = events.slice(0, 5);
  const scanning = scanMutation.isPending;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Signally</Text>
        <TouchableOpacity style={styles.avatar} onPress={() => setMenuVisible(true)}>
          <Ionicons name="person-outline" size={20} color={colors.primary} />
        </TouchableOpacity>
      </View>

      <Modal
        visible={menuVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setMenuVisible(false)}
      >
        <Pressable style={styles.menuOverlay} onPress={() => setMenuVisible(false)}>
          <View style={styles.menuCard}>
            <TouchableOpacity
              style={styles.menuItem}
              onPress={() => setMenuVisible(false)}
            >
              <Ionicons name="person-circle-outline" size={20} color={colors.primary} />
              <Text style={styles.menuItemText}>User Settings</Text>
            </TouchableOpacity>
            <View style={styles.menuDivider} />
            <TouchableOpacity
              style={styles.menuItem}
              onPress={() => {
                setMenuVisible(false);
                logout();
              }}
            >
              <Ionicons name="log-out-outline" size={20} color={colors.alert} />
              <Text style={[styles.menuItemText, { color: colors.alert }]}>Log Out</Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </Modal>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        <StatusCard hasUnknown={hasUnknown} deviceCount={devices.length} />

        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statNumber}>{devices.length}</Text>
            <Text style={styles.statLabel}>Total Devices</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={[styles.statNumber, { color: colors.approved }]}>
              {devices.filter((d) => d.status === 'approved').length}
            </Text>
            <Text style={styles.statLabel}>Approved</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={[styles.statNumber, { color: colors.unknown }]}>
              {devices.filter((d) => d.status === 'unknown').length}
            </Text>
            <Text style={styles.statLabel}>Unknown</Text>
          </View>
        </View>

        <TouchableOpacity
          style={[styles.scanBtn, scanning && styles.scanBtnActive]}
          onPress={() => scanMutation.mutate()}
          disabled={scanning}
        >
          {scanning ? (
            <ActivityIndicator size="small" color={colors.surface} />
          ) : (
            <Ionicons name="scan" size={18} color={colors.surface} />
          )}
          <Text style={styles.scanBtnText}>
            {scanning ? 'Scanning network...' : 'Scan Network'}
          </Text>
        </TouchableOpacity>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent Activity</Text>
          {recentEvents.length === 0 ? (
            <View style={styles.emptyActivity}>
              <Ionicons name="radio-outline" size={28} color={colors.textMuted} />
              <Text style={styles.emptyActivityText}>No activity yet — events will appear here once your network is being monitored.</Text>
            </View>
          ) : (
            recentEvents.map((event, i) => (
              <LogItem key={event.id ?? i} event={event} />
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
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: {
    fontSize: font.xxl,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: 0.5,
  },
  avatar: {
    width: 38,
    height: 38,
    borderRadius: radius.full,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.2)',
    justifyContent: 'flex-start',
    alignItems: 'flex-end',
    paddingTop: 80,
    paddingRight: spacing.md,
  },
  menuCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingVertical: spacing.xs,
    minWidth: 180,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
  },
  menuItemText: {
    fontSize: font.lg,
    fontWeight: '500',
    color: colors.textPrimary,
  },
  menuDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginHorizontal: spacing.sm,
  },
  scroll: { flex: 1 },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xl,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  statNumber: {
    fontSize: font.xxl,
    fontWeight: '700',
    color: colors.primary,
  },
  statLabel: {
    fontSize: font.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  scanBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  scanBtnActive: {
    opacity: 0.7,
  },
  scanBtnText: {
    color: colors.surface,
    fontSize: font.lg,
    fontWeight: '600',
  },
  section: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  sectionTitle: {
    fontSize: font.lg,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  emptyActivity: {
    alignItems: 'center',
    paddingVertical: spacing.lg,
    gap: spacing.sm,
  },
  emptyActivityText: {
    fontSize: font.sm,
    color: colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: spacing.md,
  },
});
