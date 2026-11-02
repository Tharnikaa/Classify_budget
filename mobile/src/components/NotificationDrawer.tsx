import React from "react";
import {
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest, NotificationItem } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { useAppTheme } from "@/theme/ThemeProvider";
import { MIN_TOUCH_TARGET_PX } from "@/theme/tokens";

export function useNotificationsPoll() {
  const { user } = useAuth();
  return useQuery<NotificationItem[]>({
    queryKey: ["notifications", user?.id],
    enabled: Boolean(user?.id),
    refetchInterval: 30_000,
    queryFn: () => apiRequest<NotificationItem[]>("/notifications"),
  });
}

export function NotificationDrawer({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { colors } = useAppTheme();
  const queryClient = useQueryClient();
  const { data: items = [] } = useNotificationsPoll();

  const markReadMutation = useMutation({
    mutationFn: (id: string) =>
      apiRequest<NotificationItem>(`/notifications/${id}/read`, {
        method: "POST",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.backdrop}>
        <View
          style={[
            styles.sheet,
            { backgroundColor: colors.surface, borderColor: colors.border },
          ]}
        >
          <View style={styles.header}>
            <Text style={[styles.title, { color: colors.textPrimary }]}>
              Notifications ({items.filter((i) => !i.is_read).length} unread)
            </Text>
            <Pressable
              onPress={onClose}
              style={[
                styles.closeButton,
                { backgroundColor: colors.primary },
              ]}
            >
              <Text style={{ color: colors.onPrimary, fontWeight: "700" }}>
                Done
              </Text>
            </Pressable>
          </View>

          <FlatList
            data={items}
            keyExtractor={(item) => item.id}
            ListEmptyComponent={
              <Text style={[styles.empty, { color: colors.textMuted }]}>
                No notifications yet for this persona.
              </Text>
            }
            renderItem={({ item }) => (
              <Pressable
                onPress={() => {
                  if (!item.is_read) {
                    markReadMutation.mutate(item.id);
                  }
                }}
                style={[
                  styles.card,
                  {
                    backgroundColor: item.is_read
                      ? colors.background
                      : colors.surfaceElevated,
                    borderColor: colors.border,
                  },
                ]}
              >
                <Text
                  style={[styles.cardTitle, { color: colors.textPrimary }]}
                >
                  {item.title}
                </Text>
                <Text
                  style={[styles.cardMessage, { color: colors.textMuted }]}
                >
                  {item.message}
                </Text>
                <Text style={[styles.cardMeta, { color: colors.accent }]}>
                  {item.type} · {item.is_read ? "Read" : "Tap to mark read"}
                </Text>
              </Pressable>
            )}
          />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(4, 30, 29, 0.6)",
    justifyContent: "flex-end",
  },
  sheet: {
    maxHeight: "78%",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    padding: 16,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
  },
  closeButton: {
    minHeight: MIN_TOUCH_TARGET_PX,
    paddingHorizontal: 16,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  empty: {
    paddingVertical: 32,
    textAlign: "center",
  },
  card: {
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 10,
    minHeight: MIN_TOUCH_TARGET_PX,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 4,
  },
  cardMessage: {
    fontSize: 13,
    marginBottom: 6,
  },
  cardMeta: {
    fontSize: 11,
    fontWeight: "600",
  },
});
