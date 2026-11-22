"""Module for tests test settings.py."""

import pytest
from pydantic import ValidationError
from pydantic import SecretStr

from config.settings import Settings


def settings(**kwargs):
    """Construct isolated settings without reading an environment file."""
    return Settings(_env_file=None, **kwargs)


def test_defaults_are_dry_run_and_practice():
    """Verify defaults are dry run and practice."""
    s = settings()
    assert s.dry_run is True
    assert s.scenario == "practice"
    assert s.http_timeout_seconds == 120
    assert s.allowed_touch_limit == 30


def test_wrong_api_host_is_rejected():
    """Verify wrong api host is rejected."""
    with pytest.raises(ValidationError):
        settings(target_api_base_url="https://untrusted.example/v1")


def test_unencrypted_api_url_is_rejected():
    """Verify unencrypted api url is rejected."""
    with pytest.raises(ValidationError):
        settings(target_api_base_url="http://target-api.apps.01.cf.eu01.stackit.cloud/v1")


def test_eval_requires_production():
    """Verify eval requires production."""
    with pytest.raises(ValidationError):
        settings(scenario="eval", environment="development")
    assert settings(scenario="eval", environment="production").allowed_touch_limit == 10


def test_rate_limit_cannot_exceed_server_cap():
    """Verify rate limit cannot exceed server cap."""
    with pytest.raises(ValidationError):
        settings(requests_per_minute=61)


def test_secrets_never_reach_public_diagnostics():
    """Verify secrets never reach public diagnostics."""
    s = settings(
        team_key=SecretStr("top-secret-team-key"),
        openai_api_key=SecretStr("top-secret-openai-key"),
    )
    assert "secret" not in str(s.public_diagnostics())
    assert "top-secret" not in repr(s)


def test_invalid_timezone_is_rejected():
    """Verify invalid timezone is rejected."""
    with pytest.raises(ValidationError):
        settings(story_timezone="Mars/Base")
