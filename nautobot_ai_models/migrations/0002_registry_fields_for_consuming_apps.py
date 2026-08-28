"""Add the registry fields a consuming app needs. See issues #2, #3, #4 and #5.

Each column is added nullable, filled in, and only then altered to its final shape. Adding a column
with a default in one step can rewrite the whole table under a lock.
"""

from django.db import migrations, models


def fill_in_the_new_columns(apps, schema_editor):
    """Fill in the four new columns.

    A provider that served the OpenAI shape becomes ``openai_compatible``, but only when its
    integration carries a remote URL. That dialect is an address rather than a service, so
    AIProvider.clean() requires the URL, and labelling a row that has none would make it refuse
    every later save over a field nobody touched.

    Every other provider is left empty. The boolean says nothing about what a row that was not
    OpenAI-shaped speaks instead, and a guess would send the credential elsewhere. The model
    refuses an empty value, so an operator answers on the next save.
    """
    AIProvider = apps.get_model("nautobot_ai_models", "AIProvider")  # pylint: disable=invalid-name
    AIModel = apps.get_model("nautobot_ai_models", "AIModel")  # pylint: disable=invalid-name

    AIProvider.objects.update(provider_type="", enabled=True)
    AIProvider.objects.filter(openai_compatible=True).exclude(external_integration__remote_url="").update(
        provider_type="openai_compatible"
    )

    AIModel.objects.update(kind="chat", default_parameters={})


def empty_the_new_columns(apps, schema_editor):
    """Clear the four columns, so the AlterField steps reverse back to nullable."""
    AIProvider = apps.get_model("nautobot_ai_models", "AIProvider")  # pylint: disable=invalid-name
    AIModel = apps.get_model("nautobot_ai_models", "AIModel")  # pylint: disable=invalid-name

    AIProvider.objects.update(provider_type=None, enabled=None)
    AIModel.objects.update(kind=None, default_parameters=None)


class Migration(migrations.Migration):
    """Add AIProvider.provider_type, AIProvider.enabled, AIModel.kind and AIModel.default_parameters."""

    dependencies = [
        ("nautobot_ai_models", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="aimodel",
            name="default_parameters",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="aimodel",
            name="kind",
            field=models.CharField(db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="aiprovider",
            name="enabled",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="aiprovider",
            name="provider_type",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.RunPython(fill_in_the_new_columns, empty_the_new_columns),
        migrations.AlterField(
            model_name="aimodel",
            name="default_parameters",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="aimodel",
            name="kind",
            field=models.CharField(db_index=True, default="chat", max_length=255),
        ),
        migrations.AlterField(
            model_name="aiprovider",
            name="enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="aiprovider",
            name="provider_type",
            field=models.CharField(blank=True, db_index=True, default="openai", max_length=255),
        ),
    ]
