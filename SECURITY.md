# Security Policy

## Supported versions

Security fixes target the latest released version and the default branch.

## Reporting a vulnerability

Please do not open a public issue for sensitive vulnerabilities. Report concerns through GitHub private vulnerability reporting if enabled, or contact the maintainers privately with:

- Affected version or commit.
- Reproduction steps.
- Impact assessment.
- Any suggested mitigation.

## Scope

In scope:

- Unsafe handling of API credentials, private keys, or authenticated requests.
- Secrets exposure in logs, examples, or client configuration.
- Dependency vulnerabilities.
- Incorrect order book, REST, or WebSocket parsing that could cause unsafe trading behavior when integrated downstream.

Out of scope:

- Strategy profitability claims.
- Exchange API availability, rate limits, or market-data quality issues outside this package.
- Vulnerabilities requiring compromised local developer machines.

## Maintainer response target

We aim to acknowledge reports within 3 business days and provide a remediation plan or status update within 10 business days.
