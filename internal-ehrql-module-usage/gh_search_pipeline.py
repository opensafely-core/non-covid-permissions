from github import Github, Auth
import os
import csv
import argparse
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
from jobserver_db_pipeline import parse_python_files
from dataclasses import dataclass


load_dotenv()
API_TOKEN = os.getenv("GH_ACCESS_TOKEN")
auth = Auth.Token(API_TOKEN)

g = Github(auth=auth)

@dataclass
class QueryParams:
    repo_name: str

# Build GitHub search API query
def get_search_query_results(params):
    query = 'org:opensafely language:python "from ehrql"'

    if params and params.repo_name:
        query = f'repo:opensafely/{params.repo_name} language:python "from ehrql"'

    # search_code uses the Search API
    return g.search_code(query)


def get_jobserver_file_shas(file_path):
    # Read txt file and return appropriate messages
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File does not exist: {file_path}. Try running the jobserver pipeline to create this file."
        )

    with open(file_path, "r") as jf:
        return [line.strip() for line in jf]


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

    # Checks within the last 9 months
    start_time_naive = datetime.now() - timedelta(days=270)  # no timezone info

    # Convert to timezone aware, the format in which git commit dates are stored. Without converting, we cannot compare with commit dates.
    start_time = start_time_naive.replace(tzinfo=timezone.utc)

    file_path = "output_files/jobserver_file_shas.txt"

    valid_search_results = []
    for result in get_search_query_results(params):
        jobserver_shas = get_jobserver_file_shas(file_path)
        file_exists_jobserver = result.sha in jobserver_shas

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

        # Get main authors email. Just a single match is needed. # TODO: confirm that an OS author can only have only email authorised to make commits.
        email = {
            commit.commit.author.email
            for commit in commits
            if commit.commit.author.name == main_author
        }

        result_dict = defaultdict(str)
        result_dict["Name"] = main_author
        result_dict["Email"] = email.pop()
        result_dict["Repo"] = result.repository.name
        result_dict["File Path"] = result.path
        result_dict["File Content"] = result.decoded_content.decode("utf-8")

        valid_search_results.append(result_dict)

    # here we want to return a list of objects which will have callable data in another function
    return valid_search_results


# TODO write function to build final output after data parsing
def get_faulty_imports_from_github_search_results(params):
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

    for search_result in get_valid_search_results(params):
        data = search_result["File Content"]

        try:
            tables = parse_python_files(data)
        except Exception as e:
            file = search_result["File Path"]
            repo = search_result["Repo"]
            print(f"File: {file} in Repo: '{repo}' caused an error '{e}'")
            continue

        if tables:
            name = search_result["Name"]
            email = search_result["Email"]

            import_information = {
                "Repo": search_result["Repo"],
                "File Path": search_result["File Path"],
                "Faulty Imports": ", ".join(tables),
            }
            if name in github_users_with_internal_imports.keys():
                github_users_with_internal_imports[name].append(import_information)
            else:
                github_users_with_internal_imports[name] = [email, import_information]
    return github_users_with_internal_imports


def generate_output_file(params=None):
    user_dict = get_faulty_imports_from_github_search_results(params)
    output_file = "output_files/search_api_internal_module_users_9_months.csv"
    with open(output_file, "w") as output_csv:
        fieldnames = [
            "User",
            "Email",
            "Repo",
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
                    repo = item["Repo"]
                    file = item["File Path"]
                    imports = item["Faulty Imports"]
                    writer.writerow(
                        {
                            "User": name,
                            "Email": email,
                            "Repo": repo,
                            "Python File with Issue": file,
                            "Faulty Imports": imports,
                        }
                    )

    print(
        "Results written to: output_files/search_api_internal_module_users_9_months.csv"
    )
    return

def run():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-r",
        "--repo_name",
        type=str,
        nargs="?",
        help="To analyse a single repo",
    )
    args = parser.parse_args()

    params = QueryParams(args.repo_name)

    # Run search pipeline 
    generate_output_file(params)


if __name__ == "__main__":
    run()
