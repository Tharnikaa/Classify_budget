import React, { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAppTheme } from "@/theme/ThemeProvider";
import { MIN_TOUCH_TARGET_PX } from "@/theme/tokens";
import { normalizeReceiptImage } from "@/utils/image";
import {
  apiRequest,
  createIdempotencyKey,
  ExtractedReceipt,
  MockPreset,
} from "@/api/client";
import { formatINRPaise, parseRupeesInputToPaise } from "@/utils/money";

interface CategoryOption {
  code: string;
  name: string;
}

const DEFAULT_CATEGORIES: CategoryOption[] = [
  { code: "MEALS", name: "Meals" },
  { code: "TRAVEL", name: "Travel" },
  { code: "LODGING", name: "Lodging" },
  { code: "OFFICE_SUPPLIES", name: "Office" },
  { code: "SOFTWARE_TOOLS", name: "Software" },
  { code: "INTERNET_PHONE", name: "Telecom" },
  { code: "OTHER", name: "Other" },
];

const BLACKLISTED_TAGS = new Set(["alcohol", "tobacco", "gift_card", "personal"]);

export default function SnapScreen() {
  const { colors } = useAppTheme();
  const queryClient = useQueryClient();

  // Extraction & editable claim state
  const [extracted, setExtracted] = useState<ExtractedReceipt | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Editable fields for review screen
  const [vendorName, setVendorName] = useState("");
  const [invoiceDate, setInvoiceDate] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("MEALS");
  const [totalRupeesText, setTotalRupeesText] = useState("");
  const [taxRupeesText, setTaxRupeesText] = useState("");

  // Fetch dynamic categories from backend
  const { data: serverCategories } = useQuery<CategoryOption[]>({
    queryKey: ["categories"],
    queryFn: () => apiRequest<CategoryOption[]>("/categories"),
    staleTime: 1000 * 60 * 5,
  });

  const activeCategories = serverCategories?.length ? serverCategories : DEFAULT_CATEGORIES;

  // Initialize review form from OCR extraction
  const loadExtractionIntoForm = (data: ExtractedReceipt) => {
    setExtracted(data);
    setVendorName(data.vendor_name || "");
    setInvoiceDate(data.invoice_date || "");
    setSelectedCategory(data.suggested_category_code || "OTHER");
    setTotalRupeesText((data.total_amount_paise / 100).toFixed(2));
    setTaxRupeesText((data.tax_amount_paise / 100).toFixed(2));
  };

  // Mock scan preset mutation
  const mockScanMutation = useMutation({
    mutationFn: (preset: MockPreset) =>
      apiRequest<ExtractedReceipt>("/ocr/mock-scan", {
        method: "POST",
        body: JSON.stringify({ preset }),
      }),
    onSuccess: (data) => {
      loadExtractionIntoForm(data);
    },
    onError: (err) => {
      Alert.alert("Preset Scan Error", err.message);
    },
  });

  // Submit claim mutation
  const submitClaimMutation = useMutation({
    mutationFn: async () => {
      if (!extracted) throw new Error("No receipt to submit");

      const totalPaise = parseRupeesInputToPaise(totalRupeesText);
      const taxPaise = parseRupeesInputToPaise(taxRupeesText);

      return apiRequest("/claims", {
        method: "POST",
        headers: { "Idempotency-Key": createIdempotencyKey("snap-claim") },
        body: JSON.stringify({
          receipt_id: extracted.receipt_id,
          vendor_name: vendorName.trim() || "Unknown Vendor",
          invoice_date: invoiceDate.trim() || new Date().toISOString().slice(0, 10),
          category_code: selectedCategory,
          currency: extracted.detected_currency || "INR",
          total_amount_paise: totalPaise,
          tax_amount_paise: taxPaise,
          submit_immediately: true,
          line_items: extracted.line_items.map((li) => ({
            description: li.description,
            quantity: li.quantity,
            amount_paise: li.amount_paise,
            item_tag: li.item_tag,
          })),
        }),
      });
    },
    onSuccess: () => {
      Alert.alert("Success", "Expense claim submitted for approval!");
      setExtracted(null);
      void queryClient.invalidateQueries({ queryKey: ["claims"] });
      void queryClient.invalidateQueries({ queryKey: ["quota"] });
    },
    onError: (err) => {
      Alert.alert("Submission Error", err.message);
    },
  });

  // Camera capture handler
  const handleCameraCapture = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permission Required", "Camera permission is required to capture receipts.");
      return;
    }

    const res = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.85,
    });

    if (!res.canceled && res.assets[0]?.uri) {
      await processUploadedImage(res.assets[0].uri);
    }
  };

  // Gallery photo picker handler
  const handleGalleryPick = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.85,
    });

    if (!res.canceled && res.assets[0]?.uri) {
      await processUploadedImage(res.assets[0].uri);
    }
  };

  // Upload image to backend OCR endpoint
  const processUploadedImage = async (localUri: string) => {
    try {
      setIsProcessing(true);
      const normalized = await normalizeReceiptImage(localUri);
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
      loadExtractionIntoForm(data);
    } catch (e: unknown) {
      Alert.alert("Upload Failed", e instanceof Error ? e.message : "Error scanning receipt");
    } finally {
      setIsProcessing(false);
    }
  };

  // Compute blacklisted deduction amount for visual feedback
  const blacklistedDeductionPaise = (extracted?.line_items || []).reduce(
    (sum, item) => (BLACKLISTED_TAGS.has(item.item_tag.toLowerCase()) ? sum + item.amount_paise : sum),
    0
  );
  const currentTotalPaise = parseRupeesInputToPaise(totalRupeesText);
  const estimatedEligiblePaise = Math.max(0, currentTotalPaise - blacklistedDeductionPaise);

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      {/* 1. Capture Header & Actions Card */}
      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[styles.heading, { color: colors.textPrimary }]}>Snap & Classify Receipt</Text>
        <Text style={[styles.sub, { color: colors.textMuted }]}>
          Vision AI automatically extracts vendor, date, line items, and classifies into dynamic expense policies.
        </Text>

        {isProcessing ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={[styles.loadingText, { color: colors.primary }]}>
              Analyzing receipt with Vision AI...
            </Text>
          </View>
        ) : (
          <View style={styles.captureRow}>
            <Pressable
              accessibilityRole="button"
              onPress={handleCameraCapture}
              style={[styles.actionBtn, { backgroundColor: colors.primary }]}
            >
              <Text style={[styles.actionBtnText, { color: colors.onPrimary }]}>
                📷 Camera
              </Text>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              onPress={handleGalleryPick}
              style={[
                styles.actionBtn,
                { backgroundColor: colors.surface, borderColor: colors.primary, borderWidth: 1.5 },
              ]}
            >
              <Text style={[styles.actionBtnText, { color: colors.primary }]}>
                🖼️ Gallery
              </Text>
            </Pressable>
          </View>
        )}

        {/* Synthetic Presets for Testing */}
        <Text style={[styles.sectionTitle, { color: colors.textMuted, marginTop: 18 }]}>
          QUICK SYNTHETIC TEST PRESETS
        </Text>
        <View style={styles.presetGrid}>
          {(
            [
              { id: "clean_meal", label: "Clean Meal" },
              { id: "hotel_with_alcohol", label: "Hotel + Alcohol" },
              { id: "over_cap_flight", label: "Over-Cap Flight" },
              { id: "blurry_missing_date", label: "Blurry / No Date" },
              { id: "foreign_usd", label: "Foreign USD" },
            ] as const
          ).map((p) => (
            <Pressable
              key={p.id}
              onPress={() => mockScanMutation.mutate(p.id)}
              disabled={mockScanMutation.isPending || isProcessing}
              style={[
                styles.presetBtn,
                { backgroundColor: colors.background, borderColor: colors.border },
              ]}
            >
              <Text style={[styles.presetText, { color: colors.textPrimary }]}>{p.label}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      {/* 2. Confidence-Highlighted Review Screen */}
      {extracted && (
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          {/* Review Header & Badges */}
          <View style={styles.reviewHeaderRow}>
            <Text style={[styles.heading, { color: colors.textPrimary }]}>Review Extracted Data</Text>
            <View
              style={[
                styles.confidenceBadge,
                {
                  backgroundColor:
                    extracted.confidence_score >= 0.85
                      ? colors.success + "20"
                      : extracted.confidence_score >= 0.7
                        ? colors.warning + "20"
                        : colors.danger + "20",
                },
              ]}
            >
              <Text
                style={{
                  color:
                    extracted.confidence_score >= 0.85
                      ? colors.success
                      : extracted.confidence_score >= 0.7
                        ? colors.warning
                        : colors.danger,
                  fontSize: 11,
                  fontWeight: "700",
                }}
              >
                {Math.round(extracted.confidence_score * 100)}% Confidence
              </Text>
            </View>
          </View>

          {/* Non-INR Warning Banner */}
          {extracted.detected_currency !== "INR" && (
            <View style={[styles.warningBanner, { backgroundColor: colors.danger + "15", borderColor: colors.danger }]}>
              <Text style={[styles.warningText, { color: colors.danger }]}>
                ⚠️ Non-INR Currency ({extracted.detected_currency}) Detected: Expense policies mandate INR receipts.
              </Text>
            </View>
          )}

          {/* Invalid / Blurry Warning */}
          {!extracted.is_valid_receipt && (
            <View style={[styles.warningBanner, { backgroundColor: colors.warning + "15", borderColor: colors.warning }]}>
              <Text style={[styles.warningText, { color: colors.warning }]}>
                ⚠️ Low Quality Receipt: Missing or blurred fields require manual correction below.
              </Text>
            </View>
          )}

          {/* Field: Vendor */}
          <View style={styles.fieldGroup}>
            <View style={styles.fieldHeaderRow}>
              <Text style={[styles.fieldLabel, { color: colors.textMuted }]}>VENDOR NAME</Text>
              <ConfidencePill score={extracted.field_confidence?.vendor ?? 0.9} colors={colors} />
            </View>
            <TextInput
              value={vendorName}
              onChangeText={setVendorName}
              placeholder="e.g. Third Wave Coffee"
              placeholderTextColor={colors.textMuted}
              style={[
                styles.input,
                {
                  backgroundColor: colors.background,
                  color: colors.textPrimary,
                  borderColor:
                    (extracted.field_confidence?.vendor ?? 1) < 0.8 ? colors.warning : colors.border,
                },
              ]}
            />
          </View>

          {/* Field: Invoice Date */}
          <View style={styles.fieldGroup}>
            <View style={styles.fieldHeaderRow}>
              <Text style={[styles.fieldLabel, { color: colors.textMuted }]}>INVOICE DATE (YYYY-MM-DD)</Text>
              <ConfidencePill score={extracted.field_confidence?.date ?? 0.9} colors={colors} />
            </View>
            <TextInput
              value={invoiceDate}
              onChangeText={setInvoiceDate}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.textMuted}
              style={[
                styles.input,
                {
                  backgroundColor: colors.background,
                  color: colors.textPrimary,
                  borderColor:
                    (extracted.field_confidence?.date ?? 1) < 0.8 || !invoiceDate
                      ? colors.warning
                      : colors.border,
                },
              ]}
            />
          </View>

          {/* Field: Category Selector */}
          <View style={styles.fieldGroup}>
            <View style={styles.fieldHeaderRow}>
              <Text style={[styles.fieldLabel, { color: colors.textMuted }]}>CATEGORY</Text>
              <ConfidencePill score={extracted.field_confidence?.category ?? 0.9} colors={colors} />
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.categoryScroll}>
              {activeCategories.map((cat) => {
                const isSelected = selectedCategory === cat.code;
                return (
                  <Pressable
                    key={cat.code}
                    onPress={() => setSelectedCategory(cat.code)}
                    style={[
                      styles.categoryPill,
                      {
                        backgroundColor: isSelected ? colors.primary : colors.background,
                        borderColor: isSelected ? colors.primary : colors.border,
                      },
                    ]}
                  >
                    <Text
                      style={{
                        color: isSelected ? colors.onPrimary : colors.textPrimary,
                        fontSize: 12,
                        fontWeight: isSelected ? "700" : "500",
                      }}
                    >
                      {cat.name}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>
          </View>

          {/* Field: Total & Tax Amounts */}
          <View style={styles.row}>
            <View style={[styles.fieldGroup, { flex: 1, marginRight: 8 }]}>
              <View style={styles.fieldHeaderRow}>
                <Text style={[styles.fieldLabel, { color: colors.textMuted }]}>TOTAL (₹)</Text>
                <ConfidencePill score={extracted.field_confidence?.total ?? 0.9} colors={colors} />
              </View>
              <TextInput
                value={totalRupeesText}
                onChangeText={setTotalRupeesText}
                keyboardType="decimal-pad"
                placeholder="0.00"
                placeholderTextColor={colors.textMuted}
                style={[styles.input, { backgroundColor: colors.background, color: colors.textPrimary, borderColor: colors.border }]}
              />
            </View>

            <View style={[styles.fieldGroup, { flex: 1, marginLeft: 8 }]}>
              <Text style={[styles.fieldLabel, { color: colors.textMuted, marginBottom: 4 }]}>TAX (₹)</Text>
              <TextInput
                value={taxRupeesText}
                onChangeText={setTaxRupeesText}
                keyboardType="decimal-pad"
                placeholder="0.00"
                placeholderTextColor={colors.textMuted}
                style={[styles.input, { backgroundColor: colors.background, color: colors.textPrimary, borderColor: colors.border }]}
              />
            </View>
          </View>

          {/* 3. Factual Line Items Breakdown */}
          <Text style={[styles.sectionTitle, { color: colors.textMuted, marginTop: 14 }]}>
            FACTUAL LINE ITEMS ({extracted.line_items.length})
          </Text>
          {extracted.line_items.map((item, idx) => {
            const isBlacklisted = BLACKLISTED_TAGS.has(item.item_tag.toLowerCase());
            return (
              <View
                key={idx}
                style={[
                  styles.lineItemCard,
                  {
                    backgroundColor: colors.background,
                    borderColor: isBlacklisted ? colors.warning : colors.border,
                  },
                ]}
              >
                <View style={styles.lineItemRow}>
                  <Text style={[styles.lineItemDesc, { color: colors.textPrimary }]}>
                    {item.description}
                  </Text>
                  <Text style={[styles.lineItemAmount, { color: colors.textPrimary }]}>
                    {formatINRPaise(item.amount_paise)}
                  </Text>
                </View>

                <View style={styles.lineItemSubRow}>
                  <Text style={[styles.lineItemQty, { color: colors.textMuted }]}>
                    Qty: {item.quantity}
                  </Text>
                  <View
                    style={[
                      styles.tagBadge,
                      {
                        backgroundColor: isBlacklisted ? colors.warning + "20" : colors.primary + "15",
                      },
                    ]}
                  >
                    <Text
                      style={{
                        color: isBlacklisted ? colors.warning : colors.primary,
                        fontSize: 10,
                        fontWeight: "700",
                        textTransform: "uppercase",
                      }}
                    >
                      {item.item_tag}
                      {isBlacklisted ? " (Auto-Deducted)" : ""}
                    </Text>
                  </View>
                </View>
              </View>
            );
          })}

          {/* 4. Policy Payout Preview Card */}
          <View style={[styles.summaryCard, { backgroundColor: colors.background, borderColor: colors.border }]}>
            <View style={styles.summaryRow}>
              <Text style={[styles.summaryLabel, { color: colors.textMuted }]}>Total Amount:</Text>
              <Text style={[styles.summaryVal, { color: colors.textPrimary }]}>
                {formatINRPaise(currentTotalPaise)}
              </Text>
            </View>
            {blacklistedDeductionPaise > 0 && (
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabel, { color: colors.danger }]}>Policy Deductions:</Text>
                <Text style={[styles.summaryVal, { color: colors.danger }]}>
                  -{formatINRPaise(blacklistedDeductionPaise)}
                </Text>
              </View>
            )}
            <View style={[styles.summaryRow, styles.summaryDivider, { borderColor: colors.border }]}>
              <Text style={[styles.summaryTotalLabel, { color: colors.primary }]}>Eligible Reimbursement:</Text>
              <Text style={[styles.summaryTotalVal, { color: colors.primary }]}>
                {formatINRPaise(estimatedEligiblePaise)}
              </Text>
            </View>
          </View>

          {/* Submission CTAs */}
          <Pressable
            accessibilityRole="button"
            onPress={() => submitClaimMutation.mutate()}
            disabled={submitClaimMutation.isPending}
            style={[styles.submitBtn, { backgroundColor: colors.accent, marginTop: 16 }]}
          >
            {submitClaimMutation.isPending ? (
              <ActivityIndicator color={colors.onAccent} />
            ) : (
              <Text style={[styles.submitBtnText, { color: colors.onAccent }]}>
                Submit Expense Claim
              </Text>
            )}
          </Pressable>

          <Pressable
            accessibilityRole="button"
            onPress={() => setExtracted(null)}
            style={[styles.discardBtn, { minHeight: MIN_TOUCH_TARGET_PX }]}
          >
            <Text style={[styles.discardText, { color: colors.textMuted }]}>
              Discard & Scan Another
            </Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

function ConfidencePill({
  score,
  colors,
}: {
  score: number;
  colors: ReturnType<typeof useAppTheme>["colors"];
}) {
  const isHigh = score >= 0.8;
  const pct = Math.round(score * 100);
  return (
    <View
      style={[
        styles.pill,
        {
          backgroundColor: isHigh ? colors.success + "15" : colors.warning + "20",
        },
      ]}
    >
      <Text
        style={{
          color: isHigh ? colors.success : colors.warning,
          fontSize: 10,
          fontWeight: "700",
        }}
      >
        {isHigh ? `${pct}%` : `⚠️ ${pct}% Verify`}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  card: { padding: 16, borderRadius: 14, borderWidth: 1, marginBottom: 16 },
  heading: { fontSize: 18, fontWeight: "700", marginBottom: 4 },
  sub: { fontSize: 13, lineHeight: 18, marginBottom: 16 },
  captureRow: { flexDirection: "row", gap: 12 },
  actionBtn: {
    flex: 1,
    minHeight: MIN_TOUCH_TARGET_PX,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  actionBtnText: { fontSize: 15, fontWeight: "700" },
  loadingContainer: { padding: 24, alignItems: "center", justifyContent: "center" },
  loadingText: { marginTop: 12, fontSize: 14, fontWeight: "600" },
  sectionTitle: { fontSize: 11, fontWeight: "700", letterSpacing: 0.6, marginBottom: 8 },
  presetGrid: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  presetBtn: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 40,
    justifyContent: "center",
  },
  presetText: { fontSize: 12, fontWeight: "600" },
  reviewHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  confidenceBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  warningBanner: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 12,
  },
  warningText: { fontSize: 12, fontWeight: "600", lineHeight: 16 },
  fieldGroup: { marginBottom: 12 },
  fieldHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  fieldLabel: { fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },
  input: {
    height: MIN_TOUCH_TARGET_PX,
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 12,
    fontSize: 14,
  },
  row: { flexDirection: "row" },
  categoryScroll: { flexDirection: "row", marginTop: 4 },
  categoryPill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    marginRight: 8,
    minHeight: 36,
    justifyContent: "center",
  },
  lineItemCard: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 8,
  },
  lineItemRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  lineItemDesc: { fontSize: 13, fontWeight: "600", flex: 1, marginRight: 8 },
  lineItemAmount: { fontSize: 13, fontWeight: "700" },
  lineItemSubRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 4,
  },
  lineItemQty: { fontSize: 11 },
  tagBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  summaryCard: {
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 12,
  },
  summaryRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 4 },
  summaryLabel: { fontSize: 13 },
  summaryVal: { fontSize: 13, fontWeight: "600" },
  summaryDivider: { borderTopWidth: 1, paddingTop: 8, marginTop: 4 },
  summaryTotalLabel: { fontSize: 14, fontWeight: "700" },
  summaryTotalVal: { fontSize: 15, fontWeight: "800" },
  submitBtn: {
    minHeight: MIN_TOUCH_TARGET_PX,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  submitBtnText: { fontSize: 15, fontWeight: "700" },
  discardBtn: {
    justifyContent: "center",
    alignItems: "center",
    marginTop: 8,
  },
  discardText: { fontSize: 13, fontWeight: "600" },
  pill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
});
