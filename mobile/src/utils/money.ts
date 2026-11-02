/**
 * Exact integer INR paise helpers (zero IEEE-754 float arithmetic).
 */

export function formatINRPaise(amountPaise: number): string {
  const safe = Math.trunc(amountPaise);
  const sign = safe < 0 ? "-" : "";
  const abs = Math.abs(safe);
  const rupees = Math.floor(abs / 100);
  const paise = abs % 100;
  const formattedRupees = rupees.toLocaleString("en-IN");
  const formattedPaise = String(paise).padStart(2, "0");
  return `${sign}\u20B9${formattedRupees}.${formattedPaise}`;
}

export function parseRupeesInputToPaise(input: string): number {
  const cleaned = input.replace(/[^0-9.]/g, "").trim();
  if (!cleaned) return 0;
  const [wholePart = "0", fracPart = ""] = cleaned.split(".");
  const rupees = parseInt(wholePart || "0", 10);
  const paddedFrac = (fracPart + "00").slice(0, 2);
  const paise = parseInt(paddedFrac, 10);
  return rupees * 100 + paise;
}

