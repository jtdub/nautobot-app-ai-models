"""Record what one model call spent, and what it cost at the price of the day.

One table and no data. It is a ``BaseModel``, so there is no change-log mixin block here: a row
lands on every model call, and change logging every one of them would double the write cost.
"""

import uuid

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_ai_models", "0006_mcp_resources_and_prompts"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIUsageRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("cached_input_tokens", models.PositiveIntegerField(default=0)),
                ("reasoning_tokens", models.PositiveIntegerField(default=0)),
                (
                    "input_cost",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "output_cost",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("usage_payload", models.JSONField(blank=True, default=dict)),
                ("recorded_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="usage_records",
                        to="nautobot_ai_models.aiagent",
                    ),
                ),
                (
                    "model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="usage_records",
                        to="nautobot_ai_models.aimodel",
                    ),
                ),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_records",
                        to="nautobot_ai_models.aiagentthread",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Usage Record",
                "verbose_name_plural": "AI Usage Records",
                "ordering": ["-recorded_at", "pk"],
                "get_latest_by": "recorded_at",
                "indexes": [
                    models.Index(fields=["thread", "recorded_at"], name="nb_ai_usage_thread_recd"),
                    models.Index(fields=["model", "recorded_at"], name="nb_ai_usage_model_recd"),
                    models.Index(fields=["agent", "recorded_at"], name="nb_ai_usage_agent_recd"),
                ],
            },
        ),
    ]
