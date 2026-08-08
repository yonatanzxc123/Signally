import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import StatusCard from '../components/StatusCard';
import LogItem from '../components/LogItem';
import { colors, spacing, radius, font } from '../theme';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../context/AuthContext';
import { useDevices } from '../context/DevicesContext';
import { useEvents } from '../context/EventsContext';
import { api, ApiSecurityMode, ApiSystemState } from '../api/client';

export default function HomeScreen() {
  const { logout, role } = useAuth();
  const navigation = useNavigation<any>();
  const { devices } = useDevices();
  const { events } = useEvents();
  const queryClient = useQueryClient();
  const [menuVisible, setMenuVisible] = useState(false);
  const [modeControlWidth, setModeControlWidth] = useState(0);
  const modeAnim = useRef(new Animated.Value(0)).current;

  const scanMutation = useMutation({
    mutationFn: api.runMonitoringCycle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['system-state'] });
    },
  });

  const securityModeMutation = useMutation({
    mutationFn: (mode: ApiSecurityMode) => api.setSecurityMode(mode, role),
    onMutate: async (mode) => {
      await queryClient.cancelQueries({ queryKey: ['system-state'] });
      const snapshot = queryClient.getQueryData<ApiSystemState>(['system-state']);
      const now = new Date().toISOString();
      queryClient.setQueryData<ApiSystemState>(['system-state'], (old) => {
        if (!old) return old;
        return {
          ...old,
          mode,
          security_mode: mode,
          security_mode_updated_by_role: role,
          security_mode_updated_at: now,
          decision:
            mode === 'HOME' && old.decision === 'ALERT'
              ? 'REVIEW'
              : old.decision,
          reason:
            mode === 'HOME' && old.decision === 'ALERT'
              ? 'Home mode is active. Unknown activity is queued for review.'
              : old.reason,
        };
      });
      return snapshot;
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<ApiSystemState>(['system-state'], (old) => {
        if (!old) return old;
        return {
          ...old,
          security_mode: updated.mode,
          security_mode_updated_by_role: updated.updated_by_role,
          security_mode_updated_at: updated.updated_at,
        };
      });
      queryClient.invalidateQueries({ queryKey: ['system-state'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
    onError: (_error, _mode, snapshot) => {
      queryClient.setQueryData(['system-state'], snapshot);
    },
  });

  const { data: systemState } = useQuery({
    queryKey: ['system-state'],
    queryFn: api.getSystemState,
    // CSI is processed continuously on the Pi; refresh its correlated UI state
    // quickly without tying this cadence to the slower ARP scan interval.
    refetchInterval: 1_000,
    refetchIntervalInBackground: true,
    retry: false,
  });

  const hasUnknown = devices.some((d) => d.status === 'unknown');
  const shouldNotifyRole =
    (systemState?.current_intruder_count ?? 0) > 0 &&
    (systemState?.notification_audience ?? []).includes(role);
  const recentEvents = events.slice(0, 5);
  const scanning = scanMutation.isPending;
  const securityMode = systemState?.security_mode ?? 'HOME';
  const canChangeSecurityMode = role === 'ADMIN' || role === 'FAMILY';
  const modeSegmentWidth = modeControlWidth > 0 ? (modeControlWidth - 8) / 2 : 0;

  useEffect(() => {
    Animated.timing(modeAnim, {
      toValue: securityMode === 'AWAY' ? 1 : 0,
      duration: 260,
      useNativeDriver: false,
    }).start();
  }, [modeAnim, securityMode]);

  const modeSliderTranslate = modeAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, modeSegmentWidth],
  });

  const modeSliderColor = modeAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [colors.accent, colors.secure],
  });

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
              onPress={() => { setMenuVisible(false); navigation.navigate('UserSettings'); }}
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
        <StatusCard
          hasUnknown={shouldNotifyRole || (!systemState && hasUnknown)}
          deviceCount={devices.length}
          securityMode={securityMode}
          decision={systemState?.decision}
        />

        <View style={styles.modePanel}>
          <View style={styles.modeHeader}>
            <View style={styles.modeTitleWrap}>
              <Text style={styles.modeTitle}>Security Mode</Text>
              <Text style={styles.modeMeta}>
                {securityMode === 'AWAY'
                  ? 'Armed for unknown activity'
                  : 'Relaxed for trusted presence'}
              </Text>
            </View>
            <View
              style={[
                styles.modeBadge,
                securityMode === 'AWAY' ? styles.modeBadgeAway : styles.modeBadgeHome,
              ]}
            >
              <Ionicons
                name={securityMode === 'AWAY' ? 'lock-closed-outline' : 'home-outline'}
                size={14}
                color={securityMode === 'AWAY' ? colors.secure : colors.accent}
              />
              <Text
                style={[
                  styles.modeBadgeText,
                  { color: securityMode === 'AWAY' ? colors.secure : colors.accent },
                ]}
              >
                {securityMode}
              </Text>
            </View>
          </View>

          <View
            style={styles.modeControls}
            onLayout={(e) => setModeControlWidth(e.nativeEvent.layout.width)}
          >
            {modeSegmentWidth > 0 && (
              <Animated.View
                pointerEvents="none"
                style={[
                  styles.modeSlider,
                  {
                    width: modeSegmentWidth,
                    backgroundColor: modeSliderColor,
                    transform: [{ translateX: modeSliderTranslate }],
                  },
                ]}
              />
            )}
            {(['HOME', 'AWAY'] as const).map((mode) => {
              const active = securityMode === mode;
              return (
                <TouchableOpacity
                  key={mode}
                  style={[
                    styles.modeButton,
                    !canChangeSecurityMode && styles.modeButtonDisabled,
                  ]}
                  disabled={!canChangeSecurityMode || active || securityModeMutation.isPending}
                  onPress={() => securityModeMutation.mutate(mode)}
                  activeOpacity={0.85}
                >
                  <Ionicons
                    name={mode === 'AWAY' ? 'shield-checkmark-outline' : 'home-outline'}
                    size={16}
                    color={active ? colors.surface : colors.textSecondary}
                  />
                  <Text style={[styles.modeButtonText, active && styles.modeButtonTextActive]}>
                    {mode === 'AWAY' ? 'Away' : 'Home'}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        <View style={styles.decisionPanel}>
          <View
            style={[
              styles.decisionIcon,
              systemState?.decision === 'ALERT'
                ? styles.decisionIconAlert
                : systemState?.decision === 'REVIEW'
                ? styles.decisionIconReview
                : styles.decisionIconSafe,
            ]}
          >
            <Ionicons
              name={
                systemState?.decision === 'ALERT'
                  ? 'warning-outline'
                  : systemState?.decision === 'REVIEW'
                  ? 'help-circle-outline'
                  : 'shield-checkmark-outline'
              }
              size={20}
              color={
                systemState?.decision === 'ALERT'
                  ? colors.alert
                  : systemState?.decision === 'REVIEW'
                  ? colors.unknown
                  : colors.approved
              }
            />
          </View>
          <View style={styles.decisionBody}>
            <View style={styles.decisionHeader}>
              <Text style={styles.decisionLabel}>Correlation</Text>
              <Text
                style={[
                  styles.decisionValue,
                  {
                    color:
                      systemState?.decision === 'ALERT'
                        ? colors.alert
                        : systemState?.decision === 'REVIEW'
                        ? colors.unknown
                        : colors.approved,
                  },
                ]}
              >
                {systemState?.decision ?? 'SAFE'}
              </Text>
            </View>
            <Text style={styles.decisionReason}>
              {systemState?.reason ?? 'Waiting for backend state.'}
            </Text>
            <Text style={styles.decisionMeta}>
              Unknown {systemState?.unknown_devices ?? 0} - Alerts {systemState?.recent_alerts?.length ?? 0}
            </Text>
            <Text style={styles.decisionMeta}>
              CSI {systemState?.csi?.ready
                ? systemState.csi.recently_detected ? 'motion' : 'online'
                : systemState?.csi?.receiving_data ? 'calibrating' : 'unavailable'}
              {' - '}Probe activity {systemState?.probe_activity_detected ? 'active' : 'quiet'}
              {' - '}ARP {systemState?.arp_scanner_healthy ? 'online' : 'stale'}
            </Text>
          </View>
        </View>

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
  modePanel: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  modeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  modeTitleWrap: {
    flex: 1,
  },
  modeTitle: {
    fontSize: font.lg,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  modeMeta: {
    fontSize: font.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  modeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
  },
  modeBadgeHome: {
    backgroundColor: '#DBEAFE',
  },
  modeBadgeAway: {
    backgroundColor: colors.secureLight,
  },
  modeBadgeText: {
    fontSize: font.sm,
    fontWeight: '800',
  },
  modeControls: {
    flexDirection: 'row',
    position: 'relative',
    minHeight: 48,
    borderRadius: radius.sm,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 4,
    overflow: 'hidden',
  },
  modeSlider: {
    position: 'absolute',
    top: 4,
    bottom: 4,
    left: 4,
    borderRadius: radius.sm - 2,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  modeButton: {
    flex: 1,
    minHeight: 40,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    borderRadius: radius.sm,
    zIndex: 1,
  },
  modeButtonDisabled: {
    opacity: 0.5,
  },
  modeButtonText: {
    fontSize: font.md,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  modeButtonTextActive: {
    color: colors.surface,
  },
  decisionPanel: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  decisionIcon: {
    width: 42,
    height: 42,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  decisionIconSafe: {
    backgroundColor: colors.approvedLight,
  },
  decisionIconReview: {
    backgroundColor: colors.unknownLight,
  },
  decisionIconAlert: {
    backgroundColor: colors.alertLight,
  },
  decisionBody: {
    flex: 1,
  },
  decisionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  decisionLabel: {
    fontSize: font.sm,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
  },
  decisionValue: {
    fontSize: font.md,
    fontWeight: '800',
  },
  decisionReason: {
    fontSize: font.md,
    color: colors.textPrimary,
    fontWeight: '500',
    marginBottom: spacing.xs,
  },
  decisionMeta: {
    fontSize: font.sm,
    color: colors.textMuted,
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
