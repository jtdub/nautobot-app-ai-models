"""Run a Job in a test on any supported Nautobot version.

Nautobot 3.1 passes job variables to `run_job_for_testing()` as loose keyword arguments. Nautobot
3.2 added a `job_kwargs` parameter, made it mandatory, and deprecated the loose form. This app
supports both, so the tests call through here instead of picking one shape.
"""

import inspect

from nautobot.apps.testing import run_job_for_testing

SUPPORTS_JOB_KWARGS = "job_kwargs" in inspect.signature(run_job_for_testing).parameters


def run_job(job_model, **variables):
    """Run a Job model instance with the given input variables and return its JobResult."""
    if SUPPORTS_JOB_KWARGS:
        return run_job_for_testing(job_model, job_kwargs=variables)
    return run_job_for_testing(job_model, **variables)
