import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/context/AuthContext";
import { useAppTheme } from "@/theme/ThemeProvider";
import { apiRequest, MonthlyQuotaSummary } from "@/api/client";
import { formatINRPaise } from "@/utils/money";

export default function HomeScreen() {
  const { user } = useAuth();
  const { colors } = useAppTheme();

  const { data: quota } = useQuery<MonthlyQuotaSummary>({
    queryKey: ["quota", user?.id],
    enabled: Boolean(user?.id),
    queryFn: () => apiRequest<MonthlyQuotaSummary>("/quotas/me"),
  });

  return (
    <ScrollView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[styles.greeting, { color: colors.textPrimary }]}>
          Welcome, {user?.full_name || "Employee"}
        </Text>
        <Text style={[styles.sub, { color: colors.textMuted }]}>
          {user?.role} · Tier: {user?.spend_tier} · {user?.department_name}
        </Text>
      </View>

      {quota && (
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[styles.cardTitle, { color: colors.textPrimary }]}>
            Monthly Spend Limit ({quota.year_month})
          </Text>
          <View style={styles.metricRow}>
            <View>
              <Text style={[styles.metricLabel, { color: colors.textMuted }]}>Remaining</Text>
              <Text style={[styles.metricVal, { color: colors.primary }]}>
                {formatINRPaise(quota.remaining_paise)}
              </Text>
            </View>
            <View>
              <Text style={[styles.metricLabel, { color: colors.textMuted }]}>Disbursed</Text>
              <Text style={[styles.metricVal, { color: colors.textPrimary }]}>
                {formatINRPaise(quota.disbursed_paise)}
              </Text>
            </View>
            <View>
              <Text style={[styles.metricLabel, { color: colors.textMuted }]}>Reserved</Text>
              <Text style={[styles.metricVal, { color: colors.warning }]}>
                {formatINRPaise(quota.reserved_paise)}
              </Text>
            </View>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  card: { padding: 16, borderRadius: 14, borderWidth: 1, marginBottom: 16 },
  greeting: { fontSize: 20, fontWeight: "700", marginBottom: 4 },
  sub: { fontSize: 13, marginBottom: 4 },
  cardTitle: { fontSize: 16, fontWeight: "700", marginBottom: 12 },
  metricRow: { flexDirection: "row", justifyContent: "space-between" },
  metricLabel: { fontSize: 12, marginBottom: 4 },
  metricVal: { fontSize: 16, fontWeight: "700" },
});

