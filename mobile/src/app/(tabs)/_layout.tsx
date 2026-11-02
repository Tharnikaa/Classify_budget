import React, { useState } from "react";
import { Tabs } from "expo-router";
import { Text, Pressable, View } from "react-native";

import { useAppTheme } from "@/theme/ThemeProvider";
import { NotificationDrawer, useNotificationsPoll } from "@/components/NotificationDrawer";
import { MIN_TOUCH_TARGET_PX } from "@/theme/tokens";

export default function TabsLayout() {
  const { colors } = useAppTheme();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { data: notifications = [] } = useNotificationsPoll();
  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <>
      <Tabs
        screenOptions={{
          headerStyle: { backgroundColor: colors.surface },
          headerTintColor: colors.textPrimary,
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.border,
            minHeight: 56,
          },
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.textMuted,
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Notifications"
              onPress={() => setDrawerOpen(true)}
              style={{
                minHeight: MIN_TOUCH_TARGET_PX,
                minWidth: MIN_TOUCH_TARGET_PX,
                justifyContent: "center",
                alignItems: "center",
                marginRight: 12,
              }}
            >
              <View>
                <Text style={{ fontSize: 20 }}>🔔</Text>
                {unreadCount > 0 && (
                  <View
                    style={{
                      position: "absolute",
                      top: -4,
                      right: -8,
                      backgroundColor: colors.danger,
                      borderRadius: 10,
                      paddingHorizontal: 5,
                      paddingVertical: 1,
                    }}
                  >
                    <Text style={{ color: "#FFFFFF", fontSize: 10, fontWeight: "700" }}>
                      {unreadCount}
                    </Text>
                  </View>
                )}
              </View>
            </Pressable>
          ),
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: "Home",
            tabBarIcon: () => <Text style={{ fontSize: 18 }}>🏠</Text>,
          }}
        />
        <Tabs.Screen
          name="claims"
          options={{
            title: "Claims",
            tabBarIcon: () => <Text style={{ fontSize: 18 }}>📋</Text>,
          }}
        />
        <Tabs.Screen
          name="snap"
          options={{
            title: "Snap (+)",
            tabBarIcon: () => <Text style={{ fontSize: 18 }}>📷</Text>,
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: "Profile",
            tabBarIcon: () => <Text style={{ fontSize: 18 }}>👤</Text>,
          }}
        />
      </Tabs>
      <NotificationDrawer visible={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </>
  );
}

