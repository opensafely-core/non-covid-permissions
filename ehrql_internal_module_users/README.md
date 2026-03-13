## Set up & Installation
Follow the instructions in job-server to get a copy of the database and get a docker container running locally for executing queries [here](https://github.com/opensafely-core/job-server/blob/main/DEVELOPERS.md#restoring-backups). This will enable you to run the script from this directory. 

## Accessing the GitHub API
Parts of this script requires access to the GitHub API. In Github, generate a PAT. Copy the token from GitHub and in the .env file created, replace the placeholder token for GH_ACCESS_TOKEN, with the copied token.

## Running the jobserver pipeline

## Running the Search API pipeline
```sh
python3 search_code.py
```

####

## Running the script

### Basic usage
```sh
python3 permissions_script.py <path-to-csv-file>
```

By default the script runs using data from the last six months 

### Specify a custom time period
```sh
python3 permissions_script.py <path-to-csv-file> -n <number-of-months>
``` 

`<number-of-months>` is an integer

### Get the tables for a single workspace
```sh
python3 permissions_script.py <path-to-csv-file> -n <number-of-months> -w <workspace-name>
``` 

`<workspace-name>` gotten from job-server

### Get help running the script
```sh
python3 permissions_script.py -h
```