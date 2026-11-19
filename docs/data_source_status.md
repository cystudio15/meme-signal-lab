# Data Source Reliability Register

Last reviewed: 2026-11-18 (Asia/Shanghai)

This document records what each source contributes, how it was collected and what it cannot prove. The dashboard treats missing or secondary evidence as a visible state rather than silently replacing it.

## Source matrix

| Source | Access mode | Used for | Reliability boundary |
| --- | --- | --- | --- |
| X | Official API, bounded queries | Posts, authors, interactions and quote edges | A query-limited sample, not a complete copy of X |
| GeckoTerminal | Public API and timestamped snapshots | Pool identity and OHLCV | Availability and rate limits vary |
| Public announcements | Manual verification | Event time, contract and listing context | Confirms the announcement, not market impact |
| Secondary market history | Cross-checked public pages | NIULAI daily context | Not a substitute for pool-level execution data |
| Token analytics pages | Timestamped manual snapshots | Holder, risk and liquidity context | Dynamic values must be refreshed |

Machine-readable registrations are stored in `data/sources/source_registry.csv`.

## X collection

The Go collector supports query windows, pagination, retries, result limits and raw-response preservation. Processed records use `post_id` as the de-duplication key and retain query provenance.

Public snapshots currently support two different research designs:

- **AX1:** bounded launch-period queries plus quote-network expansion.
- **NIULAI:** historical time-window samples plus a continuous recent observation window.

Historical windows are never presented as full-volume monthly counts. Every collection run is capped by result count and keeps an auditable query window.

## Market data

Hourly market series are aligned to social activity using UTC event time and converted to Asia/Shanghai only for display. This supports statements about sequence, co-movement and divergence. It does not establish that a post caused a price move.

NIULAI also includes a daily fallback series cross-checked between two secondary sources. It supports daily context but not 15-minute, one-hour or pool-execution claims.

## Failure handling

Collectors distinguish the following states:

- valid empty response;
- authentication or rate-limit error;
- DNS or connection failure;
- request timeout;
- malformed or changed JSON schema;
- valid response with missing required fields.

A failed request does not generate substitute observations. The pipeline either retains the last timestamped evidence with a clear status or leaves the field missing.

## Re-verification requirements

The following fields are time-sensitive and must be refreshed before operational use:

- liquidity, volume and transaction counts;
- holder concentration, developer balances and wallet labels;
- mint, blacklist, pause and trading permissions;
- slippage, MEV exposure and exit capacity.

The public dashboard is therefore a reproducible research snapshot, not a live trading terminal.
