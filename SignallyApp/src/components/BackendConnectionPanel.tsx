import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { getApiBaseUrl, setApiBaseUrl, testApiConnection } from '../api/client';
import { colors, font, radius, spacing } from '../theme';

export default function BackendConnectionPanel() {
  const [url, setUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    getApiBaseUrl().then(setUrl);
  }, []);

  async function saveAndTest() {
    setTesting(true);
    setStatus(null);
    try {
      const saved = await setApiBaseUrl(url);
      setUrl(saved);
      await testApiConnection(saved);
      setStatus({ ok: true, message: 'Connected to Signally' });
    } catch (error) {
      setStatus({
        ok: false,
        message: error instanceof Error ? error.message : 'Could not reach the backend.',
      });
    } finally {
      setTesting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Backend address</Text>
      <View style={styles.controls}>
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={setUrl}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="http://10.12.194.1:8000"
          placeholderTextColor={colors.textMuted}
          accessibilityLabel="Backend address"
        />
        <TouchableOpacity
          style={styles.button}
          onPress={saveAndTest}
          disabled={testing}
          accessibilityRole="button"
          accessibilityLabel="Save and test backend connection"
        >
          {testing ? (
            <ActivityIndicator size="small" color={colors.surface} />
          ) : (
            <Ionicons name="git-network-outline" size={20} color={colors.surface} />
          )}
        </TouchableOpacity>
      </View>
      {status && (
        <View style={styles.statusRow}>
          <Ionicons
            name={status.ok ? 'checkmark-circle' : 'alert-circle'}
            size={16}
            color={status.ok ? colors.secure : colors.alert}
          />
          <Text style={[styles.statusText, { color: status.ok ? colors.secure : colors.alert }]}>
            {status.message}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.sm },
  label: { fontSize: font.sm, color: colors.textSecondary, fontWeight: '600' },
  controls: { flexDirection: 'row', gap: spacing.sm },
  input: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    fontSize: font.sm,
  },
  button: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    backgroundColor: colors.primary,
  },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  statusText: { flex: 1, fontSize: font.sm },
});
