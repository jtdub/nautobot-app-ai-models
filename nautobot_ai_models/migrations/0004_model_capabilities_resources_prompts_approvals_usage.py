"""One migration for the release that follows the agents release.

It records what a model can do, records that a person accepted what a tool binding
offers, records the other two things an MCP server advertises, and records what one
model call spent. The four changes were authored and shipped together, so they are
one migration and the intermediate numbers do not exist.

The model capability columns are nullable and carry no data: every column stays empty
on an existing row, because nobody has recorded the answer yet. An empty value is not
a "no".

The approval table is a log: a row is written once, and a withdrawal is a
``revoked_at`` stamp rather than a delete. There is no uniqueness constraint, because
a binding can be approved, withdrawn, and approved again.

Neither the resource table nor the prompt table carries a ``writable`` column: a
resource is read by protocol, and a prompt is chosen by a person.

The usage table is a ``BaseModel``, so there is no change-log mixin block: a row lands
on every model call, and change logging every one of them would double the write cost.
"""

import uuid

import django.core.serializers.json
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import nautobot.extras.models.mixins
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_ai_models", "0003_agents"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="aimodel",
            name="context_window",
            field=models.PositiveIntegerField(
                blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)]
            ),
        ),
        migrations.AddField(
            model_name="aimodel",
            name="max_output_tokens",
            field=models.PositiveIntegerField(
                blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)]
            ),
        ),
        migrations.AddField(
            model_name="aimodel",
            name="supports_structured_output",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="aimodel",
            name="supports_tools",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="aimodel",
            name="supports_vision",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="AIToolApproval",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "_custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
                ),
                ("fingerprint", models.CharField(blank=True, max_length=255)),
                ("approved_by_name", models.CharField(blank=True, max_length=255)),
                ("approved_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_by_name", models.CharField(blank=True, max_length=255)),
                ("note", models.TextField(blank=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_tool_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "binding",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approvals",
                        to="nautobot_ai_models.aiagenttool",
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="revoked_ai_tool_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Tool Approval",
                "verbose_name_plural": "AI Tool Approvals",
                "ordering": ["-approved_at", "pk"],
                "get_latest_by": "approved_at",
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="MCPPrompt",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "_custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
                ),
                ("name", models.CharField(max_length=255)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("arguments", models.JSONField(blank=True, default=list)),
                ("enabled", models.BooleanField(default=True)),
                ("definition_fingerprint", models.CharField(blank=True, max_length=255)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "mcp_server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prompts",
                        to="nautobot_ai_models.mcpserver",
                    ),
                ),
            ],
            options={
                "verbose_name": "MCP Prompt",
                "verbose_name_plural": "MCP Prompts",
                "ordering": ["mcp_server__name", "name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("mcp_server", "name"), name="nautobot_ai_models_mcpprompt_unique_server_name"
                    )
                ],
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="MCPResource",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "_custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
                ),
                ("uri", models.CharField(max_length=255)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("mime_type", models.CharField(blank=True, max_length=255)),
                ("is_template", models.BooleanField(default=False)),
                ("size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("annotations", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("definition_fingerprint", models.CharField(blank=True, max_length=255)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "mcp_server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resources",
                        to="nautobot_ai_models.mcpserver",
                    ),
                ),
            ],
            options={
                "verbose_name": "MCP Resource",
                "verbose_name_plural": "MCP Resources",
                "ordering": ["mcp_server__name", "uri"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("mcp_server", "uri"), name="nautobot_ai_models_mcpresource_unique_server_uri"
                    )
                ],
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
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
