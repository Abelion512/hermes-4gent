"""Cron log lines must not carry prompt text.

A job's ``name`` falls back to its prompt prefix (cron/jobs.py::_normalize_job_record),
so both the "Running job" and "Prompt:" lines can leak credentials pasted into a prompt.
Test the emitted records, not the source text.
"""

import logging

import pytest

# Synthetic key, never a real credential.
FAKE_SECRET = "sk-" + "A" * 32
JOB_ID = "job-secret-log"


def test_run_job_logs_id_and_length_not_prompt_or_name(caplog, monkeypatch):
    from cron import scheduler

    # no_agent keeps run_job on this path instead of delegating to run_canonical_job;
    # _prepare_job_prompt is stubbed, so the script branch itself is never entered.
    job = {"id": JOB_ID, "prompt": f"rotate {FAKE_SECRET} now", "deliver": "local", "no_agent": True}

    def _prepare(_job, _job_id, job_name, _extra_prompt, _cancel_event):
        # The name really is prompt-derived on this path; the log must still be safe.
        assert job_name == job["prompt"]
        return None, f"# Cron Job\n\n{FAKE_SECRET}\n"

    class _StopBeforeAgent:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("stop after prompt log")

    monkeypatch.setattr(scheduler, "_prepare_job_prompt", _prepare)
    monkeypatch.setattr(scheduler, "_CronRunScope", _StopBeforeAgent)

    with caplog.at_level(logging.INFO, logger="cron.scheduler"):
        with pytest.raises(RuntimeError, match="stop after prompt log"):
            scheduler.run_job(job)

    assert FAKE_SECRET not in caplog.text
    assert JOB_ID in caplog.text
    assert "Prompt: " in caplog.text


def test_unresolved_delivery_logs_id_not_prompt_derived_name(caplog):
    from cron.scheduler_delivery import _unresolved_delivery_outcome

    job = {"id": JOB_ID, "name": f"rotate {FAKE_SECRET} now", "deliver": "origin"}
    # scheduler_delivery logs through the shared "cron.scheduler" logger.
    with caplog.at_level(logging.INFO, logger="cron.scheduler"):
        assert _unresolved_delivery_outcome(job, for_failure=False, skipped=[]) is None

    assert FAKE_SECRET not in caplog.text
    assert JOB_ID in caplog.text
