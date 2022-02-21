# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3] - 2022-02-21
### Added
 - Add `AccessClient.contract_id` property
 - Add `DIPRequest.dip_id` property
 - Add the functionality to fetch ingest reports as three new methods in the `AccessClient` class: `get_ingest_report_entries`, `get_ingest_report` and `get_latest_ingest_report`.
 - Add the functionality to fetch ingest reports to the CLI.

### Changed
 - `DIPRequest.poll` renamed to `DIPRequest.check_status`
 - `DIPRequest.poll` argument `block` renamed to `poll`
 - Changed CLI commands `download` and `delete` to be grouped under the command `dip`

## [0.2] - 2022-01-04

 - No user-facing changes

## 0.1 - 2021-10-16
### Added
 - First release of dpres-access-rest-api-client

[0.3]: https://github.com/Digital-Preservation-Finland/access-rest-api-client/compare/v0.2...v0.3
[0.2]: https://github.com/Digital-Preservation-Finland/access-rest-api-client/compare/v0.1...v0.2
[Unreleased]: https://github.com/Digital-Preservation-Finland/access-rest-api-client/compare/v0.3...HEAD
