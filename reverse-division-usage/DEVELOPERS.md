# ehrQL Reverse Division Usage
This directory contains a script to investigate the use of reverse division operations in ehrQL analysis code. Created to solve [this issue](https://github.com/opensafely-core/ehrql/pull/2710).

## Set up & Installation
Follow the instructions in the [README](../README.md). 

## Jobserver Data pipeline

```sh
python3 ehrql_internal_module_users.py
```

### Specify a custom time period
```sh
python3 ehrql_internal_module_users.py -n <number-of-months>
``` 

`<number-of-months>` is an integer
By default the script runs using data from the last nine months 

### Query a single workspace
```sh
python3 ehrql_internal_module_users.py -n <number-of-months> -w <workspace-name>
``` 

`<workspace-name>` gotten from job-server

## Search API pipeline
```sh
python3 search_code.py
```

### Query a single repo 
```sh
python3 search_code.py -r <repo-name>
```
