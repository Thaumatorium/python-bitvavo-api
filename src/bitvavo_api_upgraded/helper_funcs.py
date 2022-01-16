"""
Some helper functions that should make my life a lot easier
"""
import logging
import os
from logging.config import dictConfig
from time import time

import structlog

from bitvavo_api_upgraded.settings import BITVAVO_API_UPGRADED
from bitvavo_api_upgraded.type_aliases import ms, s_f


def time_ms() -> ms:
    return int(time() * 1000)


def time_to_wait(rateLimitResetAt: ms) -> s_f:
    curr_time = time_ms()
    if curr_time > rateLimitResetAt:
        # rateLimitRemaining has already reset
        return 0
    else:
        return abs(s_f((rateLimitResetAt - curr_time) / 1000))


def configure_loggers() -> None:
    """
    source: https://docs.python.org/3.9/library/logging.config.html#dictionary-schema-details
    """

    # overwrite settings for existing loggers from other libs (urllib3 and websocket being big ones!)
    loggers = {}
    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        loggers[logger.name] = {
            "handlers": ["console"],
            "level": BITVAVO_API_UPGRADED.LOG_LEVEL,
            "propagate": True,
        }

    structlog_console_pre_chain = [
        structlog.threadlocal.merge_threadlocal,
        structlog.stdlib.add_logger_name,  # show which named logger made the message!
        structlog.processors.add_log_level,  # info, warning, error, etc
        structlog.processors.TimeStamper(fmt="%Y-%m-%dT%H:%M:%S", utc=False),  # add an ISO formatted string
        structlog.processors.StackInfoRenderer(),  # log.info("some-event", stack_info=True)
        structlog.processors.format_exc_info,  # log.info("some-event", exc_info=True)
        structlog.processors.UnicodeDecoder(),  # decode any bytes to unicode
    ]

    console_renderer_kwargs = {
        "colors": True,
        "exception_formatter": structlog.dev.rich_traceback,
        "level_styles": structlog.dev.ConsoleRenderer.get_default_level_styles(colors=True),
        "sort_keys": True,
        "pad_event": 10,
    }

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structlog_console": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(**console_renderer_kwargs),
                    "foreign_pre_chain": structlog_console_pre_chain,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "DEBUG",
                    "formatter": "structlog_console",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": loggers,
        }
    )

    if structlog.is_configured():
        # only run structlog.configure() once
        return

    # {'event': 'yitten', 'logger': 'bitvavo-api-upgraded', 'level': 'warning', 'timestamp': '2022-01-16T00:05:26.110710Z'}
    structlog.configure(
        processors=[
            *structlog_console_pre_chain,
            structlog.dev.ConsoleRenderer(**console_renderer_kwargs),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
