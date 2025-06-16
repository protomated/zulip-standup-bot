# Zulip API

[![Build status](https://github.com/zulip/python-zulip-api/workflows/build/badge.svg)](
https://github.com/zulip/python-zulip-api/actions?query=branch%3Amain+workflow%3Abuild)
[![Coverage status](https://img.shields.io/codecov/c/github/zulip/python-zulip-api)](
https://codecov.io/gh/zulip/python-zulip-api)

This repository contains the source code for Zulip's PyPI packages:

* `zulip`: [PyPI package](https://pypi.python.org/pypi/zulip/)
  for Zulip's API bindings.
* `zulip_bots`: [PyPI package](https://pypi.python.org/pypi/zulip-bots)
  for Zulip's bots and bots API.
* `zulip_botserver`: [PyPI package](https://pypi.python.org/pypi/zulip-botserver)
  for Zulip's Flask Botserver.

The source code is written in *Python 3*.

## Docker Deployment

This repository is configured to run in Docker, which makes it easy to deploy to environments like CapRover.

### Local Docker Deployment

To run the botserver locally using Docker:

1. Make sure you have Docker and Docker Compose installed
2. Clone this repository
3. Configure your `botserverrc` file with your bot credentials
4. Run `docker-compose up` to start the botserver

### CapRover Deployment

To deploy to CapRover:

1. Make sure your CapRover instance is set up
2. Configure your `botserverrc` file with your bot credentials
3. Push this repository to your CapRover instance
4. CapRover will automatically build and run the Docker image

The Docker build process includes a provisioning step that installs all required dependencies, including bot-specific requirements. This is similar to running the `tools/provision` script in a local development environment.

The botserver will run with the command `zulip-botserver -c botserverrc` inside the Docker container.

## Development

This is part of the Zulip open source project; see the
[contributing guide](https://zulip.readthedocs.io/en/latest/overview/contributing.html)
and [commit guidelines](https://zulip.readthedocs.io/en/latest/contributing/version-control.html).

1. Fork and clone the Git repo, and set upstream to zulip/python-zulip-api:
   ```
   git clone https://github.com/<your_username>/python-zulip-api.git
   cd python-zulip-api
   git remote add upstream https://github.com/zulip/python-zulip-api.git
   git fetch upstream
   ```

2. Make sure you have [pip](https://pip.pypa.io/en/stable/installing/).

3. Run:
   ```
   python3 ./tools/provision
   ```
   This sets up a virtual Python environment in `zulip-api-py<your_python_version>-venv`,
   where `<your_python_version>` is your default version of Python. If you would like to specify
   a different Python version, run
   ```
   python3 ./tools/provision -p <path_to_your_python_version>
   ```

4. If that succeeds, it will end with printing the following command:
   ```
   source /.../python-zulip-api/.../activate
   ```
   You can run this command to enter the virtual environment.
   You'll want to run this in each new shell before running commands from `python-zulip-api`.

5. Once you've entered the virtualenv, you should see something like this on the terminal:
   ```
   (zulip-api-py3-venv) user@pc ~/python-zulip-api $
   ```
   You should now be able to run any commands/tests/etc. in this
   virtual environment.

### Running tests

You can run all the tests with:

`pytest`

or test individual packages with `pytest zulip`, `pytest zulip_bots`,
or `pytest zulip_botserver` (see the [pytest
documentation](https://docs.pytest.org/en/latest/how-to/usage.html)
for more options).

To run the linter, type:

`./tools/lint`

To check the type annotations, run:

`./tools/run-mypy`
