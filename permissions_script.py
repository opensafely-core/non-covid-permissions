import ast
import os

# TODO: write code for passing argument into script run command (the file arg passed shoulg go into the gitignore)
import argparse

import csv

import psycopg2 as pg
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()

DATABASE_CONNECTION_URL = os.getenv("DATABASE_URL", "postgres://user:pass@localhost:6543/jobserver")

API_TOKEN = os.getenv("GH_ACCESS_TOKEN")

conn = pg.connect(DATABASE_CONNECTION_URL)

# This query finds the project, workspace, and repo information for workspaces that have a job that ran in the last three months
open_project_query = """
        SELECT DISTINCT w.name AS "Workspace Name", p.id AS "Project ID", p.slug AS "Project Slug", p.status AS "Project Status", w.branch AS "Branch", r.url AS "Repo"
        FROM jobserver_workspace AS w
        INNER JOIN jobserver_project AS p ON (p.id = w.project_id)
        INNER JOIN jobserver_repo AS r ON (r.id = w.repo_id)
        INNER JOIN jobserver_jobrequest AS jr ON (w.id = jr.workspace_id)
        WHERE jr.created_at >= date_trunc('month', CURRENT_DATE - interval '3' MONTH)
        """


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
        for node in ast.walk(ast_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "ehrql.tables.tpp":
                tables.extend(alias.name for alias in node.names)

        for table in tables:
            ehrql_tables.add(table)

    if ehrql_tables:
        return ehrql_tables


def get_tables(repo_url, repo_branch):
    workspace_tree_url = get_branch_url(repo_url, repo_branch)
    python_files_in_repo = get_files_from_trees(workspace_tree_url)
    tpp_tables = get_tables_from_file_content(
        repo_url, repo_branch, python_files_in_repo
    )
    return tpp_tables


def get_info_from_data():
    yield from read_data(open_project_query)

# Dictionary containing a mapping of projects with their tables
def get_project_and_tables():
    
    project_dict = {}
    for i, project in enumerate(get_info_from_data()):
        repo_url = project["Repo"]
        repo_branch = project["Branch"]
        tables = get_tables(repo_url, repo_branch)

        project_tables = tables

        project_slug = project["Project Slug"]

        # with open("project_tables_mapping.txt", "a") as f:
        #     f.write(f"\n\n Round {i} before gouping: \n\n{project_slug}: {project_tables}")

        existing_project = [item for item in project_dict.keys() if project_slug == item]

        if project_tables and existing_project:
            merged_tables = project_dict[existing_project[0]] | project_tables
            project_dict[existing_project[0]] = merged_tables

        elif not project_tables and existing_project:
            # with open("project_tables_mapping.txt", "a") as f:
            #     f.write(f"\n\nround {i} existing name but no tables: \n\n{project_dict}")
            continue
        else:
            project_dict[project_slug] = project_tables

        # with open("project_tables_mapping.txt", "a") as f:
        #     f.write(f"\n\nround {i} after grouping: \n\n{project_dict}")

    # TODO: if file exists but is not empty, create a copy

    # Generates a file showing project-table mapping
    # with open("full_project_tables_mapping.txt", "w") as f:
    #     f.write(f"\n\nFull project-tables mapping: \n\n{project_dict}")
    
    yield from project_dict

# breakpoint()
# Read full csv file and extract tables
# TODO: convert this to a function that takes the input file name/path as an argument for reproducibility. It should also end with .csv
def get_eligible_tables(input_file):
    # input_file is the filename when the csv is stored in the same directory or the filepath when it is stored elsewhere in the system
    with open("tpp_table_extract.csv", "w") as output_table, open(input_file) as full_source_table:
        fieldnames = ["Table", "Eligible under new direction? (NHSE)"]
        reader = csv.DictReader(full_source_table)
        writer = csv.DictWriter(output_table, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            writer.writerow({"Table": row["Table"].lower(), "Eligible under new direction? (NHSE)": row["Eligible under new direction? (NHSE)"].lower()})

get_eligible_tables("os-tpp-database-source-of-tables.csv")

# TODO: pass the result of the above function so that reading the file is not repeated. using yield to generate each line? 
# Filter extracted tables
def filter_tables():
    with open("tpp_table_extract.csv", "r") as tables_file:
        reader = csv.DictReader(tables_file)
        # reader.next() # to skip the header row (is this necessary)
        collected_tables = [row["Table"] for row in reader] # tables in the tpp spreadsheet
    
    # print(collected_tables)

    full_project_table_mapping = get_project_and_tables()

    # breakpoint()
    # new_project_dict = {}
    for project, table in full_project_table_mapping:
        breakpoint()
        for item in project.values():
            if item not in collected_tables:
                project.values().remove(item)
    breakpoint()
        # print(item)

    # print(full_project_table_mapping)

print(filter_tables())  





        