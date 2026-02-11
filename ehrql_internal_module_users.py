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
    ehrql_users = f"""
                SELECT DISTINCT u.fullname AS "User Name", u.email AS "Email", w.name AS "Workspace Name", w.branch AS "Branch", r.url AS "Repo"
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
    user_info = cursor.fetchall()
    return user_info


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


@dataclass
class ExistsInJobserver:
    files: dict = None


# Create a class instance
files_in_jobserver = ExistsInJobserver()


def get_files_from_trees(repo_tree_url):
    response = requests.get(
        repo_tree_url,
        headers={"Authorization": f"token {API_TOKEN}"},
    )
    if response.status_code != 200:
        raise Exception(f"GitHub returned an error {response.status_code}")

    # Populate the class instance with the file attributes so it can be called from the other script to check for existing file sha's. In search_code.py,
    # we need to ensure that data that exist in jobserver is not analysed a s this will create duplicates.

    # TODO Figure out how to access this from search_code.py because we don't have repo_tree_url to pass if get_files_from_trees/ExistsInJobserver is imported
    # (or alternatively write the data out to a file but this defeats the purpose of a closed e-2-e pipeline). This also needs to happen without running this entire script.
    # If the entire script needs to run, would adding time.sleep() and then ending the program after this function work here?
    # TODO Handle repeated for loops
    file_path_sha = {
        item["path"]: item["sha"]
        for item in response.json()["tree"]
        if item["path"].endswith(".py")
    }

    files_in_jobserver.files = file_path_sha
    print(files_in_jobserver)

    repo_py_scripts = [
        item["path"] for item in response.json()["tree"] if item["path"].endswith(".py")
    ]
    return repo_py_scripts


def get_faulty_imports_from_file_content(repo_url, repo_branch, python_files_in_repo):
    faulty_imports = set()
    python_files_with_faulty_imports = []

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

        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ImportFrom):
                if (
                    node.module
                    and node.module.startswith("ehrql.")
                    and not node.module.startswith("ehrql.t")
                ):
                    tables.extend(alias.name for alias in node.names)
        if tables:
            faulty_imports.update(tables)
            python_files_with_faulty_imports.append(file)

    faulty_imports_str = ", ".join(faulty_imports)
    files_str = ", ".join(python_files_with_faulty_imports)
    return faulty_imports_str, files_str


def get_imports_and_files(repo_url, repo_branch):
    workspace_tree_url = get_branch_url(repo_url, repo_branch)
    python_files_in_repo = get_files_from_trees(workspace_tree_url)
    imports_and_files = get_faulty_imports_from_file_content(
        repo_url, repo_branch, python_files_in_repo
    )
    return imports_and_files


def get_info_from_data(params):
    query = get_db_query(params)
    yield from read_data(query)


# Dictionary containing users that have imported from internal ehrql modules
def get_users_and_import_info(params):
    """Example structure:
    users_with_internal_imports = {
    "User_a": [
        "user_a@gmail.com",
        {
            "Workspace": "death-report",
            "File Path": "data_def.py",
            "Faulty Imports": "INTERVAL",
        },
        {
            "Workspace": "openpathology_main",
            "File Path": "data_definition.py",
            "Faulty Imports": "ICD10",
        },
    ]
    }
    """
    users_with_internal_imports = {}
    for users in get_info_from_data(params):
        username = users["User Name"]
        email = users["Email"]
        repo_url = users["Repo"]
        repo_branch = users["Branch"]
        workspace_name = users["Workspace Name"]
        imported_tables, files_with_imports = get_imports_and_files(
            repo_url, repo_branch
        )
        imports_from_wrong_location = imported_tables
        files_containing_wrong_imports = files_with_imports

        if not files_containing_wrong_imports:
            continue

        import_information = {
            "Workspace": workspace_name,
            "File Path": files_containing_wrong_imports,
            "Faulty Imports": imports_from_wrong_location,
        }

        if username in users_with_internal_imports.keys():
            users_with_internal_imports[username].append(import_information)
        else:
            users_with_internal_imports[username] = [email, import_information]

    return users_with_internal_imports


def generate_output_file(params):
    user_dict = get_users_and_import_info(params)
    output_file = f"output_files/internal_module_users_{params.no_of_months}_months.csv"
    with open(output_file, "w") as output_file:
        fieldnames = [
            "User",
            "Email",
            "Workspace",
            "Python File with Issue",
            "Faulty Imports",
        ]
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for name, import_info in user_dict.items():
            for item in import_info:
                if not isinstance(item, dict):
                    email = item
                else:
                    workspace = item["Workspace"]
                    file = item["File Path"]
                    imports = item["Faulty Imports"]
                    writer.writerow(
                        {
                            "User": name,
                            "Email": email,
                            "Workspace": workspace,
                            "Python File with Issue": file,
                            "Faulty Imports": imports,
                        }
                    )

    print(
        f"Results written to: output_files/internal_module_users_{params.no_of_months}_months.csv"
    )
    return output_file


@dataclass
class QueryParams:
    no_of_months: int
    workspace_name: str


def run():
    parser = argparse.ArgumentParser()

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
    generate_output_file(params)


if __name__ == "__main__":
    run()
