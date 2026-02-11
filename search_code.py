# This is proof of concept spike using pygihub's search_code

from github import Github, Auth
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone


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


# query = 'org:opensafely language:python "from ehrql"'
query = 'repo:opensafely/post-covid-renal language:Python "from ehrql"'
print(dir(g.search_code(query)))
print(g.search_code(query).is_rest)
print(g.search_code(query).get_page)
print(g.search_code(query).totalCount)
# breakpoint()
for result in g.search_code(query):
    # TODO: check if the file in this search result exists in the jobserver db. If it does, skip the iteration early.
    # This is where result.path will be passed into an instance of ExistsInJobserver() imported from ehrql_internal_module_users.py

    repo = result.repository
    # html_url = result.html_url
    # download_url = result.download_url
    # decode = result.decoded_content.decode("utf-8")
    # breakpoint()
    if repo.pushed_at < start_time:
        continue

    # TODO: to fix the issue of a dev making the latest commit and having that on record, have a collections counter and get the user with the max no of commits
    # TODO: use the latest commit date for the date.
    commits = repo.get_commits(path=result.path)

    if commits[0].commit.author.date < start_time:
        continue

    authors_in_commits = [commit.author.name for commit in commits]

    # We want to use the most frequent commit author in this script's generated data because there are instances where the latest
    # commits were not made by the main researcher. See opensafely/post-covid-renal as an example
    main_file_author = max(authors_in_commits)
    print(main_file_author)
    breakpoint()

    data = result.decoded_content.decode("utf-8")
    print(data)
    breakpoint()
