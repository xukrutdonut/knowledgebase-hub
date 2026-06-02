from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Base de datos
    database_url: str = "postgresql+asyncpg://reev:pass@postgres:5432/vartracker"
    database_url_sync: str = "postgresql://reev:pass@postgres:5432/vartracker"

    # Celery / Redis
    redis_url: str = "redis://redis:6379/1"
    rabbitmq_url: str = "amqp://guest@rabbitmq:5672//"

    # REEV
    reev_api_url: str = "http://reev-backend:8080"

    # ClinVar
    clinvar_data_dir: str = "/data/clinvar"
    clinvar_ftp_base: str = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38"
    clinvar_genome_build: str = "GRCh38"

    # Notificaciones
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@neuropedialab.org"
    smtp_tls: bool = True
    webhook_url: str = ""

    # Lab
    lab_name: str = "Laboratorio de Neuropediatría"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
