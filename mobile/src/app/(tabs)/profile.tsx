import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/context/AuthContext";
import { useAppTheme } from "@/theme/ThemeProvider";
import { MIN_TOUCH_TARGET_PX } from "@/theme/tokens";

export default function ProfileScreen() {
  const { user, logout } = useAuth();
  const { colors, isDark, setMode, mode } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[styles.name, { color: colors.textPrimary }]}>{user?.full_name}</Text>
        <Text style={[styles.email, { color: colors.textMuted }]}>{user?.email}</Text>
        <View style={styles.divider} />
        <Text style={[styles.item, { color: colors.textPrimary }]}>
          Role: <Text style={{ fontWeight: "700" }}>{user?.role}</Text>
        </Text>
        <Text style={[styles.item, { color: colors.textPrimary }]}>
          Spend Tier: <Text style={{ fontWeight: "700" }}>{user?.spend_tier}</Text>
        </Text>
        <Text style={[styles.item, { color: colors.textPrimary }]}>
          Department: <Text style={{ fontWeight: "700" }}>{user?.department_name}</Text>
        </Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[styles.sectionTitle, { color: colors.textPrimary }]}>Theme Settings</Text>
        <View style={styles.themeRow}>
          {(["system", "light", "dark"] as const).map((m) => (
            <Pressable
              key={m}
              accessibilityRole="button"
              onPress={() => setMode(m)}
              style={[
                styles.themeBtn,
                {
                  backgroundColor: mode === m ? colors.primary : colors.background,
                  borderColor: colors.border,
                },
              ]}
            >
              <Text
                style={{
                  color: mode === m ? colors.onPrimary : colors.textPrimary,
                  fontWeight: "700",
                }}
              >
                {m.toUpperCase()}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Pressable
        accessibilityRole="button"
        onPress={() => {
          void logout();
        }}
        style={[styles.logoutBtn, { backgroundColor: colors.danger }]}
      >
        <Text style={{ color: "#FFFFFF", fontWeight: "700" }}>Log Out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  card: { padding: 16, borderRadius: 14, borderWidth: 1, marginBottom: 16 },
  name: { fontSize: 20, fontWeight: "700" },
  email: { fontSize: 13, marginBottom: 8 },
  divider: { height: 1, backgroundColor: "#E2E8F0", marginVertical: 8 },
  item: { fontSize: 14, marginBottom: 4 },
  sectionTitle: { fontSize: 16, fontWeight: "700", marginBottom: 12 },
  themeRow: { flexDirection: "row", gap: 8 },
  themeBtn: {
    flex: 1,
    minHeight: MIN_TOUCH_TARGET_PX,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  logoutBtn: {
    minHeight: MIN_TOUCH_TARGET_PX,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
});

