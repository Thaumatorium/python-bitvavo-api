import logging

from bitvavo_api_upgraded.helper_funcs import configure_loggers, time, time_ms, time_to_wait


def test_time_ms_happy_path(mocker):
    mock_time = mocker.patch("bitvavo_api_upgraded.helper_funcs.time", return_value=1642420179.226361)
    result = time_ms()
    assert mock_time.call_count == 1
    assert type(result) == int
    assert result == 1642420179226


def test_time_to_wait_happy_path(mocker):
    mock_time_ms = mocker.patch("bitvavo_api_upgraded.helper_funcs.time_ms", return_value=1642420179226)
    result = time_to_wait(1642420179226 + 1000)
    assert mock_time_ms.call_count == 1
    assert type(result) == float
    assert result == 1.0


def test_time_to_wait_unhappy_flow(mocker):
    mock_time_ms = mocker.patch("bitvavo_api_upgraded.helper_funcs.time_ms", return_value=1642420179226)
    result = time_to_wait(1642420179226 - 1000)
    assert mock_time_ms.call_count == 1
    assert type(result) == float
    assert result == 0