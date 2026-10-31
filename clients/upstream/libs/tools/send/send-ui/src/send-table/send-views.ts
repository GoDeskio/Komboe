// Komboe: view-count display for Sends ("expiring secure links").

export type SendViews = {
  /** e.g. "3 / 10" with a limit, or "3" without */
  label: string;
  /** views left before the link stops working, or null when unlimited */
  remaining: number | null;
};

export function sendViews(accessCount: number | null | undefined, maxAccessCount: number | null | undefined): SendViews {
  const used = Math.max(0, Number(accessCount) || 0);
  if (maxAccessCount == null || !Number.isFinite(Number(maxAccessCount))) {
    return { label: String(used), remaining: null };
  }
  const max = Math.max(0, Number(maxAccessCount));
  return { label: `${used} / ${max}`, remaining: Math.max(0, max - used) };
}
