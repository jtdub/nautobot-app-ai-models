"""Add the registry fields a consuming app needs. See issues #2, #3, #4 and #5.

Each column is added nullable, filled in, and only then altered to its final shape.

The three steps stay in one file because the order is load-bearing. Django's null-to-not-null
AlterField writes the field default into every row that is still NULL, so an alter that ran before
the backfill would give every provider the dialect ``openai``, which is the guess that
fill_in_the_new_columns exists to refuse.
"""

from django.db import migrations, models


def fill_in_the_new_columns(apps, schema_editor):
    """Write a value into every row that the AddField steps left empty.

    A provider that served the OpenAI shape becomes ``openai_compatible``, but only when its
    integration carries a remote URL. That dialect is an address rather than a service, so
    AIProvider.clean() requires the URL, and labelling a row that has none would make it refuse
    every later save over a field nobody touched.

    Every other provider is left empty. The boolean says nothing about what a row that was not
    OpenAI-shaped speaks instead, and a guess would send the credential elsewhere. The model
    refuses an empty value, and the form offers an empty option for such a row, so an operator
    answers on the next save.

    The other three columns carry the meaning that every row already had.

    Args:
        apps: The historical model registry.
        schema_editor: Unused.
    """
    AIProvider = apps.get_model("nautobot_ai_models", "AIProvider")  # pylint: disable=invalid-name
    AIModel = apps.get_model("nautobot_ai_models", "AIModel")  # pylint: disable=invalid-name

    AIProvider.objects.update(provider_type="", enabled=True)
    AIProvider.objects.filter(openai_compatible=True).exclude(external_integration__remote_url="").update(
        provider_type="openai_compatible"
    )

    AIModel.objects.update(kind="chat", default_parameters={})


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
        migrations.RunPython(fill_in_the_new_columns, migrations.RunPython.noop),
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
