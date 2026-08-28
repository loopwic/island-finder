# Security policy

## Reporting a vulnerability

Please do not open a public issue for vulnerabilities involving controller
input safety, local API access, path traversal, captured personal data, or
dependency compromise. Use GitHub's **Report a vulnerability** flow in the
Security tab of this repository.

Include the affected version or commit, operating system, reproduction steps,
expected safe behavior, and whether real controller hardware was connected.
Do not attach account screenshots, firmware backups, access tokens, console
identifiers, or other private material.

## Scope

The supported security boundary is the local application listening on
`127.0.0.1`. Running it on a public interface, modifying it to accept remote
controller commands, or distributing private firmware and game data is outside
the supported configuration.
