def get_list():
    list_ = [0, 1, 3, 5, 6, 7, 8, 7]
    yield from list_

# for item in get_list():
    # print(item)


# filter tables 
def get_project():
    dict = {'project_1': {'clinical_events', 'ons_deaths', 'addresses'}, 'project_2': {'household_memberships_2020', 'ethnicity_from_sus'}}
    return dict

def filter_table():
    collected_tables = ['ons_deaths', 'addresses', 'household_memberships_2020', 'ethnicity_from_sus']
    full_project = get_project()

    for project, project_tables in full_project.items():
        # breakpoint()
        filtered_table = {table for table in project_tables if table in collected_tables}
        full_project[project] = filtered_table
        # for item in project_tables:
        #     if item not in collected_tables:
        #         project_tables.remove(item)
        #         print(project_tables)
        # full_project[project] = project_tables ## check where the indentatiomn should be
    return full_project
        # for item in project.values():
        #     if item not in collected_tables:
        #         project.values().remove(item)
    # breakpoint()

print(filter_table())  