/**
 * Haptic feedback via Web Vibration API.
 * Gracefully no-ops on desktop or unsupported devices.
 */
export function haptic(type: "selection" | "impact" | "success" | "warning" = "selection") {
  if (typeof navigator === "undefined" || !navigator.vibrate) return;
  const patterns: Record<typeof type, number | number[]> = {
    selection: 8,
    impact:    15,
    success:   [10, 50, 10],
    warning:   [20, 40, 20],
  };
  navigator.vibrate(patterns[type]);
}
