# Figure out why workspace data is being overwritten when I try to expose the workspace column

# Hardcode this pipeline
# def get_project_and_tables(params):
#     project_dict = {}
#     for project in get_info_from_data(params):
#         repo_url = project["Repo"]
#         repo_branch = project["Branch"]
#         workspace_name = project["Workspace Name"]
#         tables = get_tables(repo_url, repo_branch)

#         # breakpoint()
#         # project_tables = tables

#         project_info = {"Workspace": workspace_name, "Tables": tables}

#         project_slug = project["Project Slug"]

#         existing_project = [
#             item for item in project_dict.keys() if project_slug == item
#         ]

#         if project_info["Tables"] and existing_project:
#             merged_tables = project_dict[existing_project[0]] | project_info
#             project_dict[existing_project[0]] = merged_tables

#         elif not project_info["Tables"] and existing_project:
#             continue
#         else:
#             project_dict[project_slug] = project_info
#     # breakpoint()
#     return project_dict


BASE_LIST_DICT = [
    {
        "Project Slug": "Project_abc",
        "Workspace Name": "post-renal",
        "Tables": {"table a", "table b"},
    },
    {
        "Project Slug": "Project_abc",
        "Workspace Name": "post-covid",
        "Tables": {"table c", "table d"},
    },
]

project_dict = {}
for project in BASE_LIST_DICT:
    workspace_name = [project["Workspace Name"]]
    tables = project["Tables"]

    project_info = {"Workspace": workspace_name, "Tables": tables}

    project_slug = project["Project Slug"]

    existing_project = [item for item in project_dict.keys() if project_slug == item]

    if project_info["Tables"] and existing_project:
        # Add additional workspaces to the workspace list of the existing project
        project_dict[existing_project[0]]["Workspace"].extend(project_info["Workspace"])

        # Extend the tables set of the existing project
        project_dict[existing_project[0]]["Tables"].update(project_info["Tables"])

    elif not project_info["Tables"] and existing_project:
        continue
    else:
        project_dict[project_slug] = project_info
print(project_dict)
