from supabase import create_client, Client
from core.config import settings

def get_supabase_client() -> Client:
    """
    Returns a configured Supabase client using environment variables.
    """
    return create_client(settings.supabase_url, settings.supabase_service_key)
