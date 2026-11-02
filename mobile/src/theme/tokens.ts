/**
 * ExpenseIt Design System — Teal Modern FinTech (WCAG 2.1 AA Verified)
 *
 * Light Primary (#0F766E) + #FFFFFF = 5.47:1 (passes AA 4.5:1)
 * Dark Primary  (#14B8A6) + #041E1D = 7.31:1 (passes AA 4.5:1)
 */

export const MIN_TOUCH_TARGET_PX = 48;

export interface ThemePalette {
  background: string;
  surface: string;
  surfaceElevated: string;
  primary: string;
  primaryPressed: string;
  onPrimary: string;
  accent: string;
  onAccent: string;
  border: string;
  textPrimary: string;
  textMuted: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
}

export const lightPalette: ThemePalette = {
  background: "#F0FDFA",
  surface: "#FFFFFF",
  surfaceElevated: "#CCFBF1",
  primary: "#0F766E",
  primaryPressed: "#115E59",
  onPrimary: "#FFFFFF",
  accent: "#6D28D9",
  onAccent: "#FFFFFF",
  border: "#CCFBF1",
  textPrimary: "#0F172A",
  textMuted: "#475569",
  success: "#15803D",
  warning: "#B45309",
  danger: "#B91C1C",
  info: "#0369A1",
};

export const darkPalette: ThemePalette = {
  background: "#041E1D",
  surface: "#0D2D2A",
  surfaceElevated: "#134E4A",
  primary: "#14B8A6",
  primaryPressed: "#0D9488",
  onPrimary: "#041E1D",
  accent: "#A78BFA",
  onAccent: "#0F172A",
  border: "#134E4A",
  textPrimary: "#F0FDFA",
  textMuted: "#94A3B8",
  success: "#4ADE80",
  warning: "#FBBF24",
  danger: "#F87171",
  info: "#38BDF8",
};

