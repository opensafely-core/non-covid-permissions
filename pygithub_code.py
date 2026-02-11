# This is a proof of concept spike. It is complex and time-consuming to run so will be kept for reference

from github import Github, Auth
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import ast


load_dotenv()
API_TOKEN = os.getenv("GH_ACCESS_TOKEN")
auth = Auth.Token(API_TOKEN)

# TODO: GETTING THE FILE CONTENTS  => DONE
# TODO: GET FILES WITHIN THE DATE RANGE => DONE
# TODO: GET NAMES, EMAILS => DONE
# TODO: FIGURE OUT HOW TO ISOLATE THESE FROM THOSE ALREADY IN JS DB TO AVOID DUPLICATION  => compare file sha's?
# TODO: GET FILES WHEN WE DONT HAVE REPO INFORMATION (WORKING IN REVERSE) => DONE
# TODO: (MAYBE) HAVE THESE SEARCH API FUNCTIONS IN A DIFFERENT FILE

g = Github(auth=auth)

# Checks within the last 9 months
start_time_naive = datetime.now() - timedelta(days=270)  # no timezone info

# Convert to timezone aware, the format in which git commit dates are stored
start_time = start_time_naive.replace(tzinfo=timezone.utc)

end_time_naive = datetime.now()
end_time = end_time_naive.replace(tzinfo=timezone.utc)


def get_file_info(repo, contents):
    # TODO: have an early return here so that file processing time is not wasted on repos that don't match
    while contents:
        # breakpoint()

        # tmp: same as a one ContentFile in contentFile.py
        repo_content = contents.pop(0)

        if repo_content.path.endswith(".py"):
            # print(file_content)  # prints the ContentFile object which contains the file path in the repo. other attributes have to be specially called
            # print(file_content.download_url)
            # print(type(file_content.decoded_content))  # prints a bytes string which ast cannot work with
            # print(file_content.decoded_content.decode("utf-8"))  # decodes and converts to string # TODO: use this code
            commit = repo.get_commits(path=repo_content.path)
            # breakpoint()

            # TODO: Some of the latest commits were not made by the main researcher. This was usually by a developer. Think about how to handle this case. Will the top repo contributor be a better estimate.
            # See opensafely/post-covid-renal as example
            # TODO: add link to the docs that reference this code
            latest_commit = commit[0]
            print(dir(latest_commit))  ## to delete
            time_interval = start_time < latest_commit.commit.author.date <= end_time

            # Skips to the next iteration if the date of the last commit is not within the time
            if not time_interval:
                continue
            # if time_interval:
            # TODO: ast parsing applied here

            # The 'decoded_content' method returns a bytes string (ast cannot work with this data type). Calling 'decode' on this method converts it to a string
            data = repo_content.decoded_content.decode("utf-8")
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

            if not tables:
                continue

            print(f"File: {repo_content}")
            print(latest_commit.commit.author.date)  # type: datetime.datetime
            print(latest_commit.commit.author.name)
            print(latest_commit.commit.author.email)
            # breakpoint()
            print(" ")

        elif repo_content.type == "dir":  # to search for files recursively
            contents.extend(
                repo.get_contents(repo_content.path)
            )  # for loop is not used because the original list is being modified and the while syntax does not like list sizes changing mid-iteration

    return


# TODO: GET FILES WHEN WE DONT HAVE REPO INFORMATION (WORKING IN REVERSE)
os_org = g.get_organization("opensafely")

# Check through all repos in org for those that are active
for repo in os_org.get_repos():  # can check for duplication here? and in the contents?
    # only runs if the latest push to repo was within the last 9 months
    if repo.pushed_at > start_time:
        print(f"this is for the openpath repo: {repo.name}")
        all_contents_in_repo = repo.get_contents("")
        result = get_file_info(repo, all_contents_in_repo)
        if result:
            print(result)
        # breakpoint()
