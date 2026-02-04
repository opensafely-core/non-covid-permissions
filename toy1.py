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
# TODO: FIGURE OUT HOW TO ISOLATE THESE FROM THOSE ALREADY IN JS DB TO AVOID DUPLICATION
# TODO: GET FILES WHEN WE DONT HAVE REPO INFPMATION (WORKING IN REVERSE)

g = Github(auth=auth)

repo = g.get_repo("opensafely/open-pathology-sdr")
print(f"this is for the openpath repo: {repo.description}")

# for repo in g.get_user().get_repos():
#     print(repo.full_name)
# g.close()

contents = repo.get_contents("")


start_time_naive = datetime.now() - timedelta(days=270)  # no timezone info
start_time = start_time_naive.replace(
    tzinfo=timezone.utc
)  # converts to timezone aware, the format in which git commit dates are stored

end_time_naive = datetime.now()
end_time = end_time_naive.replace(tzinfo=timezone.utc)
# breakpoint()


while contents:
    # breakpoint()
    file_content = contents.pop(0)
    if file_content.type == "dir":  # to search for files recursively
        contents.extend(
            repo.get_contents(file_content.path)
        )  # for loop is not used because the original list is being modified and the while syntax does not like list sizes changing mid-iteration
    elif file_content.path.endswith(".py"):
        # print(file_content)  # prints the ContentFile object which contains the file path in the repo. other attributes have to be specially called
        # print(file_content.download_url)
        # print(type(file_content.decoded_content))  # prints a bytes string which at cannot work with
        # print(file_content.decoded_content.decode("utf-8"))  # decodes and converts to string # TODO: use this code
        commit = repo.get_commits(path=file_content.path)
        # breakpoint()
        latest_commit = commit[0]
        if start_time < latest_commit.commit.author.date <= end_time:
            print(latest_commit.commit.author.date)  # type: datetime.datetime
            print(latest_commit.commit.author.name)
            print(latest_commit.commit.author.email)
        # breakpoint()
        print(" ")
