/**
 * Turning a timestamp into "how long ago".
 *
 * `now` is a parameter rather than a call to `Date.now()` inside the function, for the
 * same reason the backend passes a reference date into its rules: otherwise the expected
 * values in a test change while the test is running.
 */

/** Whole days between an ISO timestamp and `now`, rounded down. Negative values clamp to 0. */
export function daysSince(isoTimestamp: string, now: Date): number {
  const then = new Date(isoTimestamp).getTime();
  if (Number.isNaN(then)) {
    return Number.NaN;
  }

  const milliseconds = now.getTime() - then;

  return Math.max(0, Math.floor(milliseconds / 86_400_000));
}

/** A short human label for an age, for a table cell that has to stay narrow. */
export function describeAge(isoTimestamp: string, now: Date): string {
  const days = daysSince(isoTimestamp, now);
  if (Number.isNaN(days)) {
    return 'unknown';
  }

  if (days === 0) {
    return 'today';
  }

  return days === 1 ? '1 day ago' : `${days} days ago`;
}
