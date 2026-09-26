from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Supabase Settings
    supabase_url: str = "http://placeholder.supabase.co"
    supabase_service_key: str = "placeholder_key"
    
    # OpenRouter Settings
    openrouter_api_key: str = "placeholder_key"
    orca_router_model: str = "nvidia/llama-3.1-nemotron-70b-instruct:free"
    orca_generator_model: str = "nvidia/llama-3.1-nemotron-70b-instruct:free"
    
    # LangSmith Observability
    langchain_tracing_v2: str = "true"
    langchain_project: str = "orca-backend"
    langchain_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        extra = "ignore"

# Instantiate global settings
settings = Settings()
