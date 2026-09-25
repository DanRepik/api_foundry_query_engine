import logging
import os

# The root log level comes from LOGGING_LEVEL, defaulting to INFO. force=True
# so the configuration applies even when the Lambda runtime has already
# installed a handler.
DEFAULT_LOGGING_LEVEL = "INFO"

# At DEBUG, botocore logs every request it signs: the headers, including the
# caller's x-amz-security-token, and the body -- which for the RDS Data API
# carries every SQL parameter. These loggers are therefore held at WARNING
# whatever LOGGING_LEVEL is, unless AWS_SDK_LOGGING_LEVEL explicitly says
# otherwise.
AWS_SDK_LOGGERS = ("boto3", "botocore", "s3transfer", "urllib3")
DEFAULT_AWS_SDK_LOGGING_LEVEL = "WARNING"


def _logging_level() -> str:
    return os.getenv("LOGGING_LEVEL", DEFAULT_LOGGING_LEVEL).upper()


def _quiet_aws_sdk_loggers() -> None:
    level = os.getenv("AWS_SDK_LOGGING_LEVEL", DEFAULT_AWS_SDK_LOGGING_LEVEL).upper()
    for name in AWS_SDK_LOGGERS:
        logging.getLogger(name).setLevel(level)


logging.basicConfig(
    format="%(name)s:%(lineno)s - %(levelname)s - %(message)s",
    level=_logging_level(),
    force=True,
)
_quiet_aws_sdk_loggers()

WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG


def logger(name=None):
    """
    Function to create a logger with a specified name or default name.

    Parameters:
        name (str): Name of the logger. If not provided, the root logger is returned.

    Returns:
        logging.Logger: Logger object with the specified name or the root logger.

    """
    # Re-applied on every call: LOGGING_LEVEL may have changed since import.
    logging.getLogger().setLevel(_logging_level())
    _quiet_aws_sdk_loggers()
    return logging.getLogger(name)


def write_logging_file(file_name, content):
    """
    Function to write a given string to a file in the temp/logging folder.

    Parameters:
        file_name (str): Name of the file to write the content to.
        content (str): The string content to write to the file.

    """
    # Define the directory path
    dir_path = os.path.join("temp", "logging")

    # Ensure the directory exists
    os.makedirs(dir_path, exist_ok=True)

    # Define the file path
    file_path = os.path.join(dir_path, file_name)

    # Write the content to the file
    with open(file_path, "w") as file:
        file.write(content + "\n")
