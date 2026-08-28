"""Run a Job in a test on any supported Nautobot version.

Nautobot 3.1 takes loose keyword arguments; 3.2 requires ``job_kwargs``. This app supports both.
"""

import inspect

from nautobot.apps.testing import run_job_for_testing

SUPPORTS_JOB_KWARGS = "job_kwargs" in inspect.signature(run_job_for_testing).parameters


def run_job(job_model, **variables):
    """Run a Job with the given input variables.

    Args:
        job_model: The installed Job to run.
        **variables: The Job's input variables.

    Returns:
        JobResult: The result of the run.
    """
    if SUPPORTS_JOB_KWARGS:
        return run_job_for_testing(job_model, job_kwargs=variables)
    return run_job_for_testing(job_model, **variables)
