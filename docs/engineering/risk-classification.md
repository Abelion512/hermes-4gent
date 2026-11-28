# Risk Classification

## Purpose

Every PR is assigned a **risk tier** that determines the approval requirements. Higher tiers require more evidence, more reviews, and explicit human approval before merge.

> **Rule 5 from the Blueprint:** *Human release authority — tidak ada merge atau deployment berisiko tanpa approval.*

## Risk Tiers

| Tier | Name | Max Lines Changed | Review Required | CI Required | Human Approval |
|------|------|-------------------|----------------|-------------|----------------|
| **T0** | Trivial | ≤ 20 | 0 | 0 | NO — auto-merge |
| **T1** | Low | ≤ 100 | 1 | 1 | NO — Hermes can merge |
| **T2** | Medium | ≤ 500 | 1 | 2 | YES |
| **T3** | High | ≤ 2000 | 2 | 3+ | YES (explicit) |
| **T4** | Critical | Any | 2+ | 3+ | YES (explicit + written) |

### Tier Details

#### T0 — Trivial
- Pure refactors, test-only changes, documentation fixes.
- No user-facing behavior change.
- Examples: typo fix, comment update, formatting.
- **Merge:** Auto-merge if CI passes (no human needed).

#### T1 — Low
- Small bug fixes, minor feature additions.
- Limited scope, low blast radius.
- Examples: config parsing fix, logging improvement.
- **Merge:** Hermes merges if CI passes and 1 review approved.

#### T2 — Medium
- Logic changes, new API endpoints, moderate test additions.
- Moderate blast radius — could affect multiple users.
- Examples: vault backend fix, CLI command change.
- **Merge:** Human founder must approve.

#### T3 — High
- Architecture changes, security-sensitive code, credential handling.
- Broad blast radius — could affect many users or cause data loss.
- Examples: vault unlock flow, session token management.
- **Merge:** Human founder must explicitly approve. Hermes does not auto-merge.

#### T4 — Critical
- Security vulnerabilities, breaking API changes, data model changes.
- Full blast radius — system-wide impact.
- Examples: credential store rewrite, protocol change.
- **Merge:** Human founder must explicitly approve + sign off. Hermes blocks.

## Risk Classification Factors

A PR is classified by the **highest** applicable factor:

| Factor | Adds 1 Tier |
|--------|------------|
| Changes credential handling (tokens, passwords, API keys) | +2 |
| Changes subprocess execution or shell commands | +1 |
| Changes network/HTTP behavior | +1 |
| Changes on-disk file I/O or persistence | +1 |
| Changes session state or concurrency | +1 |
| Changes user-facing API or CLI | +1 |
| New dependency added | +1 |
| Security-relevant area (auth, crypto, secrets) | +2 |
| No new tests added | +1 (from base) |
| No RED test verification | +1 |
| Test failures at HEAD | +2 |
| CI checks missing or not passing | +1 |

### Base calculation
1. Start at T0 (≤20 lines).
2. Add tiers for each factor above (sum the additions).
3. Cap at T4.

### Example
A 158-line vault backend change with credential handling and concurrency:
- Base: T1 (≤100 lines)
- +2: changes credential/session token handling
- +1: changes subprocess execution (`bw sync`)
- +1: changes concurrency (module-level lock, module-level `_LAST_SYNC` dict)
- **Total: T4 (Critical)**

## Approval Requirements by Tier

### T0
- ✅ CI passing (if any checks exist)
- ✅ Auto-merge

### T1
- ✅ 1 independent review (approved)
- ✅ CI passing (if checks exist)
- ⬜ Hermes merges after review

### T2
- ✅ 1 independent review (approved)
- ✅ All required CI checks passing
- ✅ Founder approval (Hermes blocks merge until approval)

### T3
- ✅ 2 independent reviews
- ✅ All required CI checks passing (≥2)
- ✅ Founder explicit approval (Hermes blocks merge)
- ✅ Risk acknowledgment in review packet

### T4
- ✅ 2+ independent reviews (at least one security-focused)
- ✅ All required CI checks passing (≥3)
- ✅ Founder explicit + written approval
- ✅ Written risk acknowledgment
- ✅ Post-merge monitoring plan

## Merge Blocking

Hermes **must not merge** if:
- Risk tier ≥ T2 and no Founder approval
- Risk tier ≥ T1 and no independent review
- Any CI check is failing
- Any review has `CHANGES_REQUESTED`
- Test failures at HEAD (GREEN not achieved)

Hermes **must** block and escalate to Founder for:
- T3 and above
- Any security findings from review
- CI missing entirely (no required checks configured)
