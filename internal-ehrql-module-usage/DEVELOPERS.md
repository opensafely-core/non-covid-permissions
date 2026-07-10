This is the guide to run the pipeline for fetching internal ehrQL module users

There are two data pipelines here: 
- The jobserver data pipeline : using the latest data from the jobserver database 
- Search API pipeline : using data from GitHub's Search API results which don't occur in the jobserver database

Note: The jobserver pipeline command MUST be run first

## Set up & Installation
Follow the instructions in job-server to get a copy of the database and get a docker container running locally for executing queries [here](https://github.com/opensafely-core/job-server/blob/main/DEVELOPERS.md#restoring-backups). This will enable you to run the script from this directory. 

## Setting up your development environment
Create a .env file using `just devenv` 

## Accessing the GitHub API
Parts of this script requires access to the GitHub API. In Github, generate a PAT. Copy the token from GitHub and in the .env file created, replace the placeholder token for GH_ACCESS_TOKEN, with the copied token.

## Jobserver Data pipeline

```sh
python3 jobserver_db_pipeline.py
```

### Specify a custom time period
```sh
python3 jobserver_db_pipeline.py -n <number-of-months>
``` 

`<number-of-months>` is an integer
By default the script runs using data from the last nine months 

### Query a single workspace
```sh
python3 jobserver_db_pipeline.py -n <number-of-months> -w <workspace-name>
``` 

`<workspace-name>` gotten from job-server

## Search API pipeline
```sh
python3 gh_search_pipeline.py
```

### Query a single repo 
```sh
python3 gh_search_pipeline.py -r <repo-name>
```
