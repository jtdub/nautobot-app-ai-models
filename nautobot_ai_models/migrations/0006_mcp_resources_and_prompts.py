"""Record the other two things an MCP server advertises.

Two tables and no data. A server offers tools, resources, and prompts; only tools had a table.
Neither table carries a ``writable`` column: a resource is read by protocol, and a prompt is
chosen by a person.
"""

import uuid

import django.core.serializers.json
import django.db.models.deletion
import nautobot.extras.models.mixins
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_ai_models", "0005_ai_tool_approval"),
    ]

    operations = [
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
    ]
