"""Write and prune the record of what a run spent.

This app makes no model call, so it records nothing of its own accord. This module is the one
write helper a consuming app calls after it makes a call, and the one place that freezes the money.

The freeze is the point. ``AIModel.input_cost_per_million`` changes when a vendor changes its
price, and a cost worked out on read would quietly reprice last quarter. This module works the cost
out once, at the price of the day, and stores it.
"""

import logging
from decimal import Decimal

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
