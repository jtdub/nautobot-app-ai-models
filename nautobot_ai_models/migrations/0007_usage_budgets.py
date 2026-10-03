"""Record a permitted spend over one scope and one calendar period.

One table and no data. The three scope columns are nullable and the row's ``clean()`` requires
exactly one, because a budget names one thing it limits. This app records and reports; the
consuming app enforces.
"""

import uuid

import django.core.serializers.json
import django.core.validators
import django.db.models.deletion
import nautobot.extras.models.mixins
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nautobot_ai_models', '0006_agent_fallbacks'),
        ('tenancy', '0009_update_all_charfields_max_length_to_255'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIUsageBudget',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('_custom_field_data', models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('enabled', models.BooleanField(default=True)),
                ('period', models.CharField(max_length=255)),
                ('cost_limit', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('token_limit', models.PositiveBigIntegerField(blank=True, null=True)),
                ('agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='usage_budgets', to='nautobot_ai_models.aiagent')),
                ('model', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='usage_budgets', to='nautobot_ai_models.aimodel')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='usage_budgets', to='tenancy.tenant')),
            ],
            options={
                'verbose_name': 'AI Usage Budget',
                'verbose_name_plural': 'AI Usage Budgets',
                'ordering': ['name'],
            },
            bases=(nautobot.extras.models.mixins.DataComplianceModelMixin, nautobot.extras.models.mixins.DynamicGroupMixin, nautobot.extras.models.mixins.NotesMixin, models.Model),
        ),
    ]
