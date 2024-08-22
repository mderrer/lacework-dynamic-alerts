from datetime import datetime, timedelta, timezone
import os
from string import Template
import sys

from laceworksdk import LaceworkClient, exceptions
import yaml

# this is a test
# this is another t3est

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def load_yaml_file(filename):
    with open(filename, "r", encoding="utf-8") as file:
        # Load the contents of the file
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
        print(f"{query_id} successfully updated.")
    except exceptions.ApiError as e:
        raise e


def format_list_as_quoted_string(list):
    quoted_string = ", ".join([f"'{element}'" for element in list])
    return quoted_string


def main():
    files = []
    for file in os.listdir(os.getcwd()):
        if file.endswith(".yaml"):
            files.append(file)

    try:
        lw = LaceworkClient()
    except exceptions.ApiError as e:
        print(f"Lacework API error: {e}")
        sys.exit()

    for query_file in files:
        queries = load_yaml_file(query_file)
        try:
            dynamic_values = execute_resource_query(
                lw, queries["resource_query"]["queryText"]
            )
        except exceptions.ApiError as e:
            print(e)
            print(f"Error with resource query\nUnable to automate: {query_file}")
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
                print(e)
                print(
                    f"Error with dynamic quert update\nUnable to automate: {query_file}"
                )
        else:
            # more thought needs to go into this, should
            print(f"No resoure values returned. {query_file} not updated")


if __name__ == "__main__":
    main()
