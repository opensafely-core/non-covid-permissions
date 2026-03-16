import os

import argparse


import psycopg2 as pg
from psycopg2.extras import RealDictCursor
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
    # workspace_name: str


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

    # if params.workspace_name:
    #     ehrql_users += f"AND w.name = '{params.workspace_name}'"

    return ehrql_users


def read_data(query):
    # Use ReadDictCursor to return the result of the query as a dictionary
    conn = pg.connect(DATABASE_CONNECTION_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query)
    user_info = cursor.fetchall()
    return user_info


def run():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-n",
        "--number_of_months",
        type=int,
        nargs="?",
        default=36,
        help="Last N months to query the database which starts from the first day of the earliest month",
    )
    # parser.add_argument(
    #     "-w",
    #     "--workspace_name",
    #     type=str,
    #     nargs="?",
    #     help="Workspace name for single workspace to analyse",
    # )

    args = parser.parse_args()

    params = QueryParams(args.number_of_months)

    # Run the query
    query = get_db_query(params)
    print(read_data(query))


if __name__ == "__main__":
    run()
