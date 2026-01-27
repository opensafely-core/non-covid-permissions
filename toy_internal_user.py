import csv

internal_user = {
    "Andrea": [
        "andrea@gmail.com",
        {
            "workspace": "death-report",
            "python_file": "data_def.py",
            "faulty_imports": "INTERVAL",
        },
        {
            "workspace": "openpathology_main",
            "python_file": "data_definition.py",
            "faulty_imports": "ICD10",
        },
    ]
}

# print(type(internal_user))
# breakpoint()
# print(internal_user)

# for name, values in internal_user.items():
#     print(f"{name} owns this row")
#     for item in values:
#         if not isinstance(item, dict):
#             print(f"the email is {item}")
#         else:
#             print(f"This is one workspace {item["workspace"]}")
#             print(f"This is one file {item["python_file"]}")
#             print(f"This is one faulty import {item["faulty_imports"]}")


# user name, email(?), workspace, repo, python file with issue, faulty import statement,

output_file = "toy_test.csv"
with open(output_file, "w") as output_file:
    fieldnames = [
        "User",
        "Email",
        "Workspace",
        "Python File with Issue",
        "Faulty Imports",
    ]
    writer = csv.DictWriter(output_file, fieldnames=fieldnames)
    writer.writeheader()
    for name, values in internal_user.items():
        for item in values:
            if not isinstance(item, dict):
                email = item
            else:
                workspace = item["workspace"]
                file = item["python_file"]
                imports = item["faulty_imports"]
                writer.writerow(
                    {
                        "User": name,
                        "Email": email,
                        "Workspace": workspace,
                        "Python File with Issue": file,
                        "Faulty Imports": imports,
                    }
                )

print("Results written to: toy_test.csv")
