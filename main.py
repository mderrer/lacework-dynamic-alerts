from datetime import datetime, timedelta, timezone
import logging
import logging.handlers
import os
from string import Template
import sys

from laceworksdk import LaceworkClient, exceptions
import yaml

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ALERT_DIR = "alerts/"
API_KEY = os.environ["API_KEY"]
API_SECRET = os.environ["API_SECRET"]
ACCOUNT = os.environ["ACCOUNT"]


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_file_handler = logging.handlers.RotatingFileHandler(
    "status.log",
    maxBytes=1024 * 1024,
    backupCount=1,
    encoding="utf8",
)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger_file_handler.setFormatter(formatter)
logger.addHandler(logger_file_handler)


def load_yaml_file(filename):
    with open(ALERT_DIR + filename, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data


def execute_resource_query(laceworkclient, query):
    time_range = {
        "StartTimeRange": (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            ISO_FORMAT
        ),
        "EndTimeRange": datetime.now(timezone.utc).strftime(ISO_FORMAT),
    }
    try:
        results = laceworkclient.queries.execute(query_text=query, arguments=time_range)
        return [i["RESOURCE_RESULTS"] for i in results["data"]]
    except exceptions.ApiError as e:
        raise e


def update_dynamic_query(laceworkclient, query, query_id, query_var):
    query_template = Template(query)
    query = query_template.substitute(query_var=query_var)
    try:
        laceworkclient.queries.update(query_text=query, query_id=query_id)
        logger.info(f"{query_id} successfully updated.")
    except exceptions.ApiError as e:
        raise e


def format_list_as_quoted_string(list):
    quoted_string = ", ".join([f"'{element}'" for element in list])
    return quoted_string


def main():
    files = []
    for file in os.listdir(ALERT_DIR):
        if file.endswith(".yaml"):
            files.append(file)

    try:
        lw = LaceworkClient(account=ACCOUNT,
                            api_key=API_KEY,
                            api_secret=API_SECRET)
    except exceptions.ApiError as e:
        logger.error(f"Lacework API error: {e}")
        sys.exit()

    for query_file in files:
        queries = load_yaml_file(query_file)
        try:
            dynamic_values = execute_resource_query(
                lw, queries["resource_query"]["queryText"]
            )
        except exceptions.ApiError as e:
            logger.error(e)
            logger.error(f"Error with resource query\nUnable to automate: {query_file}")
            continue

        if dynamic_values:
            values = format_list_as_quoted_string(dynamic_values)
            try:
                update_dynamic_query(
                    lw,
                    queries["dynamic_query"]["queryText"],
                    queries["dynamic_query"]["queryId"],
                    values,
                )
            except exceptions.ApiError as e:
                logger.error(e)
                logger.error(
                    f"Error with dynamic quert update\nUnable to automate: {query_file}"
                )
        else:
            # more thought needs to go into this, should
            logger.error(f"No values returned from resource query. Alert based on {query_file} not updated")


if __name__ == "__main__":
    main()
