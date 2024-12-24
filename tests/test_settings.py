import pytest

from bitvavo_api_upgraded.settings import BitvavoApiUpgradedSettings, BitvavoSettings


@pytest.mark.parametrize(
    ("log_level", "expected"),
    [
        ("INFO", "INFO"),
        ("DEBUG", "DEBUG"),
        ("INVALID", pytest.raises(ValueError)),  # noqa: PT011
    ],
)
def test_validate_log_level(log_level: str, expected: str) -> None:
    if isinstance(expected, str):
        assert BitvavoApiUpgradedSettings.validate_log_level(log_level) == expected
    else:
        with expected:
            BitvavoApiUpgradedSettings.validate_log_level(log_level)


def test_api_rating_limit_per_second() -> None:
    """
    Input divided by 60
    """
    settings = BitvavoSettings(API_RATING_LIMIT_PER_SECOND=120)
    assert settings.API_RATING_LIMIT_PER_SECOND == 2


def test_api_rating_limit_per_minute() -> None:
    """
    Input not changed
    """
    val = 120
    settings = BitvavoSettings(API_RATING_LIMIT_PER_MINUTE=val)
    assert settings.API_RATING_LIMIT_PER_MINUTE == val  # noqa: SIM300
