from app.data_provider import ProviderRegistry
from app.provider_config import ProviderConfig
from app.indian_market_provider import IndianMarketProvider
from app.provider_orchestrator import ProviderOrchestrator

def build_provider_registry()->ProviderRegistry:
    registry=ProviderRegistry()
    config=ProviderConfig.from_env('indian_rest')
    if config.enabled:
        registry.register(IndianMarketProvider(config))
    return registry

def build_provider_orchestrator()->ProviderOrchestrator:
    registry=build_provider_registry()
    return ProviderOrchestrator([registry.get(name) for name in registry.names()])
