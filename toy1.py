from github import Github, Auth
import os
from dotenv import load_dotenv


load_dotenv()
API_TOKEN = os.getenv("GH_ACCESS_TOKEN")
auth = Auth.Token(API_TOKEN)

# TODO: GETTING THE FILE CONTENTS
g = Github(auth=auth)

repo = g.get_repo("opensafely/open-pathology-sdr")
print(f"this is for the openpath repo: {repo.description}")

# for repo in g.get_user().get_repos():
#     print(repo.full_name)
# g.close()

contents = repo.get_contents("")
# for content_file in contents:
#     print(content_file.download_url)
#     print(content_file.content)
#     print(" ")

while contents:
    # breakpoint()
    file_content = contents.pop(0)
    if file_content.type == "dir":  # to search for file recursively
        contents.extend(
            repo.get_contents(file_content.path)
        )  # for loop is not used because the original list is being modified and the while syntax does not like list sizes changing mid-iteration
    elif file_content.path.endswith(".py"):
        print(
            file_content
        )  # prints the ContentFile object which contains the file path in the repo. other attributes have to be specially called
        # print(file_content.download_url)
        print(
            type(file_content.decoded_content)
        )  # prints a bytes string which at cannot work with
        # print(file_content.decoded_content.decode("utf-8"))  # decodes and converts to string
        print(file_content.commit)
        # breakpoint()
        print(" ")
