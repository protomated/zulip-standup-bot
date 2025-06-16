# Deploying Standup Bot to CapRover with Zulip Botserver

This guide provides step-by-step instructions for deploying the Standup Bot to CapRover using the Zulip Botserver.

## Prerequisites

Before you begin, make sure you have:

1. **A CapRover server** set up and running
2. **A PostgreSQL database** (either hosted on CapRover or externally)
3. **A Zulip account for the bot** with API key
4. **An OpenAI API key** (optional, but recommended for AI summary generation)

## Step 1: Create a Bot in Zulip

1. Log in to your Zulip organization as an administrator
2. Go to **Settings** > **Organization settings** > **Bots**
3. Click **Add a new bot**
4. Select **Outgoing webhook** as the bot type
5. Fill in the bot details:
   - **Full name**: Standup Bot
   - **Username**: standup-bot (or your preferred username)
   - **Endpoint URL**: Leave blank for now (we'll update this later)
6. Click **Create bot**
7. Note down the **API key** that is generated
8. Also note the **outgoing webhook token** that is generated (you'll need this for the `ZULIP_BOTSERVER_CONFIG` environment variable)

## Step 2: Create a New App in CapRover

1. Log in to your CapRover dashboard
2. Go to **Apps** and click **Create a New App**
3. Enter a name for your app (e.g., `standup-bot`)
4. Click **Create New App**

## Step 3: Configure the Bot

You have two options for configuring the bot. Choose the method that works best for your deployment environment.

### Option 1: Using a botserverrc File (Recommended)

The recommended way to configure the bot is using a configuration file:

1. Create a file named `botserverrc` in your project directory with the following content:

   ```
   [standup]
   email=standup-bot@your-org.zulipchat.com
   key=your_bot_api_key
   site=https://your-org.zulipchat.com
   token=your-outgoing-webhook-token
   ```

   Replace:
   - `standup-bot@your-org.zulipchat.com` with your bot's email
   - `your_bot_api_key` with the API key from Step 1
   - `https://your-org.zulipchat.com` with your Zulip organization URL
   - `your-outgoing-webhook-token` with the token from Step 1

2. **Important**: Add `botserverrc` to your `.gitignore` file to avoid committing sensitive information:
   ```bash
   echo "botserverrc" >> .gitignore
   ```

3. For local development, you can copy the example file:
   ```bash
   cp botserverrc.example botserverrc
   ```
   Then edit it with your actual credentials.

4. When deploying to CapRover, you'll need to securely transfer this file to your server or create it directly on the server.

> **Note**: The Dockerfile is already configured to use the botserverrc file:
```
# Command to run the bot server
CMD ["zulip-botserver", "--config-file", "/app/botserverrc", "--port", "5002"]
```

### Option 2: Using Environment Variables (Alternative)

If you prefer to use environment variables:

1. In your CapRover dashboard, go to your newly created app
2. Click on the **Environmental Variables** tab
3. Add the following environment variables:

   ```
   # Zulip Botserver Configuration (required)
   # This is a JSON string with the bot configuration
   ZULIP_BOTSERVER_CONFIG={"standup": {"email": "standup-bot@your-org.zulipchat.com", "key": "your_bot_api_key", "site": "https://your-org.zulipchat.com", "token": "your-outgoing-webhook-token"}}

   # Zulip Configuration (used by the bot code)
   ZULIP_EMAIL=standup-bot@your-org.zulipchat.com
   ZULIP_API_KEY=your_bot_api_key
   ZULIP_SITE=https://your-org.zulipchat.com
   ZULIP_BOT_NAME=Standup Bot

   # OpenAI Configuration (optional, for AI summary generation)
   OPENAI_API_KEY=your_openai_api_key

   # Database Configuration (optional, for persistent storage)
   DATABASE_URL=postgresql://user:password@host:port/database

   # Bot Configuration (optional, defaults shown)
   DEFAULT_TIMEZONE=Africa/Lagos
   DEFAULT_PROMPT_TIME=09:30
   DEFAULT_CUTOFF_TIME=12:45
   DEFAULT_REMINDER_TIME=11:45

   # Logging Configuration (optional)
   LOG_LEVEL=INFO
   ```

   Replace the values with your actual credentials.

4. Click **Add Environmental Variables**

5. Modify the Dockerfile to use environment variables:
   ```
   # Command to run the bot server
   CMD ["zulip-botserver", "--use-env-vars", "--bot-name", "standup", "--port", "5002"]
   ```
   The `--bot-name` argument is required to tell the bot server which bot module to load. Note that you should specify the bot name without the .py extension.

### Troubleshooting Configuration Issues

If you encounter the error: `Error: Bot "standup" doesn't exist. Please make sure you have set up the botserverrc file correctly.`

This means the Zulip botserver cannot find a bot with the name "standup" in your configuration. Check:

1. If using a botserverrc file:
   - The file exists in the project root (not in the zulip_bots/bots/standup/ directory)
   - It contains a section with the correct bot name: `[standup]`
   - All credentials are correct
   - The Dockerfile includes the `--config-file` parameter

2. If using environment variables:
   - The `ZULIP_BOTSERVER_CONFIG` variable is correctly formatted
   - It contains a key for your bot: `{"standup": {...}}`
   - The Dockerfile does NOT include the `--config-file` parameter
   - The Dockerfile includes the `--bot-name` argument with the correct bot name (without the .py extension)
   - The bot file exists in the specified location (zulip_bots/bots/standup/standup.py)


## Step 4: Configure Port Mapping

1. In your CapRover dashboard, go to your app
2. Click on the **App Configs** tab
3. Under **Container HTTP Port**, enter `5002` (this is the port exposed in the Dockerfile)
4. Click **Save & Update**

## Step 5: Deploy the Bot

### Option 1: Deploy from GitHub

1. In your CapRover dashboard, go to your app
2. Click on the **Deployment** tab
3. Under **Method 3: Deploy from Github/Bitbucket/Gitlab**, enter the repository URL
4. Set the branch to `main` or your preferred branch
5. Click **Deploy**

### Option 2: Deploy using CapRover CLI

1. Install the CapRover CLI: `npm install -g caprover`
2. Navigate to your project directory
3. Run `caprover deploy`
4. Follow the prompts to select your CapRover server and app

### Option 3: Deploy using tar file

1. Create a tar file of your project: `tar -czf standup-bot.tar.gz *`
2. In your CapRover dashboard, go to your app
3. Click on the **Deployment** tab
4. Under **Method 2: Upload tar file**, upload your tar file
5. Click **Deploy**

## Step 6: Update the Webhook URL in Zulip

1. After deployment, note the URL of your app (e.g., `https://standup-bot.your-caprover-domain.com`)
2. Go back to your Zulip organization settings
3. Find your bot and click **Edit**
4. Update the **Endpoint URL** to your app URL
5. Make sure the **Outgoing webhook token** matches the one you set in the `ZULIP_BOTSERVER_CONFIG` environment variable
6. Click **Save changes**

## Step 7: Verify the Deployment

1. In Zulip, add the bot to a channel where you want to use it
2. Send a test message: `/standup help`
3. The bot should respond with its usage instructions

## Troubleshooting

If you encounter issues:

1. **Check the logs**: In CapRover, go to your app and click on the **Logs** tab
2. **Verify environment variables**: Make sure all required environment variables are set correctly
3. **Check database connection**: Ensure your PostgreSQL database is accessible from your CapRover app
4. **Restart the app**: Sometimes a simple restart can fix issues

## Using supervisord (Alternative Deployment)

If you prefer to use supervisord instead of CapRover, follow these steps:

1. Install supervisord: `sudo apt-get install supervisor`
2. Create a configuration file at `/etc/supervisor/conf.d/zulip-botserver.conf`:

   ```
   [program:zulip-botserver]
   command=zulip-botserver --use-env-vars
   directory=/path/to/your/bot  # This should be the root directory of the project, not the zulip_bots/bots/standup/ directory
   environment=ZULIP_BOTSERVER_CONFIG='{"standup": {"email": "your-bot-email@example.com", "key": "your-api-key", "site": "https://your-zulip-site.com", "token": "your-outgoing-webhook-token"}}',DATABASE_URL='postgresql://user:password@host:port/database'
   autostart=true
   autorestart=true
   startsecs=3
   stdout_logfile=/var/log/zulip-botserver.log
   redirect_stderr=true
   ```

3. Update supervisord: `supervisorctl reread && supervisorctl update`
4. Check status: `supervisorctl status zulip-botserver`

## Next Steps

Once deployed, you can:

1. Set up standups in your channels with `/standup setup`
2. Configure your timezone with `/standup timezone America/New_York`
3. Customize prompt and cutoff times with `/standup config prompt_time 10:00`

For more details on using the bot, refer to the [README.md](./README.md) file.
