# ehrQL Reverse Division Usage
This directory contains a script to investigate the use of reverse division operations in ehrQL analysis code. Created to solve [this issue](https://github.com/opensafely-core/ehrql/pull/2710).

## Set up & Installation
Follow the instructions in the [README](../README.md). 

## Running the script

```sh
python3 division_operation.py
```

### Specify a custom time period
```sh
python3 division_operation.py -n <number-of-months>
``` 

`<number-of-months>` is an integer
By default the script runs using data from the last thirty eight months 

### Get help running the script
```sh
python3 division_operation.py.py -h
```