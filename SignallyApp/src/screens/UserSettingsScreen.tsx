import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { colors, font, radius, spacing } from '../theme';
import { useAuth } from '../context/AuthContext';

export default function UserSettingsScreen() {
  const { user } = useAuth();
  const navigation = useNavigation();

  const roleLabel = user?.role === 'ADMIN' ? 'Admin' : user?.role === 'FAMILY' ? 'Family Member' : user?.role ?? '—';

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={24} color={colors.primary} />
        </TouchableOpacity>
        <Text style={styles.title}>User Settings</Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={styles.card}>
        <Row icon="person-outline" label="Name" value={user?.displayName ?? '—'} />
        <Divider />
        <Row icon="mail-outline" label="Email" value={user?.email ?? '—'} />
        <Divider />
        <Row icon="shield-checkmark-outline" label="Role" value={roleLabel} />
      </View>
    </SafeAreaView>
  );
}

function Row({ icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={20} color={colors.primary} style={styles.rowIcon} />
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

function Divider() {
  return <View style={styles.divider} />;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  backBtn: { width: 40, alignItems: 'flex-start' },
  title: { fontSize: font.lg, fontWeight: '700', color: colors.textPrimary },
  card: {
    margin: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: 16,
  },
  rowIcon: { marginRight: spacing.md },
  rowLabel: { flex: 1, fontSize: font.md, color: colors.textSecondary, fontWeight: '600' },
  rowValue: { fontSize: font.md, color: colors.textPrimary, fontWeight: '500' },
  divider: { height: 1, backgroundColor: colors.border, marginLeft: spacing.lg + 20 + spacing.md },
});
