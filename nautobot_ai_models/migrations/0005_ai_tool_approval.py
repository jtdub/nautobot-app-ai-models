"""Record that a person accepted what a tool binding offers.

One table and no data. The rows are a log: a row is written once, and a withdrawal is a
``revoked_at`` stamp rather than a delete. There is no uniqueness constraint, because a binding
can be approved, withdrawn, and approved again.
"""

import uuid

import django.core.serializers.json
import django.db.models.deletion
import django.utils.timezone
import nautobot.extras.models.mixins
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_ai_models", "0004_model_capabilities"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AIToolApproval",
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
                ("fingerprint", models.CharField(blank=True, max_length=255)),
                ("approved_by_name", models.CharField(blank=True, max_length=255)),
                ("approved_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_by_name", models.CharField(blank=True, max_length=255)),
                ("note", models.TextField(blank=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_tool_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "binding",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approvals",
                        to="nautobot_ai_models.aiagenttool",
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="revoked_ai_tool_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Tool Approval",
                "verbose_name_plural": "AI Tool Approvals",
                "ordering": ["-approved_at", "pk"],
                "get_latest_by": "approved_at",
            },
            bases=(
                nautobot.extras.models.mixins.DataComplianceModelMixin,
                nautobot.extras.models.mixins.DynamicGroupMixin,
                nautobot.extras.models.mixins.NotesMixin,
                models.Model,
            ),
        ),
    ]
