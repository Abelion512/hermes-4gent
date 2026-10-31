# Review Protocol

## Objective

Every code change must pass **independent review** — the Engineer who wrote the code must **not** be the only reviewer. This protocol defines how reviews happen, what they check, and how findings are recorded.

> **Rule 4 from the Blueprint:** *Independent review — pembuat kode tidak boleh menjadi satu-satunya reviewer.*

## Reviewer Assignment

For each PR audit:
1. Hermes assigns an **Independent Reviewer** — a separate AI instance or human.
2. The reviewer gets the full diff + context (PR body, related issues, test output).
3. The reviewer does **not** write code — only finds and reports issues.
4. The reviewer's output is recorded in the **Engineering Review Packet**.

## Review Axes

The reviewer checks each of the following:

### 1. Logic Correctness
- Does the code do what the PR description says it does?
- Are edge cases handled?
- Are there off-by-one errors, null dereferences, or similar bugs?

### 2. Security
- Does the change introduce new credential handling? Check for token leakage.
- Are new subprocess calls safe (no shell injection)?
- Does error handling leak sensitive data in logs?
- Are new dependencies pinned and from trusted sources?

### 3. Test Coverage
- Are all new code paths covered by tests?
- Do tests verify the **intent** of the change, not just that it runs?
- Are there tests for failure modes (network down, invalid input, expired tokens)?
- Do the tests pass at HEAD and fail at BASE (RED/GREEN)?

### 4. Code Quality
- `ruff check` passes (no lint errors).
- `ruff format --check` passes (formatting consistent).
- Code is readable and follows existing patterns.
- No dead code, no debug prints, no commented-out blocks.

### 5. Evidence Integrity
- All test output includes pass/fail counts.
- No test results are claimed without output.
- RED results are verified against the exact upstream base SHA.
- GREEN results are verified against the exact PR head SHA.

## Review Process

### Step 1: Read the Diff
- Review every changed file, line by line.
- For each function/method: understand the inputs, outputs, and side effects.

### Step 2: Check Against the Spec
- Verify the implementation matches the PR body's stated goals.
- Flag any gaps between spec and implementation.

### Step 3: Run Automated Checks
```bash
# Lint
ruff check <changed_files>

# Format
ruff format --check <changed_files>

# Type checking (if mypy configured)
mypy <changed_files>
```

### Step 4: Run Tests (RED and GREEN)
- **RED:** Checkout base SHA at `/tmp/`, apply ONLY test-file changes, run tests. New tests must **fail**.
- **GREEN:** Checkout PR head SHA at `/tmp/`, run tests. All tests must **pass**.

### Step 5: Record Findings
Record findings in the Engineering Review Packet:

| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| 001 | critical | file.py:42 | Token is logged to stdout |
| 002 | high | other.py:17 | Missing timeout on HTTP call |

**Severity scale:**
- `critical` — security vulnerability, data loss risk, credential leak
- `high` — correctness bug, crash on valid input, broken error handling
- `medium` — missing test, unclear error message, code smell
- `low` — formatting, naming, minor style

### Step 6: Synthesize
The reviewer produces a summary:
- Total findings by severity
- Any patterns (e.g., "3 tests are missing failure-mode coverage")
- Confidence level in the review (high/medium/low)

## Review Outcome

The reviewer's output feeds into the **Human Approval Gate**. The reviewer does **not** approve or reject — that is the Founder's role. The reviewer provides:

1. **Findings** (with severity and location)
2. **Evidence** (test output, lint output, code snippets)
3. **Confidence** (how thoroughly the reviewer examined the change)

## False-Positive Protocol

Findings may be false positives. The reviewer should:
- Label findings as `finding` or `possible finding`
- Explain reasoning (code snippet + explanation)
- Flag uncertainty explicitly

False positives are tracked in the review packet for process improvement.
