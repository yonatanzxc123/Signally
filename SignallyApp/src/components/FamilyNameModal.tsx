import React, { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radius, spacing } from '../theme';

type Props = {
  visible: boolean;
  initialName?: string;
  onCancel: () => void;
  onSave: (name: string) => void;
};

export default function FamilyNameModal({ visible, initialName = '', onCancel, onSave }: Props) {
  const [name, setName] = useState(initialName);

  useEffect(() => {
    if (visible) setName(initialName);
  }, [initialName, visible]);

  const cleaned = name.trim();
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <KeyboardAvoidingView style={styles.backdrop} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.dialog}>
          <View style={styles.headingRow}>
            <View style={styles.iconWrap}>
              <Ionicons name="person-outline" size={20} color={colors.approved} />
            </View>
            <View style={styles.headingText}>
              <Text style={styles.title}>Family member name</Text>
              <Text style={styles.subtitle}>Timeline entries will use this name.</Text>
            </View>
          </View>
          <TextInput
            value={name}
            onChangeText={setName}
            placeholder="e.g. Idan"
            placeholderTextColor={colors.textMuted}
            autoFocus
            maxLength={100}
            returnKeyType="done"
            onSubmitEditing={() => cleaned && onSave(cleaned)}
            style={styles.input}
          />
          <View style={styles.actions}>
            <TouchableOpacity style={styles.cancelButton} onPress={onCancel}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.saveButton, !cleaned && styles.disabled]}
              disabled={!cleaned}
              onPress={() => onSave(cleaned)}
            >
              <Text style={styles.saveText}>Save</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(13,13,43,0.45)', justifyContent: 'center', padding: spacing.lg },
  dialog: { backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.lg, gap: spacing.md },
  headingRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  iconWrap: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.approvedLight, alignItems: 'center', justifyContent: 'center' },
  headingText: { flex: 1 },
  title: { fontSize: font.lg, fontWeight: '700', color: colors.textPrimary },
  subtitle: { fontSize: font.sm, color: colors.textSecondary, marginTop: 2 },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: spacing.md, height: 48, color: colors.textPrimary, fontSize: font.lg },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: spacing.sm },
  cancelButton: { paddingHorizontal: spacing.md, height: 40, justifyContent: 'center' },
  cancelText: { color: colors.textSecondary, fontWeight: '600' },
  saveButton: { paddingHorizontal: spacing.lg, height: 40, justifyContent: 'center', borderRadius: radius.sm, backgroundColor: colors.primary },
  saveText: { color: colors.surface, fontWeight: '700' },
  disabled: { opacity: 0.4 },
});
