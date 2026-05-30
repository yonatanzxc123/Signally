import React, { useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radius, spacing } from '../theme';

interface Props {
  onAuth: () => void;
}

export default function AuthScreen({ onAuth }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [toggleWidth, setToggleWidth] = useState(0);

  const slideAnim = useRef(new Animated.Value(0)).current;
  const formOpacity = useRef(new Animated.Value(1)).current;
  const formTranslate = useRef(new Animated.Value(0)).current;

  function switchMode(next: 'login' | 'signup') {
    if (next === mode) return;
    const toSignup = next === 'signup';

    Animated.spring(slideAnim, {
      toValue: toSignup ? 1 : 0,
      useNativeDriver: false,
      tension: 300,
      friction: 30,
    }).start();

    const exitX = toSignup ? -16 : 16;
    Animated.parallel([
      Animated.timing(formOpacity, { toValue: 0, duration: 120, useNativeDriver: true }),
      Animated.timing(formTranslate, { toValue: exitX, duration: 120, useNativeDriver: true }),
    ]).start(() => {
      setError('');
      setName('');
      setEmail('');
      setPassword('');
      setConfirmPassword('');
      setMode(next);
      formTranslate.setValue(-exitX);
      Animated.parallel([
        Animated.timing(formOpacity, { toValue: 1, duration: 180, useNativeDriver: true }),
        Animated.timing(formTranslate, { toValue: 0, duration: 180, useNativeDriver: true }),
      ]).start();
    });
  }

  function handleSubmit() {
    if (mode === 'signup' && !name.trim()) {
      setError('Please enter your name.');
      return;
    }
    if (!email.trim() || !password.trim()) {
      setError('Please fill in all fields.');
      return;
    }
    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setError('');
    // TODO: replace with POST /auth/login or POST /auth/signup — store returned JWT token in SecureStore
    onAuth();
  }

  const isLogin = mode === 'login';

  const indicatorTranslate = slideAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, toggleWidth / 2],
  });

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.container}
          keyboardShouldPersistTaps="handled"
          bounces={false}
        >
          <View style={styles.header}>
            <View style={styles.logoCircle}>
              <Ionicons name="wifi" size={36} color={colors.surface} />
            </View>
            <Text style={styles.appName}>Signally</Text>
            <Text style={styles.tagline}>Your home network, secured.</Text>
          </View>

          <View style={styles.card}>
            <View
              style={styles.toggle}
              onLayout={(e) => setToggleWidth(e.nativeEvent.layout.width)}
            >
              <Animated.View
                style={[
                  styles.toggleIndicator,
                  { width: toggleWidth / 2, transform: [{ translateX: indicatorTranslate }] },
                ]}
              />
              <TouchableOpacity style={styles.toggleBtn} onPress={() => switchMode('login')}>
                <Text style={[styles.toggleText, isLogin && styles.toggleTextActive]}>
                  Log In
                </Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.toggleBtn} onPress={() => switchMode('signup')}>
                <Text style={[styles.toggleText, !isLogin && styles.toggleTextActive]}>
                  Sign Up
                </Text>
              </TouchableOpacity>
            </View>

            <Animated.View
              style={{ opacity: formOpacity, transform: [{ translateX: formTranslate }] }}
            >
              {!isLogin && (
                <>
                  <Text style={styles.label}>Name</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Your name"
                    placeholderTextColor={colors.textMuted}
                    value={name}
                    onChangeText={setName}
                  />
                </>
              )}

              <Text style={[styles.label, !isLogin && { marginTop: spacing.md }]}>Email</Text>
              <TextInput
                style={styles.input}
                placeholder="you@example.com"
                placeholderTextColor={colors.textMuted}
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
              />

              <Text style={[styles.label, { marginTop: spacing.md }]}>Password</Text>
              <View style={styles.passwordRow}>
                <TextInput
                  style={[styles.input, styles.passwordInput]}
                  placeholder="••••••••"
                  placeholderTextColor={colors.textMuted}
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                />
                <TouchableOpacity
                  style={styles.eyeBtn}
                  onPress={() => setShowPassword((v) => !v)}
                >
                  <Ionicons
                    name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                    size={20}
                    color={colors.textSecondary}
                  />
                </TouchableOpacity>
              </View>

              {!isLogin && (
                <>
                  <Text style={[styles.label, { marginTop: spacing.md }]}>Confirm Password</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="••••••••"
                    placeholderTextColor={colors.textMuted}
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    secureTextEntry={!showPassword}
                  />
                </>
              )}

              {error ? <Text style={styles.error}>{error}</Text> : null}

              <TouchableOpacity style={styles.submitBtn} onPress={handleSubmit}>
                <Text style={styles.submitBtnText}>{isLogin ? 'Log In' : 'Create Account'}</Text>
              </TouchableOpacity>

              {isLogin && (
                <TouchableOpacity>
                  <Text style={styles.forgotText}>Forgot password?</Text>
                </TouchableOpacity>
              )}
            </Animated.View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  container: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  logoCircle: {
    width: 72,
    height: 72,
    borderRadius: radius.full,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  appName: {
    fontSize: font.xxxl,
    fontWeight: '700',
    color: colors.primary,
    letterSpacing: 1,
  },
  tagline: {
    fontSize: font.md,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  toggle: {
    flexDirection: 'row',
    backgroundColor: colors.background,
    borderRadius: radius.sm,
    padding: 4,
    marginBottom: spacing.lg,
    position: 'relative',
  },
  toggleIndicator: {
    position: 'absolute',
    top: 4,
    bottom: 4,
    left: 4,
    borderRadius: radius.sm - 2,
    backgroundColor: colors.surface,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: radius.sm - 2,
    zIndex: 1,
  },
  toggleText: {
    fontSize: font.md,
    fontWeight: '600',
    color: colors.textMuted,
  },
  toggleTextActive: {
    color: colors.primary,
  },
  label: {
    fontSize: font.sm,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.xs,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: font.lg,
    color: colors.textPrimary,
    backgroundColor: colors.background,
  },
  passwordRow: { position: 'relative' },
  passwordInput: { paddingRight: 48 },
  eyeBtn: {
    position: 'absolute',
    right: 12,
    top: 0,
    bottom: 0,
    justifyContent: 'center',
  },
  error: {
    color: colors.alert,
    fontSize: font.sm,
    marginTop: spacing.sm,
  },
  submitBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.sm,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  submitBtnText: {
    color: colors.surface,
    fontSize: font.lg,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  forgotText: {
    textAlign: 'center',
    marginTop: spacing.md,
    fontSize: font.md,
    color: colors.textSecondary,
  },
});
