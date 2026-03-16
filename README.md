# About the repo
This repository contains a collection of scripts created for various use cases. They are run either once or on an ad hoc basis as needed.

Most of the scripts query the jobserver database and access the GitHub API. 

## Use cases
- [Extracting dataset permissions from analysis code](dataset-permissions)
- [Identifying users importing and using internal ehrQL modules](internal-ehrql-module-usage)
- [Identifying instances where reverse division operations have been used](reverse-division-usage)

## Set up & Installation
Follow the instructions in job-server to get a copy of the database and get a docker container running locally for executing queries [here](https://github.com/opensafely-core/job-server/blob/main/DEVELOPERS.md#restoring-backups). This will enable you to run the script from this directory. 

### Setting up your development environment
Create a .env file using `just devenv` 

### Accessing the GitHub API
Parts of this script requires access to the GitHub API. In Github, generate a PAT. Copy the token from GitHub and in the .env file created, replace the placeholder token for GH_ACCESS_TOKEN, with the copied token.

## Running the scripts
To run a script for a specific use case, navigate to the directory and follow the run instructions in the DEVELOPERS.md for that directory. 