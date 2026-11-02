import React from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useAuth } from "@/context/AuthContext";
import { useAppTheme } from "@/theme/ThemeProvider";
import { MIN_TOUCH_TARGET_PX } from "@/theme/tokens";

const ENABLE_SWITCHER =
  __DEV__ && process.env.EXPO_PUBLIC_ENABLE_ROLE_SWITCHER !== "false";

export function DevRoleSwitcher() {
  const { user, personas, switchDevPersona } = useAuth();
  const { colors } = useAppTheme();

  if (!ENABLE_SWITCHER || personas.length === 0) {
    return null;
  }

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: colors.surface, borderBottomColor: colors.border },
      ]}
    >
      <Text style={[styles.label, { color: colors.accent }]}>
        DEV PERSONA SWITCHER
      </Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {personas.map((p) => {
          const isSelected = user?.id === p.id;
          return (
            <Pressable
              key={p.id}
              accessibilityRole="button"
              onPress={() => {
                void switchDevPersona(p.persona_key);
              }}
              style={[
                styles.pill,
                {
                  backgroundColor: isSelected
                    ? colors.primary
                    : colors.background,
                  borderColor: isSelected ? colors.primary : colors.border,
                },
              ]}
            >
              <Text
                style={[
                  styles.pillTitle,
                  { color: isSelected ? colors.onPrimary : colors.textPrimary },
                ]}
              >
                {p.full_name.split(" ")[0]} ({p.role})
              </Text>
              <Text
                style={[
                  styles.pillSub,
                  { color: isSelected ? colors.onPrimary : colors.textMuted },
                ]}
              >
                {p.spend_tier}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: 6,
    borderBottomWidth: 1,
  },
  label: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.8,
    paddingHorizontal: 14,
    marginBottom: 4,
  },
  scrollContent: {
    paddingHorizontal: 12,
    gap: 8,
  },
  pill: {
    minHeight: MIN_TOUCH_TARGET_PX,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    justifyContent: "center",
  },
  pillTitle: {
    fontSize: 12,
    fontWeight: "700",
  },
  pillSub: {
    fontSize: 10,
    fontWeight: "500",
  },
});
