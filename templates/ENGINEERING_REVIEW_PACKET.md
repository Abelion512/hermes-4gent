# Engineering Review Packet

**PR:** #{{pr_number}} — {{title}}
**Author:** {{author}}
**Base:** {{base_repo}} @ {{base_sha}}
**Head:** {{head_repo}} @ {{head_sha}}
**Risk Tier:** {{tier}} (see `docs/engineering/risk-classification.md`)
**Auditor:** {{auditor}}
**Date:** {{date}}
**Status:** {{status}}

---

## 1. Human Specification

### Problem
> What user-facing problem does this PR solve? Quote from the PR body.

### Proposed Solution
> How does the PR solve it? Quote from the PR body.

### Acceptance Criteria (from PR body or issue)
- [ ] Criterion 1
- [ ] Criterion 2

---

## 2. Hermes Orchestration

### Reviewer Assignment
| Role | Assignee | Tool |
|------|----------|------|
| Engineering Orchestrator (CEO) | Hermes | — |
| Engineer (implementation) | {{author}} | Claude Code / OpenCode |
| Independent Reviewer | {{reviewer}} | code-review-and-quality skill |
| Verifier (tests + CI) | {{verifier}} | terminal / `gh` |
| Human Approval Gate | {{human}} | Founder |

### Work Isolation
- Branch: `{{branch_name}}`
- Worktree: `{{worktree_path}}` (outside `~/.hermes/`, e.g. `/tmp/`)
- Repository boundary: fork = `Abelion512/hermes-4gent`, upstream = `NousResearch/hermes-agent`

### Evidence Requirements
All claims below must carry a label:
- `VERIFIED (URL, HTTP <code>)` — directly confirmed
- `PASS (output)` — test output with pass/fail counts
- `FAIL (reason)` — test output with failure details
- `UNVERIFIED` — claimed but not yet confirmed
- `SKIPPED (reason)` — test intentionally not run

---

## 3. Agent Implementation

### Files Changed
| File | Status | Lines +/- |
|------|--------|-----------|
| {{file1}} | {{modified/new}} | +{{a}}/−{{b}} |

### Source Code Review
| File | Reviewer | Key Findings |
|------|----------|-------------|
| {{file1}} | {{reviewer}} | - {{finding1}}\n- {{finding2}} |

### Change Size
- `{{num_files}}` files changed, `{{total_additions}}+/−{{total_deletions}}`
- Functions/methods added: {{functions_added}}
- New test cases: {{tests_added}}

---

## 4. Independent Review

### Automated Code Review
Run via `code-review-and-quality` skill (or `ruff check`):
```
{{ruff_output}}
```
- `ruff check`: {{ruff_status}}
- `ruff format --check`: {{format_status}}

### Manual Code Review (Independent Reviewer)
| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| {{issue1_id}} | {{critical/high/medium/low}} | {{file:line}} | {{description}} |

**Summary:** {{N}} findings — {{critical_count}} critical, {{high_count}} high, {{medium_count}} medium, {{low_count}} low.

---

## 5. Automated Verification

### RED Test (base SHA — before PR changes)
Checked out `{{base_sha}}` to `/tmp/` worktree. Applied ONLY the test-file changes from the PR (extracted via `git checkout {{head_sha}} -- <test_files>`).

```
{{red_test_output}}
```
- New tests that **FAIL** at base: {{red_fail_count}}/{{total_new}}
- New tests that **PASS** at base (false green): {{red_pass_count}}/{{total_new}}

### GREEN Test (PR head SHA — with PR changes)
Checked out `{{head_sha}}` to `/tmp/` worktree.

```
{{green_test_output}}
```
- New tests that **PASS** at head: {{green_pass_count}}/{{total_new}}
- New tests that **FAIL** at head: {{green_fail_count}}/{{total_new}}

### Baseline vs. Head Comparison
| Metric | Base | Head | Delta |
|--------|------|------|-------|
| Tests collected | {{base_collected}} | {{head_collected}} | {{delta_collected}} |
| Tests passed | {{base_pass}} | {{head_pass}} | {{delta_pass}} |
| Tests failed | {{base_fail}} | {{head_fail}} | {{delta_fail}} |
| Tests skipped | {{base_skip}} | {{head_skip}} | {{delta_skip}} |

### CI Status
```
{{ci_status_output}}
```
- Required status checks: {{ci_required_count}}
- Checks passing: {{ci_passing}}
- Checks failing: {{ci_failing}}
- Checks pending: {{ci_pending}}
- GitHub `mergeStateStatus`: {{merge_state}}
- Branch protections: {{branch_protections}}

---

## 6. Risk Assessment

### Security
| Risk | Severity | Mitigated? | Evidence |
|------|----------|-----------|----------|
| {{risk1}} | {{critical/high/medium}} | {{yes/no/partial}} | {{evidence}} |

### Regression
| Area | Test Coverage | Regression Risk |
|------|--------------|-----------------|
| {{area1}} | {{coverage}} | {{low/medium/high}} |

### Dependencies
| Dependency | Before | After | Risk |
|-----------|--------|-------|------|
| (none new if applicable) | — | — | — |

---

## 7. Discrepancies from Previous Review

| Previous Issue | Resolved? | Evidence |
|---------------|-----------|----------|
| {{prev_issue1}} | {{yes/no}} | {{evidence1}} |

---

## 8. Human Approval Gate

### Decision Matrix
| Gate | Requirement | Status | Approver |
|------|------------|--------|----------|
| Spec | Human-written or explicitly accepted | {{status}} | {{human}} |
| CI | All required checks pass | {{status}} | — |
| Code Review | At least 1 independent review | {{status}} | {{reviewer}} |
| Risk Threshold | Tier ≤ {{approved_tier}} | {{status}} | {{human}} |
| Final Merge | Human approval | {{status}} | {{human}} |

### Final Recommendation
**{{APPROVE | REQUEST_CHANGES | HOLD}}**

Rationale: {{rationale}}

### Approval
- Human Founder: [\_\_\_/Signature] \_\_\_\_\_\_\_\_\_\_\_\_
- Date: \_\_\_\_\_\_\_\_
- Merge commit (if approved): \_\_\_\_\_\_\_\_

---

*Generated by Hermes Engineering Orchestrator — see `docs/engineering/operating-model.md`*
