import ast
import os

import argparse

import csv

import psycopg2 as pg
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass

load_dotenv()

DATABASE_CONNECTION_URL = os.getenv(
    "DATABASE_URL", "postgres://user:pass@localhost:6543/jobserver"
)

API_TOKEN = os.getenv("GH_ACCESS_TOKEN")

conn = pg.connect(DATABASE_CONNECTION_URL)


def get_db_query(params):
    # Finds the project, workspace, and repo information for workspaces with jobs run in the last N months
    ehrql_users = f"""
                SELECT DISTINCT u.fullname AS "User Name", w.name AS "Workspace Name", w.branch AS "Branch", r.url AS "Repo"
                FROM jobserver_workspace AS w
                INNER JOIN jobserver_project AS p ON (p.id = w.project_id)
                INNER JOIN jobserver_repo AS r ON (r.id = w.repo_id)
                INNER JOIN jobserver_jobrequest AS jr ON (w.id = jr.workspace_id)
                INNER JOIN jobserver_user AS u ON (u.id = jr.created_by_id)
                WHERE jr.created_at >= date_trunc('month', CURRENT_DATE - interval '{params.no_of_months}' MONTH) 
                """

    if params.workspace_name:
        ehrql_users += f"AND w.name = '{params.workspace_name}'"

    return ehrql_users


def read_data(query):
    # Use ReadDictCursor to return the result of the query as a dictionary
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    project_info = cursor.fetchall()
    return project_info


def get_org_repo_name(repo_url) -> str:
    url_segments = repo_url.split("/")
    repo_name = "/".join(url_segments[3:])
    return repo_name


def get_branch_url(repo_url, repo_branch):
    org_repo = get_org_repo_name(repo_url)

    # Use branches endpoint to get all the branches in the repo
    url = f"https://api.github.com/repos/{org_repo}/branches"
    response = requests.get(
        url,
        headers={"Authorization": f"token {API_TOKEN}"},
    )
    if response.status_code != 200:
        raise Exception(f"GitHub returned an error {response.status_code}")

    for branch in response.json():
        if branch["name"] == repo_branch:
            tree_sha = branch["commit"]["sha"]

    # return url for accessing trees endpoint
    tree_url = (
        f"https://api.github.com/repos/{org_repo}/git/trees/{tree_sha}?recursive=true"
    )
    return tree_url


def get_files_from_trees(repo_tree_url):
    response = requests.get(
        repo_tree_url,
        headers={"Authorization": f"token {API_TOKEN}"},
    )
    if response.status_code != 200:
        raise Exception(f"GitHub returned an error {response.status_code}")

    repo_py_scripts = [
        item["path"] for item in response.json()["tree"] if item["path"].endswith(".py")
    ]
    return repo_py_scripts


def get_tables_from_file_content(repo_url, repo_branch, python_files_in_repo):
    ehrql_tables = set()

    for file in python_files_in_repo:
        repo = get_org_repo_name(repo_url)
        branch = repo_branch
        file_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file}"

        response = requests.get(
            file_url, headers={"Authorization": f"token {API_TOKEN}"}
        )
        if response.status_code != 200:
            raise Exception(f"GitHub returned an error {response.status_code}")
        data = response.text

        ast_tree = ast.parse(data)

        tables = []
        # pattern = r"/\behrql\.[^t]/"
        # statement = re.findall(pattern, node.module)

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ImportFrom):
                if node.module.startswith("ehrql.") and not node.module.startswith(
                    "ehrql.t"
                ):
                    tables.extend(alias.name for alias in node.names)

        for table in tables:
            ehrql_tables.add(table)

    return ehrql_tables


def get_tables(repo_url, repo_branch):
    workspace_tree_url = get_branch_url(repo_url, repo_branch)
    python_files_in_repo = get_files_from_trees(workspace_tree_url)
    tpp_tables = get_tables_from_file_content(
        repo_url, repo_branch, python_files_in_repo
    )

    return tpp_tables


def get_info_from_data(params):
    query = get_db_query(params)
    yield from read_data(query)


# Dictionary containing a mapping of projects with their tables
def get_project_and_tables(params):
    project_dict = {}
    for project in get_info_from_data(params):
        repo_url = project["Repo"]
        repo_branch = project["Branch"]
        tables = get_tables(repo_url, repo_branch)

        project_tables = tables

        username = project["User Name"]

        existing_project = [item for item in project_dict.keys() if username == item]

        if project_tables and existing_project:
            merged_tables = project_dict[existing_project[0]] | project_tables
            project_dict[existing_project[0]] = merged_tables

        elif not project_tables and existing_project:
            continue
        else:
            project_dict[username] = project_tables

    return project_dict


# return {
#         project: tables
#         for (project, tables) in full_project_table_mapping.items()
#         if tables
#     }


# def validate_input_file(input_file):
#     # input_file is the filename when the csv is stored in the same directory or the filepath when it is stored
#     # elsewhere in the system
#     if not input_file.endswith(".csv"):
#         raise ValueError(f"File {input_file} must be in csv format")
#     if not os.path.exists(input_file):
#         raise FileNotFoundError(f"File not found: {input_file}")


# Read full csv file and extract tables
# def get_tpp_schema_tables(input_file):
#     output_file = "tpp_table_extract.csv"
#     with (
#         open(output_file, "w") as output_table,
#         open(input_file) as full_source_table,
#     ):
#         fieldnames = ["Table", "Eligible under new direction? (NHSE)"]
#         reader = csv.DictReader(full_source_table)
#         writer = csv.DictWriter(output_table, fieldnames=fieldnames)
#         writer.writeheader()
#         for row in reader:
#             writer.writerow(
#                 {
#                     "Table": row["Table"].lower(),
#                     "Eligible under new direction? (NHSE)": row[
#                         "Eligible under new direction? (NHSE)"
#                     ].lower(),
#                 }
#             )
#     return output_file


# def map_ineligible_tpp_tables_to_ehrql_format(input_file):
#     input = get_tpp_schema_tables(input_file)
#     with open(input, "r") as tpp_tables_file:
#         reader = csv.DictReader(tpp_tables_file)

#         # Filter out tables that are not allowed under non-COVID directions
#         ineligible_tpp_tables = {
#             row["Table"]: row["Eligible under new direction? (NHSE)"]
#             for row in reader
#             if row["Eligible under new direction? (NHSE)"] == "no"
#         }

#     # Map tpp tables names to their ehrql tables names where applicable. The opensafely docs has a list of ehrql tables: https://docs.opensafely.org/ehrql/reference/cheatsheet/#tables
#     tpp_to_ehrql = {
#         "openprompt": "open_prompt",
#         "healthcareworker": "occupation_on_covid_vaccine_record",
#         "sgss_alltests_negative": "sgss_covid_all_tests",
#         "sgss_alltests_positive": "sgss_covid_all_tests",
#         "sgss_negative": "sgss_covid_all_tests",
#         "sgss_positive": "sgss_covid_all_tests",
#         "therapeutics": "covid_therapeutics",
#     }

#     ineligible_ehrql_tables = {
#         tpp_to_ehrql.get(tpp_name, tpp_name): eligibility
#         for tpp_name, eligibility in ineligible_tpp_tables.items()
#     }

#     return list(ineligible_ehrql_tables.keys())


# def filter_tables(params):
#     # Filter out tables that are not allowed under non-COVID directions, after mapping tables in the TPP schema to ehrql tables
#     ehrql_tables_that_need_permission = map_ineligible_tpp_tables_to_ehrql_format(
#         params.input_file
#     )

#     full_project_table_mapping = get_project_and_tables(params)

#     for project, tables in full_project_table_mapping.items():
#         filtered_tables = {
#             table for table in tables if table in ehrql_tables_that_need_permission
#         }

#         full_project_table_mapping[project] = filtered_tables

#     return {
#         project: tables
#         for (project, tables) in full_project_table_mapping.items()
#         if tables
#     }


def generate_output_file(params):
    # validate_input_file(params.input_file)
    # projects_with_non_covid_restrictions = filter_tables(params)
    user_dict = get_project_and_tables(params)
    output_file = f"internal_module_users_{params.no_of_months}_months.csv"
    with open(output_file, "w") as output_file:
        fieldnames = ["User", "Tables"]
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for user, table in user_dict.items():
            writer.writerow(
                {
                    "User": user,
                    "Tables": table,
                }
            )

    print(f"Results written to: internal_module_users_{params.no_of_months}_months.csv")
    return output_file


@dataclass
class QueryParams:
    # input_file: str
    no_of_months: int
    workspace_name: str


def run():
    parser = argparse.ArgumentParser()
    # parser.add_argument(
    #     "input_file",
    #     type=str,
    #     help="Filepath to the downloaded csv (see setup instructions in README.md)",
    # )
    parser.add_argument(
        "-n",
        "--number_of_months",
        type=int,
        nargs="?",
        default=9,
        help="Last N months to query the database which starts from the first day of the earliest month",
    )
    parser.add_argument(
        "-w",
        "--workspace_name",
        type=str,
        nargs="?",
        help="Workspace name for single workspace to analyse",
    )
    args = parser.parse_args()

    params = QueryParams(args.number_of_months, args.workspace_name)
    # breakpoint()
    generate_output_file(params)


if __name__ == "__main__":
    run()
