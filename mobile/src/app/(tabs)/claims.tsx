import React, { useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/context/AuthContext";
import { useAppTheme } from "@/theme/ThemeProvider";
import { apiRequest, ExpenseClaim } from "@/api/client";
import { formatINRPaise } from "@/utils/money";
import { MIN_TOUCH_TARGET_PX } from "@/theme/tokens";

export default function ClaimsScreen() {
  const { user } = useAuth();
  const { colors } = useAppTheme();
  const [tab, setTab] = useState<"mine" | "queue">("mine");

  const isApprover =
    user?.role === "DEPT_HEAD" ||
    user?.role === "FINANCE_MANAGER" ||
    user?.role === "FINANCE_HEAD";

  const { data: claims = [] } = useQuery<ExpenseClaim[]>({
    queryKey: ["claims", user?.id, tab],
    enabled: Boolean(user?.id),
    queryFn: () => apiRequest<ExpenseClaim[]>(`/claims?scope=${tab}`),
  });

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {isApprover && (
        <View style={styles.segmentRow}>
          <Pressable
            accessibilityRole="button"
            onPress={() => setTab("mine")}
            style={[
              styles.segmentBtn,
              {
                backgroundColor: tab === "mine" ? colors.primary : colors.surface,
                borderColor: colors.border,
              },
            ]}
          >
            <Text
              style={{
                color: tab === "mine" ? colors.onPrimary : colors.textPrimary,
                fontWeight: "700",
              }}
            >
              My Claims
            </Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => setTab("queue")}
            style={[
              styles.segmentBtn,
              {
                backgroundColor: tab === "queue" ? colors.primary : colors.surface,
                borderColor: colors.border,
              },
            ]}
          >
            <Text
              style={{
                color: tab === "queue" ? colors.onPrimary : colors.textPrimary,
                fontWeight: "700",
              }}
            >
              Approval Queue
            </Text>
          </Pressable>
        </View>
      )}

      <FlatList
        data={claims}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ padding: 16 }}
        ListEmptyComponent={
          <Text style={[styles.empty, { color: colors.textMuted }]}>
            No claims found in this view.
          </Text>
        }
        renderItem={({ item }) => (
          <View
            style={[
              styles.card,
              { backgroundColor: colors.surface, borderColor: colors.border },
            ]}
          >
            <View style={styles.rowBetween}>
              <Text style={[styles.vendor, { color: colors.textPrimary }]}>
                {item.vendor_name}
              </Text>
              <Text style={[styles.amount, { color: colors.primary }]}>
                {formatINRPaise(item.total_amount_paise)}
              </Text>
            </View>
            <Text style={[styles.sub, { color: colors.textMuted }]}>
              {item.invoice_date} · {item.category_code} · By: {item.claimant_name}
            </Text>
            <View style={styles.rowBetween}>
              <View
                style={[
                  styles.badge,
                  { backgroundColor: colors.surfaceElevated, borderColor: colors.border },
                ]}
              >
                <Text style={[styles.badgeText, { color: colors.accent }]}>
                  {item.status}
                </Text>
              </View>
              {item.is_over_cap && (
                <Text style={{ color: colors.warning, fontSize: 11, fontWeight: "700" }}>
                  ⚠️ OVER CAP
                </Text>
              )}
            </View>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  segmentRow: {
    flexDirection: "row",
    padding: 12,
    gap: 8,
  },
  segmentBtn: {
    flex: 1,
    minHeight: MIN_TOUCH_TARGET_PX,
    borderRadius: 10,
    borderWidth: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  card: {
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 10,
  },
  rowBetween: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  vendor: { fontSize: 15, fontWeight: "700" },
  amount: { fontSize: 15, fontWeight: "700" },
  sub: { fontSize: 12, marginBottom: 8 },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
  },
  badgeText: { fontSize: 11, fontWeight: "700" },
  empty: { textAlign: "center", marginTop: 40 },
});

