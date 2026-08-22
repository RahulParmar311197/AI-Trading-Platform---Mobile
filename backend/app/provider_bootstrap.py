from app.data_provider import ProviderRegistry
from app.provider_config import ProviderConfig
from app.indian_market_provider import IndianMarketProvider

def build_provider_registry()->ProviderRegistry:
    registry=ProviderRegistry()
    config=ProviderConfig.from_env('indian_rest')
    registry.register(IndianMarketProvider(config))
    return registry
