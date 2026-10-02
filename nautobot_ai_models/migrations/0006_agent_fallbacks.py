"""Record the fallback chat models an agent moves to when its primary fails.

One table and no data. The order is the point. The model is protected, so a catalog row an agent
can fall back to is not deleted by accident.
"""

import uuid

import django.core.serializers.json
import django.db.models.deletion
import nautobot.extras.models.mixins
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nautobot_ai_models', '0005_mcp_prompt_and_resource_targets'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIAgentFallback',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('_custom_field_data', models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ('weight', models.PositiveIntegerField(default=100)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fallback_bindings', to='nautobot_ai_models.aiagent')),
                ('model', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='fallback_bindings', to='nautobot_ai_models.aimodel')),
            ],
            options={
                'verbose_name': 'AI Agent Fallback',
                'verbose_name_plural': 'AI Agent Fallbacks',
                'ordering': ['agent__name', 'weight', 'pk'],
                'constraints': [models.UniqueConstraint(fields=('agent', 'model'), name='nautobot_ai_models_aiagentfallback_unique_agent_model')],
            },
            bases=(nautobot.extras.models.mixins.DataComplianceModelMixin, nautobot.extras.models.mixins.DynamicGroupMixin, nautobot.extras.models.mixins.NotesMixin, models.Model),
        ),
    ]
