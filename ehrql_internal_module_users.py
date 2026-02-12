import ast
import os

import argparse

import csv

import psycopg2 as pg
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass
from github import Github, Auth
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

load_dotenv()

DATABASE_CONNECTION_URL = os.getenv(
    "DATABASE_URL", "postgres://user:pass@localhost:6543/jobserver"
)
API_TOKEN = os.getenv("GH_ACCESS_TOKEN")
auth = Auth.Token(API_TOKEN)


g = Github(auth=auth)
conn = pg.connect(DATABASE_CONNECTION_URL)

# Checks within the last 9 months
start_time_naive = datetime.now() - timedelta(days=270)  # no timezone info

# Convert to timezone aware, the format in which git commit dates are stored. Without converting, we cannot compare with commit dates.
start_time = start_time_naive.replace(tzinfo=timezone.utc)

# This is populated by the jobserver pipeline and used by the GitHub SearchAPI pipeline
jobserver_sha = set()


# To get data that exists in the joserver database
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


# Build GitHub search API query
def get_search_query_results(params):
    query = 'org:opensafely language:python "from ehrql"'

    if params and params.repo_name:
        query = f'repo:opensafely/{params.repo_name} language:python "from ehrql"'

    # search_code uses the Search API
    return g.search_code(query)


# To get data (python files) that doesn't exist in the jobserver database
def get_valid_search_results(params=None):
    """Example structure:
    valid_search_results = [
        {
            "Name": "John Doe",
            "Email": "johndoe@gmail.com",
            "Repo" "repo_a",
            "File Path": "analysis/dataset_definition_1.py",
            "File Content": "from ehrql.tpp import....\n rest of file content",
        },
        {
            "Name": "John Doe",
            "Email": "johndoe@gmail.com",
            "Repo" "repo_b",
            "File Path": "analysis/dataset_definition_cohort.py",
            "File Content": "from ehrql import....\n rest of file content",
        },
        {
            "Name": "Alexa Unix",
            "Email": "alexau@outlook.com",
            "Repo" "repo_c",
            "File Path": "analysis/dataset_definition_test.py",
            "File Content": "from ehrql.tpp import....\n rest of file content",
        },
    ]"""

    valid_search_results = []
    for result in get_search_query_results(params):
        # breakpoint()
        file_exists_jobserver = result.sha in jobserver_sha

        if file_exists_jobserver:
            continue

        repo = result.repository

        # Skip if repo has not been pushed in the last 9 months
        if repo.pushed_at < start_time:
            continue

        # Skip if latest commit for file path is too old
        commits = repo.get_commits(path=result.path)
        if commits[0].commit.author.date < start_time:
            continue

        # We want to use the most frequent commit author in this script's generated data because there are instances where the latest
        # commits were not made by the main researcher. See opensafely/post-covid-renal as an example
        authors_in_commits = [commit.commit.author.name for commit in commits]
        author_count = Counter(authors_in_commits)
        main_author = max(author_count, key=author_count.get)

        # Get main authors email. Just a single match is needed
        email = {
            commit.commit.author.email
            for commit in commits
            if commit.commit.author.name == main_author
        }

        result_dict = defaultdict(str)
        result_dict["Name"] = main_author
        result_dict["Email"] = email
        result_dict["Repo"] = result.repository.name
        result_dict["File Path"] = result.path
        result_dict["File Content"] = result.decoded_content.decode("utf-8")

        valid_search_results.append(result_dict)

    # here we want to return a list of objects which will have callable data in another function
    return valid_search_results


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


def get_files_from_trees(repo_tree_url):
    response = requests.get(
        repo_tree_url,
        headers={"Authorization": f"token {API_TOKEN}"},
    )
    if response.status_code != 200:
        raise Exception(f"GitHub returned an error {response.status_code}")

    repo_py_scripts = {
        item["path"]: item["sha"]
        for item in response.json()["tree"]
        if item["path"].endswith(".py")
    }
    jobserver_sha.update(repo_py_scripts.values())

    return list(repo_py_scripts.keys())


# TODO write a function to handle ast parsing so it can take data from multiple sources
def parse_python_files(data):

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
    return tables


# TODO write function to build final output after data parsing
def get_faulty_imports_from_github_search_results():
    """Example structure: The structure of the returned object should look like the below. This is because a user might be working in more than one repo.
    github_users_with_internal_imports = {
    "User_a": [
        "user_a@gmail.com",
        {
            "Repo": "death-report",
            "File Path": "data_def.py",
            "Faulty Imports": "INTERVAL",
        },
        {
            "Repo": "openpathology_main",
            "File Path": "data_definition.py",
            "Faulty Imports": "ICD10",
        },
    ]
    }
    """
    github_users_with_internal_imports = {}

    for search_result in get_valid_search_results():
        data = search_result["File Content"]

        try:
            tables = parse_python_files(data)
        except Exception as e:
            file = search_result["File Path"]
            repo = search_result["Repo"]
            print(f"File: {file} in Repo: {repo} caused an error {e}")
            continue

        if tables:
            name = search_result["Name"]
            email = search_result["Email"]

            # TODO: figure out the logic here. we need to group all the file paths and tables together per repo per user
            # TODO confirm that data is not being overwritten
            import_information = {
                "Repo": search_result["Repo"],
                "File Path": search_result["File Path"],
                "Faulty Imports": tables,
            }
            if name in github_users_with_internal_imports.keys():
                github_users_with_internal_imports[name].append(import_information)
            else:
                github_users_with_internal_imports[name] = [email, import_information]
    print(github_users_with_internal_imports)
    return github_users_with_internal_imports


def get_faulty_imports_from_file_content_in_jobserver(
    repo_url, repo_branch, python_files_in_repo
):
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

        tables = parse_python_files(data)

        if tables:
            faulty_imports.update(tables)
            python_files_with_faulty_imports.append(file)

    faulty_imports_str = ", ".join(faulty_imports)
    files_str = ", ".join(python_files_with_faulty_imports)
    return faulty_imports_str, files_str


def get_imports_and_files(repo_url, repo_branch):
    workspace_tree_url = get_branch_url(repo_url, repo_branch)
    python_files_in_repo = get_files_from_trees(workspace_tree_url)
    imports_and_files = get_faulty_imports_from_file_content_in_jobserver(
        repo_url, repo_branch, python_files_in_repo
    )
    return imports_and_files


def get_info_from_data(params):
    query = get_db_query(params)
    yield from read_data(query)


# Dictionary containing users that have imported from internal ehrql modules
def get_users_and_import_info(params):
    """Example structure: The structure of the returned object should look like the below. This is because a user might be working in more than one workspace.
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
    output_file = (
        f"output_files/jobserver_internal_module_users_{params.no_of_months}_months.csv"
    )
    with open(output_file, "w") as output_csv:
        fieldnames = [
            "User",
            "Email",
            "Workspace",
            "Python File with Issue",
            "Faulty Imports",
        ]
        writer = csv.DictWriter(output_csv, fieldnames=fieldnames)
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
        f"Results written to: output_files/jobserver_internal_module_users_{params.no_of_months}_months.csv"
    )
    return output_file


@dataclass
class QueryParams:
    no_of_months: int
    workspace_name: str
    repo_name: str


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
        help="Workspace name for single workspace to analyse. Use this for the jobserver pipeline",
    )
    parser.add_argument(
        "-r",
        "--repo_name",
        type=str,
        nargs="?",
        help="To analyse a single repo. Use this for the Search API pipeline",
    )
    args = parser.parse_args()

    params = QueryParams(args.number_of_months, args.workspace_name, args.repo_name)

    # Run jobserver data pipeline - this runs first to populate the 'jobserver_sha' object
    generate_output_file(params)

    # print(jobserver_sha)

    # Run GitHub SearchAPI pipeline
    # TODO: add main code here
    get_faulty_imports_from_github_search_results()  # tmp


if __name__ == "__main__":
    run()
