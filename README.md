# Non-COVID Permissions
This repository contains a script to extract permissions from ehrQL analysis code. 

## Set up & Installation
Follow the instructions in job-server to get a copy of the database and get a docker container running locally for executing queries [here](https://github.com/opensafely-core/job-server/blob/main/DEVELOPERS.md#restoring-backups). This will enable you to run the script from this directory. 

## Setting up your development environment
Create a .env file using `just devenv` 

## Accessing the GitHub API
Parts of this script requires access to the GitHub API. In Github <insert instructions here>. Copy the token from GitHub and in the .env file created, for the
GH_ACCESS_TOKEN variable, replace 'token' with the copied token.

## Getting the TPP tables data
Members of datalab.org have access to the data in the shared drive here: <insert file link>. 

Downlad a copy to your local machine in csv format. Save it in an easily accesible directory

## Running the script
To run the script:
`python3 permissions_script.py <path-csv-file>`