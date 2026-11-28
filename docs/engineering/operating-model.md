# Engineering Operating Model

## Purpose

This document defines how Hermes acts as the **CEO / orchestrator** of a human-controlled agentic engineering workflow. It is not a framework, not an agent, and not a dashboard. It is a *contract* for how work moves from human intent to verified, approved software.

> **Standing principle:** One human can direct, supervise, and release software with agent assistance, without blindly trusting any agent.

## Roles

| Role | Human/AI | Responsibility | Decision Authority |
|------|----------|----------------|--------------------|
| **Founder** | Human | Defines what to build, final approval on merge/deploy | ✅ FINAL |
| **Hermes (CEO)** | AI orchestrator | Breaks work into tasks, assigns agents, collects evidence, synthesizes findings | ❌ none |
| **Engineer** | AI (Claude Code / OpenCode) | Implements code, writes tests, documents | ❌ none |
| **Independent Reviewer** | AI (separate instance) | Finds defects, security issues, logic bugs | ❌ none |
| **Verifier** | AI + CI | Runs tests, validates RED/GREEN, checks CI | ❌ none |
| **CI (GitHub Actions)** | Automated | Repeatable proof of quality | ✅ PASS/FAIL |

## Workflow Phases

Every task passes through **all** phases. Hermes may start the next phase while the previous one is still running (pipelining), but no phase is skipped.

### Phase 1 — Human Specification
- **Input:** Founder states the problem + acceptance criteria.
- **Output:** Written spec in `docs/engineering/specs/<slug>.md`.
- **Acceptance:** Founder has reviewed and signed off (comment on task card).

### Phase 2 — Hermes Orchestration
- Hermes reads the spec, creates child tasks in the kanban board.
- Each task gets:
  - Isolated worktree (branch, outside `~/.hermes/`).
  - Exact upstream base SHA and PR head SHA (if auditing an existing PR).
  - Assigned reviewer and verifier.
- **No code is written in this phase.**

### Phase 3 — Agent Implementation
- Engineer agent writes code + tests.
- Uses TDD: tests written first, then implementation.
- Every change has a test, every test has expected output.

### Phase 4 — Independent Review
- A *different* AI instance (or human) reviews the diff.
- Uses the `code-review-and-quality` skill.
- Findings recorded in the Engineering Review Packet.
- Reviewer does **not** approve merge — only flags issues.

### Phase 5 — Automated Verification
- Verifier checks RED (tests fail at base) and GREEN (tests pass at head).
- CI status checked via GitHub API.
- Evidence is attached to the packet with labels (`VERIFIED`, `PASS`, `FAIL`, `UNVERIFIED`).

### Phase 6 — Human Approval
- Founder reads the packet.
- Checks: spec met, evidence verified, risks acceptable, CI green, review complete.
- Decision: `APPROVE` | `REQUEST_CHANGES` | `HOLD`.

### Phase 7 — Merge & Monitor
- If approved, Hermes merges via PR (never direct push to `main`).
- `git worktree prune` runs to clean up.
- Post-merge: monitor for regressions (CI, canary, or manual).

## Isolation Rules

1. **Repository:** Audit work happens against `NousResearch/hermes-agent` (upstream). Deliverables (docs, templates, audit packets) go in `Abelion512/hermes-4gent` (fork). Never mix.
2. **Worktrees:** Every PR audit gets a git worktree at `/tmp/` (not under `~/.hermes/`) to avoid I/O guard conflicts.
3. **Reviews:** The Engineer does **not** review their own code. A separate instance (or human) must review.

## Evidence Contract

Every claim in the Engineering Review Packet must be labeled:

| Label | Meaning | Example |
|-------|---------|---------|
| `VERIFIED` | Directly confirmed via tool | "RED: 6/6 new tests fail (output)" |
| `PASS` | Test suite result | "GREEN: 19/19 pass" |
| `FAIL` | Test suite result | "1 test fails: _LAST_SYNC missing" |
| `UNVERIFIED` | Claimed but not confirmed | "CI green (claimed by author)" |
| `SKIPPED` | Intentionally not run | "test_vault_key_storage.py skipped (missing keyring)" |

## File Layout

```
docs/engineering/
├── operating-model.md          ← this file
├── review-protocol.md          ← how reviews work
├── risk-classification.md      ← tier system + approval gates
└── specs/                      ← human specifications (per task)
    └── <slug>.md

templates/
└── ENGINEERING_REVIEW_PACKET.md ← mandatory audit template
```

## Lifecycle Management

- Hermes is the **orchestrator**, not the executor. Hermes delegates work, collects results, and synthesizes.
- Hermes does **not** write production code. Hermes does **not** merge. Hermes does **not** override human decisions.
- Hermes **does** enforce the contract: spec → code → review → evidence → approval → merge.
