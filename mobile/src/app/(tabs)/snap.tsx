import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppTheme } from "@/theme/ThemeProvider";
import { MIN_TOUCH_TARGET_PX } from "@/theme/tokens";
import { normalizeReceiptImage } from "@/utils/image";
import { apiRequest, createIdempotencyKey, ExtractedReceipt, MockPreset } from "@/api/client";
import { formatINRPaise } from "@/utils/money";

export default function SnapScreen() {
  const { colors } = useAppTheme();
  const queryClient = useQueryClient();
  const [extracted, setExtracted] = useState<ExtractedReceipt | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const mockScanMutation = useMutation({
    mutationFn: (preset: MockPreset) =>
      apiRequest<ExtractedReceipt>("/ocr/mock-scan", {
        method: "POST",
        body: JSON.stringify({ preset }),
      }),
    onSuccess: (data) => {
      setExtracted(data);
    },
    onError: (err) => {
      Alert.alert("Scan Error", err.message);
    },
  });

  const submitClaimMutation = useMutation({
    mutationFn: (rec: ExtractedReceipt) =>
      apiRequest("/claims", {
        method: "POST",
        headers: { "Idempotency-Key": createIdempotencyKey("snap") },
        body: JSON.stringify({
          receipt_id: rec.receipt_id,
          vendor_name: rec.vendor_name || "Unknown Vendor",
          invoice_date: rec.invoice_date || "2026-11-02",
          category_code: rec.suggested_category_code,
          currency: "INR",
          total_amount_paise: rec.total_amount_paise,
          tax_amount_paise: rec.tax_amount_paise,
          submit_immediately: true,
          line_items: rec.line_items.map((li) => ({
            description: li.description,
            quantity: li.quantity,
            amount_paise: li.amount_paise,
            item_tag: li.item_tag,
          })),
        }),
      }),
    onSuccess: () => {
      Alert.alert("Success", "Claim submitted for approval!");
      setExtracted(null);
      void queryClient.invalidateQueries({ queryKey: ["claims"] });
      void queryClient.invalidateQueries({ queryKey: ["quota"] });
    },
    onError: (err) => {
      Alert.alert("Submission Error", err.message);
    },
  });

  const handlePickImage = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.9,
    });
    if (!res.canceled && res.assets[0]?.uri) {
      try {
        setIsProcessing(true);
        const normalized = await normalizeReceiptImage(res.assets[0].uri);
        const formData = new FormData();
        formData.append("file", {
          uri: normalized.uri,
          name: normalized.fileName,
          type: normalized.mimeType,
        } as unknown as Blob);

        const data = await apiRequest<ExtractedReceipt>("/ocr/scan", {
          method: "POST",
          body: formData,
        });
        setExtracted(data);
      } catch (e: unknown) {
        Alert.alert("Upload Failed", e instanceof Error ? e.message : "Error");
      } finally {
        setIsProcessing(false);
      }
    }
  };

  return (
    <ScrollView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[styles.heading, { color: colors.textPrimary }]}>Capture Receipt</Text>
        <Text style={[styles.sub, { color: colors.textMuted }]}>
          Upload a receipt photo or test with deterministic synthetic presets.
        </Text>

        <Pressable
          accessibilityRole="button"
          onPress={handlePickImage}
          disabled={isProcessing}
          style={[styles.primaryBtn, { backgroundColor: colors.primary }]}
        >
          {isProcessing ? (
            <ActivityIndicator color={colors.onPrimary} />
          ) : (
            <Text style={[styles.btnText, { color: colors.onPrimary }]}>📷 Select from Gallery</Text>
          )}
        </Pressable>

        <Text style={[styles.label, { color: colors.textMuted, marginTop: 16 }]}>
          TEST WITH OCR PRESETS (SYSTEM 2 WORKFLOW)
        </Text>
        <View style={styles.presetGrid}>
          {(["clean_meal", "hotel_with_alcohol", "over_cap_flight"] as MockPreset[]).map((p) => (
            <Pressable
              key={p}
              onPress={() => mockScanMutation.mutate(p)}
              style={[
                styles.presetBtn,
                { backgroundColor: colors.background, borderColor: colors.border },
              ]}
            >
              <Text style={{ color: colors.textPrimary, fontSize: 12, fontWeight: "700" }}>
                {p}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      {extracted && (
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Text style={[styles.heading, { color: colors.textPrimary }]}>
            Review Extracted Details
          </Text>
          <Text style={[styles.detail, { color: colors.textPrimary }]}>
            Vendor: {extracted.vendor_name || "N/A"}
          </Text>
          <Text style={[styles.detail, { color: colors.textPrimary }]}>
            Date: {extracted.invoice_date || "N/A"}
          </Text>
          <Text style={[styles.detail, { color: colors.textPrimary }]}>
            Category: {extracted.suggested_category_code}
          </Text>
          <Text style={[styles.detail, { color: colors.primary, fontWeight: "700" }]}>
            Total: {formatINRPaise(extracted.total_amount_paise)}
          </Text>

          <Pressable
            accessibilityRole="button"
            onPress={() => submitClaimMutation.mutate(extracted)}
            style={[styles.primaryBtn, { backgroundColor: colors.accent, marginTop: 16 }]}
          >
            <Text style={[styles.btnText, { color: colors.onAccent }]}>
              Submit Expense Claim
            </Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  card: { padding: 16, borderRadius: 14, borderWidth: 1, marginBottom: 16 },
  heading: { fontSize: 18, fontWeight: "700", marginBottom: 6 },
  sub: { fontSize: 13, marginBottom: 16 },
  primaryBtn: {
    minHeight: MIN_TOUCH_TARGET_PX,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  btnText: { fontSize: 14, fontWeight: "700" },
  label: { fontSize: 11, fontWeight: "700", letterSpacing: 0.6, marginBottom: 8 },
  presetGrid: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  presetBtn: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: MIN_TOUCH_TARGET_PX,
    justifyContent: "center",
  },
  detail: { fontSize: 14, marginBottom: 4 },
});

