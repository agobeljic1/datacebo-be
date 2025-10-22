from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, case_sensitive=False)

    # App
    app_name: str = "Datacebo API"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./app.db"

    # Security
    access_token_secret: str = "dev-access-secret-change-me"
    refresh_token_secret: str = "dev-refresh-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 15
    refresh_token_expires_days: int = 7

    # Cookies
    refresh_cookie_name: str = "refresh_token"
    refresh_cookie_path: str = "/auth/refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"

    # Licensing
    license_default_days: int = 30


settings = Settings()
