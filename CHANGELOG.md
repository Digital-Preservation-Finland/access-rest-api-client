# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
### Added
 - Add `AccessClient.contract_id` property
 - Add `DIPRequest.dip_id` property
 - Add the functionality to fetch ingest reports as three new methods in the `AccessClient` class: `get_ingest_report_entries`, `get_ingest_report` and `get_latest_ingest_report`.

### Changed
 - `DIPRequest.poll` renamed to `DIPRequest.check_status`
 - `DIPRequest.poll` argument `block` renamed to `poll`

## 0.1 - 2021-10-16
### Added
 - First release of dpres-access-rest-api-client

[Unreleased]: https://github.com/Digital-Preservation-Finland/access-rest-api-client/compare/v0.1...HEAD
