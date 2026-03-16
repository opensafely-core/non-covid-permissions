import ast
import os

import argparse

import csv

import psycopg2 as pg
from psycopg2.extras import RealDictCursor
import requests
from dotenv import load_dotenv
from dataclasses import dataclass
from github import Github, Auth


load_dotenv()

DATABASE_CONNECTION_URL = os.getenv(
    "DATABASE_URL", "postgres://user:pass@localhost:6543/jobserver"
)
API_TOKEN = os.getenv("GH_ACCESS_TOKEN")
auth = Auth.Token(API_TOKEN)


g = Github(auth=auth)


@dataclass
class QueryParams:
    no_of_months: int


# To get data that exists in the jobserver database
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

    return ehrql_users


def read_data(query):
    # Use ReadDictCursor to return the result of the query as a dictionary
    conn = pg.connect(DATABASE_CONNECTION_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    user_info = cursor.fetchall()
    return user_info


def get_org_repo_name(repo_url) -> str:
    url_segments = repo_url.split("/")
    repo_name = "/".join(url_segments[3:])
    return repo_name


SKIPPED_BRANCHES_FILE = "output_files/skipped_branches.csv"


def log_skipped_branch(repo, branch):
    file_exists = os.path.exists(SKIPPED_BRANCHES_FILE)
    with open(SKIPPED_BRANCHES_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Repo", "Branch"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({"Repo": repo, "Branch": branch})


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

    tree_sha = None
    for branch in response.json():
        if branch["name"] == repo_branch:
            tree_sha = branch["commit"]["sha"]
            break

    if tree_sha is None:
        print(f"Branch '{repo_branch}' not found in {org_repo}, skipping.")
        log_skipped_branch(org_repo, repo_branch)
        return None

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

    python_file_and_shas = {
        item["path"]: item["sha"]
        for item in response.json()["tree"]
        if item["path"].endswith(".py")
    }

    # Return a list of python files
    return list(python_file_and_shas.keys())


def parse_python_files(data):

    ast_tree = ast.parse(data)

    division_usages = []

    for node in ast.walk(ast_tree):
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.FloorDiv):
                division_usages.append(("FloorDiv (//)", node.lineno))
            elif isinstance(node.op, ast.Div):
                division_usages.append(("TrueDiv (/)", node.lineno))

    return division_usages


def get_division_usage_from_file_content_in_jobserver(
    repo_url, repo_branch, python_files_in_repo
):
    division_usages = []
    python_files_with_divisions = []

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

        try:
            usages = parse_python_files(data)
        except SyntaxError as e:
            print(
                f"Skipping file: '{file}' in repo: '{repo}' — invalid Python syntax: {e}"
            )
            continue
        except Exception as e:
            print(f"Skipping file: '{file}' in repo: '{repo}' — unexpected error: {e}")
            continue

        if usages:
            division_usages.extend(f"{op} at line {line}" for op, line in usages)
            python_files_with_divisions.append(file)

    divisions_str = ", ".join(division_usages)
    files_str = ", ".join(python_files_with_divisions)
    return divisions_str, files_str


def get_division_operation_usage_and_files(repo_url, repo_branch):
    workspace_tree_url = get_branch_url(repo_url, repo_branch)

    if workspace_tree_url is None:
        return None, None

    python_files_in_repo = get_files_from_trees(workspace_tree_url)
    division_usage_and_files = get_division_usage_from_file_content_in_jobserver(
        repo_url, repo_branch, python_files_in_repo
    )
    return division_usage_and_files


def get_info_from_data(params):
    query = get_db_query(params)
    yield from read_data(query)


# Dictionary containing users that have used division operations
def get_users_and_division_usage(params):
    """Example structure: The structure of the returned object should look like the below. This is because a user might be working in more than one workspace.
    users_with_division_usage = {
    "User_a": [
        "user_a@gmail.com",
        {
            "Workspace": "death-report",
            "File Path": "data_def.py",
            "Division Operations": "TrueDiv (/) at line 258",
        },
        {
            "Workspace": "openpathology_main",
            "File Path": "data_definition.py",
            "Division Operations": "FloorDiv (//) at line 46",
        },
    ]
    }
    """
    users_with_division_usage = {}
    for users in get_info_from_data(params):
        username = users["User Name"]
        email = users["Email"]
        repo_url = users["Repo"]
        repo_branch = users["Branch"]
        workspace_name = users["Workspace Name"]
        division_operations, files_with_usage = get_division_operation_usage_and_files(
            repo_url, repo_branch
        )

        if division_operations is None:
            continue
        division_operation_usage = division_operations
        files_containing_division_operations = files_with_usage

        if not files_containing_division_operations:
            continue

        division_usage_information = {
            "Workspace": workspace_name,
            "File Path": files_containing_division_operations,
            "Division Operations": division_operation_usage,
        }

        if username in users_with_division_usage.keys():
            users_with_division_usage[username].append(division_usage_information)
        else:
            users_with_division_usage[username] = [email, division_usage_information]

    return users_with_division_usage


def generate_output_file(params):
    user_dict = get_users_and_division_usage(params)
    output_file = f"output_files/non_ehrql_filtered_division_operation_users_{params.no_of_months}_months.csv"

    with open(output_file, "w") as output_csv:
        fieldnames = [
            "User",
            "Email",
            "Workspace",
            "Python File with Issue",
            "Division Operations Found",
        ]
        writer = csv.DictWriter(output_csv, fieldnames=fieldnames)
        writer.writeheader()
        for name, division_operation_info in user_dict.items():
            for item in division_operation_info:
                if not isinstance(item, dict):
                    email = item
                else:
                    workspace = item["Workspace"]
                    file = item["File Path"]
                    operations = item["Division Operations"]
                    writer.writerow(
                        {
                            "User": name,
                            "Email": email,
                            "Workspace": workspace,
                            "Python File with Issue": file,
                            "Division Operations Found": operations,
                        }
                    )

    print(
        f"Results written to: output_files/non_ehrql_filtered_division_operation_users_{params.no_of_months}_months.csv"
    )

    return output_file


def run():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-n",
        "--number_of_months",
        type=int,
        nargs="?",
        default=38,
        help="Last N months to query the database which starts from the first day of the earliest month",
    )

    args = parser.parse_args()

    params = QueryParams(args.number_of_months)

    generate_output_file(params)


if __name__ == "__main__":
    run()
