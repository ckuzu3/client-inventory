/**
 * The shapes the API returns.
 *
 * These mirror the response models in the backend's `schemas.py`. They are written by
 * hand rather than generated: the OpenAPI document is right there, and generating from
 * it would be the better answer for a larger surface, but for six endpoints a reviewer
 * can read these in one screen and see exactly what the frontend relies on.
 */

/** Severity of a single finding, worst first in the API's ordering. */
export type Severity = 'high' | 'medium' | 'low';

/**
 * The stable identifier of a baseline rule.
 *
 * `(string & {})` keeps the known codes autocompleting while still accepting a code a
 * newer backend adds, so an unknown rule shows up in the table instead of breaking it.
 */
export type FindingCode =
  | 'os_version_below_baseline'
  | 'os_version_unreadable'
  | 'encryption_disabled'
  | 'patch_level_unknown'
  | 'patch_level_outdated'
  | 'not_seen_recently'
  | 'disk_space_low'
  | (string & {});

/** One baseline rule a client does not satisfy. */
export interface Finding {
  readonly code: FindingCode;
  readonly severity: Severity;
  readonly detail: string;
}

/** The current state of one client, as the API evaluated it. */
export interface Client {
  readonly hostname: string;
  readonly os_name: string;
  readonly os_version: string;
  readonly agent_version: string;
  readonly encryption_enabled: boolean;
  readonly disk_total_gb: number;
  readonly disk_free_gb: number;
  readonly free_disk_percent: number | null;
  readonly last_patched_at: string | null;
  readonly first_seen_at: string;
  readonly last_seen_at: string;
  readonly compliant: boolean;
  readonly findings: readonly Finding[];
}

/** One page of clients. */
export interface ClientPage {
  readonly items: readonly Client[];
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

/** Fleet-wide counts. */
export interface ComplianceSummary {
  readonly evaluated_at: string;
  readonly total_clients: number;
  readonly compliant_clients: number;
  readonly noncompliant_clients: number;
  readonly findings_by_code: Readonly<Record<string, number>>;
  readonly findings_by_severity: Readonly<Record<string, number>>;
}

/** The rules the fleet is measured against. */
export interface Baseline {
  readonly minimum_os_version: string;
  readonly os_version_applies_to: string;
  readonly require_encryption: boolean;
  readonly maximum_patch_age_days: number;
  readonly maximum_last_seen_age_days: number;
  readonly minimum_disk_free_percent: number;
}

/** Query parameters the client list accepts. */
export interface ClientQuery {
  readonly limit: number;
  readonly offset: number;
  readonly onlyWithFindings: boolean;
  readonly osName: string | null;
}
