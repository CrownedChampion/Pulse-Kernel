# Pulse P1 security policy

**Current release is development code, not yet bootable/certified/production-ready.**

Report vulnerabilities privately using GitHub's **Report a vulnerability** feature (private security advisories) on the project's public repository when enabled. Do not submit exploits with live user keys, secrets, personal files, or malware samples to a public issue. No project email address has been configured or verified.

Scope: Pulse P1 Linux-derived kernel build modifications, Pulse platform services, signed update verification, sandbox tools, Secure Rift lifecycle and Pace-specific optional identity shim. Linux upstream security defects should also be reported through applicable upstream channels according to coordinated-disclosure guidance.

Protection limitations: the signed manifest does not authenticate a firmware-to-root boot chain; dm-verity and MAC policies are not yet deployed; Secure Rift per-app portal and real cryptographic operation testing are not complete. A compromised kernel, hostile firmware, privileged process, stolen authentication material or compromised user session may defeat protections. Secure Rift must not be used for irreplaceable real secrets in this preview.

Release-gate evidence: `docs/RELEASE_ACCEPTANCE_P1.md`. Independent security assessment is required before security certification claims. P1 version branding remains fixed until owner authorization.
