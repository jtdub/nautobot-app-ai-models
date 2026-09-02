"""Add the agent half of the registry: what an agent is, and what it may reach.

Seven tables and no data. Three tables hold what an operator writes (`AIAgent`, `AISkill`,
`AITool`), three bind them together (`AIAgentTool`, `AIAgentSubagent`, `AIAgentSkill`), and one
records a LangGraph thread (`AIAgentThread`).

Nothing here touches the tables that the LangGraph checkpointer creates. Those tables live outside
Django's migrations, the saver creates them itself, and `services/checkpoints.py` deletes from them.
"""

import uuid

import django.core.serializers.json
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import nautobot.core.models.fields
import nautobot.extras.models.mixins
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extras", "0142_remove_scheduledjob_approval_required"),
        ("nautobot_ai_models", "0002_registry_fields_for_consuming_apps"),
        ("tenancy", "0009_update_all_charfields_max_length_to_255"),
    ]

    operations = [
        migrations.CreateModel(
            name="AISkill",
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
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("body", models.TextField()),
                ("enabled", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "AI Skill",
                "verbose_name_plural": "AI Skills",
                "ordering": ["name"],
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="AIAgent",
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
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("system_prompt", models.TextField()),
                ("pattern", models.CharField(db_index=True, default="single", max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "temperature",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=4,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(2),
                        ],
                    ),
                ),
                (
                    "num_predict",
                    models.IntegerField(
                        blank=True, null=True, validators=[django.core.validators.MinValueValidator(-1)]
                    ),
                ),
                (
                    "max_iterations",
                    models.PositiveIntegerField(default=8, validators=[django.core.validators.MinValueValidator(1)]),
                ),
                (
                    "model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="agents",
                        to="nautobot_ai_models.aimodel",
                    ),
                ),
                ("tags", nautobot.core.models.fields.TagsField(through="extras.TaggedItem", to="extras.Tag")),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ai_agents",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Agent",
                "verbose_name_plural": "AI Agents",
                "ordering": ["name"],
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="AIAgentThread",
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
                ("thread_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.CharField(db_index=True, default="running", max_length=255)),
                ("interrupt_payload", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="threads",
                        to="nautobot_ai_models.aiagent",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Agent Thread",
                "verbose_name_plural": "AI Agent Threads",
                "ordering": ["-started_at"],
                "get_latest_by": "started_at",
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="AITool",
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
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True)),
                ("argument_schema", models.JSONField(blank=True, default=dict)),
                ("kind", models.CharField(db_index=True, default="registered", max_length=255)),
                ("module", models.CharField(blank=True, max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                ("writable", models.BooleanField(default=True)),
                ("advertised_read_only", models.BooleanField(blank=True, null=True)),
                ("definition_fingerprint", models.CharField(blank=True, max_length=255)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "git_repository",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_tools",
                        to="extras.gitrepository",
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ai_tools",
                        to="extras.job",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Tool",
                "verbose_name_plural": "AI Tools",
                "ordering": ["name"],
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="AIAgentSubagent",
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
                ("tool_name", models.CharField(blank=True, max_length=255)),
                ("tool_description", models.TextField(blank=True)),
                ("input_mode", models.CharField(default="task_only", max_length=255)),
                ("weight", models.PositiveIntegerField(default=100)),
                (
                    "parent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subagent_bindings",
                        to="nautobot_ai_models.aiagent",
                    ),
                ),
                (
                    "subagent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="supervisor_bindings",
                        to="nautobot_ai_models.aiagent",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Agent Subagent",
                "verbose_name_plural": "AI Agent Subagents",
                "ordering": ["parent__name", "weight", "pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("parent", "subagent"), name="nautobot_ai_models_aiagentsubagent_unique_parent_subagent"
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
            name="AIAgentSkill",
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
                ("weight", models.PositiveIntegerField(default=100)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="skill_bindings",
                        to="nautobot_ai_models.aiagent",
                    ),
                ),
                (
                    "skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="agent_bindings",
                        to="nautobot_ai_models.aiskill",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Agent Skill",
                "verbose_name_plural": "AI Agent Skills",
                "ordering": ["agent__name", "weight", "pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("agent", "skill"), name="nautobot_ai_models_aiagentskill_unique_agent_skill"
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
            name="AIAgentTool",
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
                ("name_override", models.CharField(blank=True, max_length=255)),
                ("description_override", models.TextField(blank=True)),
                ("weight", models.PositiveIntegerField(default=100)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tool_bindings",
                        to="nautobot_ai_models.aiagent",
                    ),
                ),
                (
                    "mcp_tool",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="agent_bindings",
                        to="nautobot_ai_models.mcptool",
                    ),
                ),
                (
                    "ai_tool",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="agent_bindings",
                        to="nautobot_ai_models.aitool",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Agent Tool",
                "verbose_name_plural": "AI Agent Tools",
                "ordering": ["agent__name", "weight", "pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("agent", "mcp_tool"), name="nautobot_ai_models_aiagenttool_unique_agent_mcp_tool"
                    ),
                    models.UniqueConstraint(
                        fields=("agent", "ai_tool"), name="nautobot_ai_models_aiagenttool_unique_agent_ai_tool"
                    ),
                ],
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
    ]
