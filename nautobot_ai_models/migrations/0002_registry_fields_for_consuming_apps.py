"""Add the registry fields a consuming app needs to address a provider and use a model.

Four new columns. See GitHub issues #2, #3, #4 and #5.

Each column is added nullable and without a default, filled in by hand, and only then altered to
its final shape. That is three steps where one would do, and it is the shape Nautobot asks for:
adding a column with a default in one step can rewrite the whole table under a lock. These two
tables are small, but a migration is read as an example of how this app writes migrations.
"""

from django.db import migrations, models


def fill_in_the_new_columns(apps, schema_editor):
    """Write a value into every row the three schema steps left empty.

    `provider_type` is the only one that needs a decision. A provider that served the OpenAI shape
    is addressed as an OpenAI-compatible endpoint: that is the honest reading, because the boolean
    says nothing about whether the endpoint is openai.com or a self-hosted vLLM, and
    OpenAI-compatible covers both.

    A provider that did not serve that shape is left blank. There is no honest answer for it: the
    boolean records that the endpoint is not OpenAI-shaped and says nothing at all about what it is
    instead. Writing a dialect here would have a consuming app address the endpoint on a guess,
    with the provider's credential attached. A blank means nobody has said, and AIProvider.clean()
    makes an operator answer the next time the row is saved.

    The other three carry the meaning every existing row already had. A model was for chat, a
    provider was in service, and nobody had recorded any extra request parameters.
    """
    AIProvider = apps.get_model("nautobot_ai_models", "AIProvider")  # pylint: disable=invalid-name
    AIModel = apps.get_model("nautobot_ai_models", "AIModel")  # pylint: disable=invalid-name

    AIProvider.objects.filter(openai_compatible=True).update(provider_type="openai_compatible")
    AIProvider.objects.filter(openai_compatible=False).update(provider_type="")
    AIProvider.objects.filter(enabled=None).update(enabled=True)

    AIModel.objects.filter(kind=None).update(kind="chat")
    AIModel.objects.filter(default_parameters=None).update(default_parameters={})


def empty_the_new_columns(apps, schema_editor):
    """Reverse of the above.

    Clearing the four columns is what lets the AlterField steps reverse cleanly back to nullable.
    Nothing is lost that the forward pass did not put there: `openai_compatible` was never written.
    """
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
        # Step one: the columns arrive nullable and without a default, so nothing is rewritten.
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
        # Step two: fill them in.
        migrations.RunPython(fill_in_the_new_columns, empty_the_new_columns),
        # Step three: the shape the models declare.
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
