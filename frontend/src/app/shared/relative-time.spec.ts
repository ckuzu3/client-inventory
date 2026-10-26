import { daysSince, describeAge } from './relative-time';

const NOW = new Date('2026-10-27T12:00:00Z');

describe('daysSince', () => {
  it('counts whole days and rounds down', () => {
    expect(daysSince('2026-10-17T12:00:00Z', NOW)).toBe(10);
    expect(daysSince('2026-10-26T00:00:00Z', NOW)).toBe(1);
  });

  it('reports the same day as zero', () => {
    expect(daysSince('2026-10-27T06:00:00Z', NOW)).toBe(0);
  });

  it('clamps a timestamp from the future to zero rather than returning a negative age', () => {
    expect(daysSince('2026-10-28T12:00:00Z', NOW)).toBe(0);
  });

  it('returns NaN for something that is not a timestamp', () => {
    expect(daysSince('not a date', NOW)).toBeNaN();
  });
});

describe('describeAge', () => {
  it('uses a singular day where that reads better', () => {
    expect(describeAge('2026-10-26T06:00:00Z', NOW)).toBe('1 day ago');
  });

  it('says today instead of "0 days ago"', () => {
    expect(describeAge('2026-10-27T09:00:00Z', NOW)).toBe('today');
  });

  it('counts the days otherwise', () => {
    expect(describeAge('2026-09-11T00:00:00Z', NOW)).toBe('46 days ago');
  });

  it('says unknown rather than NaN for an unparsable value', () => {
    expect(describeAge('', NOW)).toBe('unknown');
  });
});
