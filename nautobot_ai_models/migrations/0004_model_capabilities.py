"""Record what a model can do, beside what it costs.

Five nullable columns and no data. Every column stays empty on an existing row, because nobody has
recorded the answer yet. The three boolean columns are nullable for the same reason ``MCPTool``
records an unset ``advertised_read_only``: an empty value is not a "no".
"""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_ai_models", "0003_agents"),
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
    ]
