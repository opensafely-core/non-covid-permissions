# Non-COVID Permissions
This directory contains a script to extract permissions from ehrQL analysis code. Created to solve [this issue](https://github.com/opensafely-core/job-runner/issues/1206)

## Set up & Installation
Follow the instructions in the [README](../README.md). 

## Getting the TPP tables data
Members of datalab.org have access to the data in the shared drive [here](https://docs.google.com/spreadsheets/d/1zT5YKjOap0fzSwGztQwM9y2JeJ3MnMYsGerb1_qYw3s/edit?gid=0#gid=0)

Download a copy to your local machine in csv format. Save it in the `input_files` directory. This was automatically created when you ran `just devenv`.  

## Running the script

### Basic usage
```sh
python3 permissions_script.py ../input_files/<path-to-csv-file>
```

By default the script runs using data from the last six months 

### Specify a custom time period
```sh
python3 permissions_script.py ../input_files/<path-to-csv-file> -n <number-of-months>
``` 

`<number-of-months>` is an integer

### Get the tables for a single workspace
```sh
python3 permissions_script.py ../input_files/<path-to-csv-file> -n <number-of-months> -w <workspace-name>
``` 

`<workspace-name>` gotten from job-server

### Get help running the script
```sh
python3 permissions_script.py -h
```