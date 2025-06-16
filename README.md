# Zulip Standup Bot

[![Build status](https://github.com/zulip/python-zulip-api/workflows/build/badge.svg)](
https://github.com/zulip/python-zulip-api/actions?query=branch%3Amain+workflow%3Abuild)
[![Coverage status](https://img.shields.io/codecov/c/github/zulip/python-zulip-api)](
https://codecov.io/gh/zulip/python-zulip-api)

This repository contains a Zulip Standup Bot built on top of Zulip's PyPI packages:

* `zulip`: [PyPI package](https://pypi.python.org/pypi/zulip/)
  for Zulip's API bindings.
* `zulip_bots`: [PyPI package](https://pypi.python.org/pypi/zulip-bots)
  for Zulip's bots and bots API.
* `zulip_botserver`: [PyPI package](https://pypi.python.org/pypi/zulip-botserver)
  for Zulip's Flask Botserver.

The source code is written in *Python 3*.

## Features

The Standup Bot helps teams run asynchronous standups in Zulip channels:

- **Timezone-aware scheduling**: Prompts team members at appropriate times in their local timezone
- **Flexible configuration**: Customize prompt times, cutoff times, and reminders
- **AI-powered summaries**: Generates concise summaries of team updates using OpenAI (optional)
- **Persistent storage**: Stores user preferences and standup responses in a database

### Usage

Once deployed, you can interact with the bot using these commands:

- `/standup setup` - Activate standup for a channel
- `/standup timezone America/New_York` - Set your timezone
- `/standup config prompt_time 10:00` - Configure prompt time
- `/standup help` - Show all available commands

## Deployment

### Deploying to CapRover

The Standup Bot can be easily deployed to [CapRover](https://caprover.com/), a free and open-source PaaS.

#### Configuration Options

You have two options for configuring the bot:

1. **Using Environment Variables** (Recommended for CapRover)
   - Secure and follows container best practices
   - Easy to manage through the CapRover dashboard
   - No need to modify the Dockerfile

2. **Using a Configuration File**
   - Traditional approach using a `botserverrc` file
   - Requires modifying the Dockerfile CMD
   - See [DEPLOYMENT.md](./DEPLOYMENT.md) for details

#### Quick Start with Environment Variables

1. Create a new app in your CapRover dashboard
2. Set up environment variables for configuration:
   ```
   # Zulip Botserver Configuration (required)
   ZULIP_BOTSERVER_CONFIG={"standup": {"email": "your-bot-email@example.com", "key": "your-api-key", "site": "https://your-zulip-site.com", "token": "your-outgoing-webhook-token"}}

   # Database Configuration (optional, for persistent storage)
   DATABASE_URL=postgresql://user:password@host:port/database

   # OpenAI Configuration (optional, for AI summary generation)
   OPENAI_API_KEY=your_openai_api_key
   ```
3. Deploy using one of these methods:
   - GitHub repository
   - CapRover CLI
   - Uploading a tar file
4. **Important**: After deployment, update your Zulip bot's webhook URL:
   - Go to your Zulip organization settings
   - Find your bot and click **Edit**
   - Set the **Endpoint URL** to your CapRover app URL (e.g., `https://standup-bot.your-caprover-domain.com`)
   - Verify the outgoing webhook token matches the one in your configuration
5. Verify your deployment:
   - Add the bot to a channel in Zulip
   - Send a test message: `/standup help`
   - The bot should respond with usage instructions

For detailed instructions, including setting up the Zulip bot, configuring port mapping, and troubleshooting, see [DEPLOYMENT.md](./DEPLOYMENT.md).

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
