from dotenv import load_dotenv
import os


import psycopg2 as pg
from psycopg2.extras import RealDictCursor


load_dotenv()

DATABASE_CONNECTION_URL = os.getenv(
    "DATABASE_URL", "postgres://user:pass@localhost:6543/jobserver"
)

conn = pg.connect(DATABASE_CONNECTION_URL)

internal_module_users = """
                SELECT DISTINCT w.name AS "Workspace Name", u.fullname AS "User Name", p.id AS "Project ID", p.slug AS "Project Slug", p.status AS "Project Status", w.branch AS "Branch", r.url AS "Repo"
                FROM jobserver_workspace AS w
                INNER JOIN jobserver_project AS p ON (p.id = w.project_id)
                INNER JOIN jobserver_repo AS r ON (r.id = w.repo_id)
                INNER JOIN jobserver_jobrequest AS jr ON (w.id = jr.workspace_id)
                INNER JOIN jobserver_user AS u ON (u.id = w.created_by_id)
                WHERE jr.created_at >= date_trunc('month', CURRENT_DATE - interval '3' MONTH) AND w.name = 'polypharmacy-deprescribing-dementia'
                """

cursor = conn.cursor(cursor_factory=RealDictCursor)
cursor.execute(internal_module_users)
project_info = cursor.fetchall()

print(project_info)

# TODO: define query
# Finds the user, project, workspace, and repo information for workspaces that have a job that run in the last three - six months
