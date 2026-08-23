"""Jobs for nautobot_ai_models."""

from django.core.exceptions import ObjectDoesNotExist
from nautobot.apps.exceptions import SecretError
from nautobot.apps.jobs import BooleanVar, Job, ObjectVar, register_jobs

from nautobot_ai_models import discovery
from nautobot_ai_models.models import AIModel, Provider

# Nautobot reads this module-level constant to group the Jobs in the UI.
name = "AI Models"  # pylint: disable=invalid-name


class DiscoverAIModels(Job):
    """Read the model catalog from each OpenAI-compatible provider and sync AIModel records."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Meta attributes."""

        name = "Discover AI Models"
        description = "Query OpenAI-compatible providers and create or update AIModel records."
        has_sensitive_variables = False
        soft_time_limit = 300
        time_limit = 600

    provider = ObjectVar(
        model=Provider,
        required=False,
        label="AI Provider",
        description="Limit discovery to one provider. Leave empty to run against every provider.",
    )
    enable_new_models = BooleanVar(
        default=True,
        description="Mark newly discovered models as enabled.",
    )

    def run(self, *, provider, enable_new_models):  # pylint: disable=arguments-differ
        """Discover models for one provider or for all of them."""
        providers = [provider] if provider is not None else list(Provider.objects.all())
        if not providers:
            self.logger.warning("No AI Providers are defined. Nothing to discover.")
            return

        for each_provider in providers:
            self.discover_provider(each_provider, enable_new_models)

    def discover_provider(self, provider, enable_new_models):
        """Sync the AIModel records for a single provider. Never delete a record."""
        if not provider.openai_compatible:
            self.logger.warning(
                "Skipped. No standard model-discovery endpoint exists for a provider that is not OpenAI-compatible.",
                extra={"object": provider},
            )
            return

        try:
            discovered = discovery.fetch_models(provider)
        except (SecretError, ObjectDoesNotExist) as error:
            self.logger.failure(
                "Could not read the API token for this provider: %s",
                type(error).__name__,
                extra={"object": provider},
            )
            return
        except Exception as error:  # pylint: disable=broad-except
            # Log the exception type only. A message may carry a URL with an embedded credential.
            self.logger.failure(
                "Model discovery request failed: %s",
                type(error).__name__,
                extra={"object": provider},
            )
            return

        created, updated = self.sync_models(provider, discovered, enable_new_models)
        self.report_missing(provider, discovered)
        self.logger.success(
            "Discovery complete. Found %d models. Created %d. Updated %d.",
            len(discovered),
            created,
            updated,
            extra={"object": provider},
        )

    def sync_models(self, provider, discovered, enable_new_models):
        """Create missing AIModel records and update existing ones. Return the two counts."""
        existing = {each.name: each for each in provider.ai_models.all()}
        created = 0
        updated = 0

        for entry in discovered:
            ai_model = existing.get(entry["name"])
            if ai_model is None:
                ai_model = AIModel(
                    provider=provider,
                    name=entry["name"],
                    description=entry["description"],
                    enabled=enable_new_models,
                )
                ai_model.validated_save()
                created += 1
                self.logger.info("Created AI Model.", extra={"object": ai_model})
                continue

            # Never overwrite enabled, num_predict, or temperature. A user may have set them by hand.
            if entry["description"] and not ai_model.description:
                ai_model.description = entry["description"]
                ai_model.validated_save()
                updated += 1
                self.logger.info("Updated the description.", extra={"object": ai_model})

        return created, updated

    def report_missing(self, provider, discovered):
        """Log every AIModel record the provider no longer offers. Delete nothing."""
        discovered_names = {entry["name"] for entry in discovered}
        for ai_model in provider.ai_models.all():
            if ai_model.name not in discovered_names:
                self.logger.warning(
                    "The provider no longer offers this model. The record was kept.",
                    extra={"object": ai_model},
                )


jobs = [DiscoverAIModels]
register_jobs(*jobs)
