from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Provider ─────────────────────────────────────────────────────────
    # Options: "bedrock" (default) or "openai"
    llm_provider: str = "bedrock"

    # ── AWS Bedrock ──────────────────────────────────────────────────────────
    aws_default_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_profile: str = ""
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_max_tokens: int = 4096
    bedrock_temperature: float = 0.1

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model_id: str = "gpt-4o"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.1

    # ── Jira ─────────────────────────────────────────────────────────────────
    jira_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    jira_projects_filter: str = ""
    jira_poll_jql: str = 'status = "Ready for Dev" ORDER BY created DESC'
    jira_poll_interval_seconds: int = 300

    # ── GitHub ───────────────────────────────────────────────────────────────
    github_personal_access_token: str = Field(default="", alias="GITHUB_PERSONAL_ACCESS_TOKEN")
    github_repo_owner: str = ""
    github_repo_name: str = ""
    github_base_branch: str = "main"
    github_default_reviewers: str = ""

    # ── Persistence ──────────────────────────────────────────────────────────
    sqlite_db_path: str = "data/sdlc_assistant.db"
    db_echo: bool = False

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    activity_log_path: str = "logs/activity.jsonl"
    llm_log_path: str = "logs/llm_calls.jsonl"

    # ── Metrics ──────────────────────────────────────────────────────────────
    metrics_port: int = 8080
    pr_reconcile_interval_seconds: int = 3600

    # ── Confluence ───────────────────────────────────────────────────────────
    confluence_url: str = ""           # e.g. https://your-org.atlassian.net/wiki
    confluence_space_keys: str = ""    # comma-separated space keys, e.g. "ENG,ARCH"
    confluence_max_pages: int = 10

    # ── Agent behaviour ───────────────────────────────────────────────────────
    repo_scout_max_files: int = 20
    completeness_threshold: float = 0.65
    llm_parse_retry_count: int = 3

    # ── Development ──────────────────────────────────────────────────────────
    dry_run: bool = False

    # ── Derived helpers ──────────────────────────────────────────────────────
    @property
    def github_token(self) -> str:
        return self.github_personal_access_token

    @property
    def default_reviewers_list(self) -> list[str]:
        return [r.strip() for r in self.github_default_reviewers.split(",") if r.strip()]

    @property
    def jira_projects_list(self) -> list[str]:
        return [p.strip() for p in self.jira_projects_filter.split(",") if p.strip()]

    @property
    def confluence_space_keys_list(self) -> list[str]:
        return [s.strip() for s in self.confluence_space_keys.split(",") if s.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
