import uuid

import django.core.serializers.json
import django.core.validators
import django.db.models.deletion
import nautobot.core.models.fields
import nautobot.extras.models.mixins
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("extras", "0142_remove_scheduledjob_approval_required"),
        ("tenancy", "0009_update_all_charfields_max_length_to_255"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIProvider",
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
                ("openai_compatible", models.BooleanField(default=True)),
                (
                    "num_predict",
                    models.IntegerField(
                        blank=True, null=True, validators=[django.core.validators.MinValueValidator(-1)]
                    ),
                ),
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
                    "external_integration",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ai_model_providers",
                        to="extras.externalintegration",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Provider",
                "verbose_name_plural": "AI Providers",
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
            name="MCPServer",
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
                ("transport", models.CharField(default="streamable-http", max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                ("protocol_version", models.CharField(blank=True, max_length=255)),
                ("server_name", models.CharField(blank=True, max_length=255)),
                ("server_version", models.CharField(blank=True, max_length=255)),
                ("instructions", models.TextField(blank=True)),
                ("capabilities", models.JSONField(blank=True, default=dict)),
                ("last_discovered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "external_integration",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="mcp_servers",
                        to="extras.externalintegration",
                    ),
                ),
                ("tags", nautobot.core.models.fields.TagsField(through="extras.TaggedItem", to="extras.Tag")),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="mcp_servers",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "MCP Server",
                "verbose_name_plural": "MCP Servers",
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
            name="AIModel",
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
                ("description", models.CharField(blank=True, max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "num_predict",
                    models.IntegerField(
                        blank=True, null=True, validators=[django.core.validators.MinValueValidator(-1)]
                    ),
                ),
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
                    "input_cost_per_million",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "output_cost_per_million",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_models",
                        to="nautobot_ai_models.aiprovider",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Model",
                "verbose_name_plural": "AI Models",
                "ordering": ["provider", "name"],
                "unique_together": {("name", "provider")},
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="MCPTool",
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
                ("input_schema", models.JSONField(blank=True, default=dict)),
                ("output_schema", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("writable", models.BooleanField(default=True)),
                ("advertised_read_only", models.BooleanField(blank=True, null=True)),
                ("definition_fingerprint", models.CharField(blank=True, max_length=255)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "mcp_server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tools",
                        to="nautobot_ai_models.mcpserver",
                    ),
                ),
            ],
            options={
                "verbose_name": "MCP Tool",
                "verbose_name_plural": "MCP Tools",
                "ordering": ["mcp_server__name", "name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("mcp_server", "name"), name="nautobot_ai_models_mcptool_unique_server_name"
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
    ]
