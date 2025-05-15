# Quant-Tookit

## This is a private library of packages that contain several tools to implement and interact with quantitative finance projects

## This repo uses the tool UV for package management. In case you have got access to this repo via github please make sure to create your own virtual environment and then use the `uv sync` command to sync the virtual environment

### This lib has the following packages

    1. data_API: Classes, methods and functions which would be useful in interacting with databases.
    2. datetime_API: Classes, and methods used to generate correct contract ticker, for derivatives contracts of NSE and BSE.
    3. decorators: This module has some functions to be used as decorators, like validate_params, time_logger, et cetera. 
    4. helper: This module has some helper functions, like converting a stock name to valid ticker, data_batches so that we don't overwhelm the broker API, and a few more.
