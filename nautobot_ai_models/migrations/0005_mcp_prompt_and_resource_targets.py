"""Bind an agent to the other two things an MCP server advertises.

Two nullable foreign keys and two unique constraints, and no data. A prompt or a resource a
person chooses for an agent belongs on the binding table beside the MCP tool and the AI tool.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_ai_models", "0004_model_capabilities_resources_prompts_approvals_usage"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiagenttool",
            name="mcp_prompt",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agent_bindings",
                to="nautobot_ai_models.mcpprompt",
                verbose_name="MCP Prompt",
            ),
        ),
        migrations.AddField(
            model_name="aiagenttool",
            name="mcp_resource",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agent_bindings",
                to="nautobot_ai_models.mcpresource",
                verbose_name="MCP Resource",
            ),
        ),
        migrations.AddConstraint(
            model_name="aiagenttool",
            constraint=models.UniqueConstraint(
                fields=("agent", "mcp_prompt"),
                name="nautobot_ai_models_aiagenttool_unique_agent_mcp_prompt",
            ),
        ),
        migrations.AddConstraint(
            model_name="aiagenttool",
            constraint=models.UniqueConstraint(
                fields=("agent", "mcp_resource"),
                name="nautobot_ai_models_aiagenttool_unique_agent_mcp_resource",
            ),
        ),
    ]