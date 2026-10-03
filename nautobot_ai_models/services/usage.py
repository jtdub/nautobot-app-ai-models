"""Write and prune the record of what a run spent.

This app makes no model call, so it records nothing of its own accord. This module is the one
write helper a consuming app calls after it makes a call, and the one place that freezes the money.

The freeze is the point. ``AIModel.input_cost_per_million`` changes when a vendor changes its
price, and a cost worked out on read would quietly reprice last quarter. This module works the cost
out once, at the price of the day, and stores it.
"""

# pylint: disable=cyclic-import

import logging
from datetime import datetime, time as dt_time, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from nautobot_ai_models.choices import AIUsageBudgetPeriodChoices
from nautobot_ai_models.constants import COST_DECIMAL_PLACES, TOKENS_PER_MILLION

logger = logging.getLogger(__name__)

QUANTUM = Decimal(1).scaleb(-COST_DECIMAL_PLACES)
"""The smallest amount a cost column holds."""


def cost_of(tokens, price_per_million):
    """What a number of tokens costs at one price.

    Args:
        tokens: How many tokens were spent.
        price_per_million: What a million of them cost, or None when nobody recorded a price.

    Returns:
        Decimal | None: The cost, rounded to the column's precision, or None when there is no
            price. None means unknown, not free.
    """
    if price_per_million is None:
        return None
    return (Decimal(tokens) * Decimal(price_per_million) / TOKENS_PER_MILLION).quantize(QUANTUM)


def record(thread, agent, ai_model, *, input_tokens=0, output_tokens=0, **extra):
    """Write one usage record, with the cost frozen at today's price.

    Args:
        thread: The AIAgentThread this call belongs to.
        agent: The AIAgent that made the call. A subagent call is its own.
        ai_model: The AIModel actually called.
        input_tokens: Tokens sent.
        output_tokens: Tokens returned.
        **extra: Any other column, such as ``cached_input_tokens``, ``reasoning_tokens``, or
            ``usage_payload``.

    Returns:
        AIUsageRecord: The saved row.
    """
    from nautobot_ai_models.models import AIUsageRecord  # pylint: disable=import-outside-toplevel

    usage = AIUsageRecord(
        thread=thread,
        agent=agent,
        model=ai_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost=cost_of(input_tokens, ai_model.input_cost_per_million),
        output_cost=cost_of(output_tokens, ai_model.output_cost_per_million),
        **extra,
    )
    usage.validated_save()
    return usage


def delete_for_threads(threads):
    """Delete every usage record of the given threads.

    ``PruneAgentThreads`` can keep the thread rows and drop only the state. Usage is state, and
    without this it would outlive every retention window the deployment set.

    Args:
        threads: A queryset or an iterable of AIAgentThread rows.

    Returns:
        int: How many records were deleted.
    """
    from nautobot_ai_models.models import AIUsageRecord  # pylint: disable=import-outside-toplevel

    deleted, _ = AIUsageRecord.objects.filter(thread__in=threads).delete()
    if deleted:
        logger.info("Deleted %s usage record(s).", deleted)
    return deleted


def period_start(period, now=None):
    """The start of the current calendar period in the server time zone.

    A day starts at midnight, a week on Monday, and a month on the first.

    Args:
        period: An `AIUsageBudgetPeriodChoices` value.
        now: The moment to anchor the period on, or now.

    Returns:
        datetime: An aware datetime at the start of the period.

    Raises:
        ValueError: The period is not one of the three.
    """
    now = now or timezone.now()
    local = timezone.localtime(now)
    if period == AIUsageBudgetPeriodChoices.DAY:
        start = datetime(local.year, local.month, local.day)
    elif period == AIUsageBudgetPeriodChoices.WEEK:
        monday = local.date() - timedelta(days=local.weekday())
        start = datetime.combine(monday, dt_time.min)
    elif period == AIUsageBudgetPeriodChoices.MONTH:
        start = datetime(local.year, local.month, 1)
    else:
        raise ValueError(f"Unknown budget period: {period!r}")
    return timezone.make_aware(start)


def spend(budget, *, now=None):
    """What a budget's scope spent since the start of its period.

    A missing cost counts as zero, because "nothing was recorded" must not read as "free".

    Args:
        budget: The AIUsageBudget to measure.
        now: The moment to anchor the period on, or now.

    Returns:
        tuple: ``(spent_cost, spent_tokens)``, the summed cost as a Decimal and the summed
            tokens as an int.
    """
    from nautobot_ai_models.models import AIUsageRecord  # pylint: disable=import-outside-toplevel

    records = AIUsageRecord.objects.filter(recorded_at__gte=period_start(budget.period, now))
    if budget.agent_id is not None:
        records = records.filter(agent=budget.agent)
    elif budget.model_id is not None:
        records = records.filter(model=budget.model)
    elif budget.tenant_id is not None:
        records = records.filter(agent__tenant=budget.tenant)

    totals = records.aggregate(
        cost=Coalesce(Sum("input_cost"), Decimal("0")) + Coalesce(Sum("output_cost"), Decimal("0")),
        tokens=Coalesce(Sum("input_tokens"), 0) + Coalesce(Sum("output_tokens"), 0),
    )
    return totals["cost"], totals["tokens"]


def budgets_for(ai_agent, ai_model):
    """The enabled budgets a call could hit.

    A call sits inside an agent, a model, and possibly a tenant, so any of the three scopes can
    apply.

    Args:
        ai_agent: The agent about to call.
        ai_model: The model about to be called.

    Returns:
        QuerySet: The enabled AIUsageBudget rows whose scope matches.
    """
    from nautobot_ai_models.models import AIUsageBudget  # pylint: disable=import-outside-toplevel

    scope = Q(agent=ai_agent) | Q(model=ai_model)
    if ai_agent.tenant_id is not None:
        scope |= Q(tenant=ai_agent.tenant)
    return AIUsageBudget.objects.filter(enabled=True).filter(scope)


def exceeded_budgets(ai_agent, ai_model, *, now=None):
    """The budgets a call would break.

    The consuming app calls this before a model call and refuses the call when the list is not
    empty.

    Args:
        ai_agent: The agent about to call.
        ai_model: The model about to be called.
        now: The moment to anchor the periods on, or now.

    Returns:
        list: The enabled budgets whose spend is at or over a limit.
    """
    exceeded = []
    for budget in budgets_for(ai_agent, ai_model):
        spent_cost, spent_tokens = spend(budget, now=now)
        if (budget.cost_limit is not None and spent_cost >= budget.cost_limit) or (
            budget.token_limit is not None and spent_tokens >= budget.token_limit
        ):
            exceeded.append(budget)
    return exceeded
