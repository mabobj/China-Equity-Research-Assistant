import type { PriceRange } from "@/types/api";

const priceFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatDate(value: string): string {
  return value;
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return priceFormatter.format(value);
}

export function formatRange(range: PriceRange | null | undefined): string {
  if (!range) {
    return "-";
  }
  return `${formatPrice(range.low)} - ${formatPrice(range.high)}`;
}

export function formatScore(value: number): string {
  return `${value} / 100`;
}

export function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}
