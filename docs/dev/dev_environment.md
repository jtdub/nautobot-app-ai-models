# Building Your Development Environment

## Quickstart Guide

You can use the development environment in two ways:

1. **(Recommended)** Docker containers run each service, Nautobot included. A volume mount lets you develop locally.
2. A local Poetry environment, if you want to develop outside Docker. Docker still gives the database (PostgreSQL by default, MySQL as an option) and Redis.

This is a quick reference. The rest of this document gives the details.

### Invoke

The [Invoke](http://www.pyinvoke.org/) library gives helper commands for the environment. You can send these parameters to Invoke to override the default configuration:

- `nautobot_ver`: the version of Nautobot to use as a base for any built docker containers (default: 3.1.0)
- `project_name`: the default docker compose project name (default: `ai-models`)
- `python_ver`: the version of Python to use as a base for any built docker containers (default: 3.12)
- `local`: a boolean flag. It says whether an invoke task runs on the host or in the Docker containers (default: False, which runs the command in a container)
- `compose_dir`: the full path to a directory containing the project compose files
- `compose_files`: a list of compose files applied in order (see [Multiple Compose files](https://docs.docker.com/compose/extends/#multiple-compose-files) for more information)
- `ephemeral_ports`: Setting this value to `true` and not using any custom compose files will make all Nautobot containers with published ports expose themselves with dynamic ports. This is useful when running multiple Nautobot versions at the same time on the same machine so you won't experience system port conflicts. If setting `compose_files`, this will have no effect so please ensure to manually add the applicable `docker-compose.ephemeral-ports.yml` file or files to your list.

**Invoke** gives [several methods](https://docs.pyinvoke.org/en/stable/concepts/configuration.html) to override these options. The simplest is an environment variable named `INVOKE_NAUTOBOT_AI_MODELS_VARIABLE_NAME`, where `VARIABLE_NAME` is the option to override. `compose_files` is the one exception. It is a list, so you must override it in a YAML file. Start from the example file `invoke.example.yml` in this directory.

### Docker Development Environment

!!! tip
    This is the recommended option for development.

[Python Poetry](https://python-poetry.org/) manages this project. Your development environment needs these three things:

1. Install Poetry, see the [Poetry documentation](https://python-poetry.org/docs/#installation) for your operating system.
2. Install Docker, see the [Docker documentation](https://docs.docker.com/get-docker/) for your operating system.
3. Install Docker-compose, see the [Docker-compose documentation](https://github.com/docker/compose) for your operation system.

After you install Poetry and Docker, run these commands in the root of the repository. They install the other development dependencies in an isolated Python virtual environment:

```shell
poetry self add poetry-plugin-shell
poetry shell
poetry install
invoke build
invoke start
```

The Nautobot server can now be accessed at [http://localhost:8080](http://localhost:8080) and the live documentation at [http://localhost:8001](http://localhost:8001).

`invoke start` and `invoke debug` write the published host port mappings to `.service_ports.json`. The file lists only the services that publish a port to the host. With ephemeral ports, Docker assigns a dynamic host port and the file records it. With fixed ports, the file records the static value.

You can also read the ports with `invoke ps` or with `docker compose port`, for example `docker compose port nautobot 8080`.

To turn on ephemeral ports, set `INVOKE_NAUTOBOT_AI_MODELS_EPHEMERAL_PORTS=1`. To turn them off, unset the variable, set it to an empty value, or set it to `0`.

Use one of these two commands to stop or to destroy the development environment.

- **invoke stop** - Stop the containers, but keep all underlying systems intact
- **invoke destroy** - Stop and remove each container and volume. CAUTION: This deletes the volume, so you lose the data in it.

### Local Poetry Development Environment

- Create an `invoke.yml` file at the root of the repository with the contents below. Edit it as necessary.

```yaml
---
nautobot_ai_models:
  local: true
```

Run the following commands:

```shell
poetry self add poetry-plugin-shell
poetry shell
poetry install --extras nautobot
export $(cat development/development.env | xargs)
export $(cat development/creds.env | xargs)
invoke start && sleep 5
nautobot-server migrate
```

!!! note
    If you want to develop on the latest develop branch of Nautobot, run the following command: `poetry add --optional git+https://github.com/nautobot/nautobot@develop`. After the `@` symbol must match either a branch or a tag.

You can now run a `nautobot-server` command, as the [Nautobot documentation](https://docs.nautobot.com/projects/core/en/stable/user-guide/administration/tools/nautobot-server/) describes. For example, start the development server:

```shell
nautobot-server runserver 0.0.0.0:8080 --insecure
```

Nautobot server can now be accessed at [http://localhost:8080](http://localhost:8080).

Start the Nautobot **runserver** command in a separate shell. You can then continue to develop and manage the web server apart from each other.

### Updating the Documentation

The documentation dependencies are pinned to exact versions, which gives a consistent result. The `pyproject.toml` file defines them for the development environment.

### CLI Helper Commands

The project has a CLI helper that uses [Invoke](https://www.pyinvoke.org/). It sets up the development environment. The commands are in three categories:

- `dev environment`
- `utility`
- `testing`

Run a command with `invoke <command>`. Each command accepts `--nautobot-ver` and `--python-ver` to set the Nautobot and Python versions. Each command has its own help: `invoke <command> --help`.

#### Local Development Environment

```
  build            Build all docker images.
  debug            Start Nautobot and its dependencies in debug mode.
  destroy          Destroy all containers and volumes.
  restart          Restart Nautobot and its dependencies in detached mode.
  start            Start Nautobot and its dependencies in detached mode.
  stop             Stop Nautobot and its dependencies.
```

#### Utility

```
  cli              Launch a bash shell inside the running Nautobot container.
  create-user      Create a new user in django (default: admin), will prompt for password.
  makemigrations   Run Make Migration in Django.
  nbshell          Launch a nbshell session.
```

#### Testing

```
  ruff             Run ruff to perform code formatting and/or linting.
  pylint           Run pylint code analysis.
  markdownlint     Run pymarkdown linting.
  tests            Run all tests for this app.
  unittest         Run Django unit tests for the app.
  djlint           Run djlint to perform django template linting.
  djhtml           Run djhtml to perform django template formatting.
```

## Project Overview

You can manage the Nautobot server locally, with Docker for the supporting services, or you can manage Nautobot in Docker as well. The difference is **pdb**. Locally, you can debug with **pdb** directly. In a container, you must first enter the container with `docker exec`, or attach your IDE to the container and start the Nautobot service by hand.

Docker has one advantage: you do not manage the Nautobot server. The [Docker logs](#docker-logs) give most of the data that you need to find a problem. You start quickly, you do several fewer manual steps, and you do not keep a separate terminal open for the server.

!!! note
	The local environment still uses Docker containers for the supporting services (Postgres, Redis, and RQ Worker), but the Nautobot server is handled locally by you, the developer.

Obey the directions below for the development environment that you select.

## Poetry

Poetry replaces the "virtualenv" commands, in both environments. The virtual environment gives each Python package that manages the development environment, such as **Invoke**. To install Nautobot for local development, read the [Local Development Environment](#local-poetry-development-environment) section.

The `pyproject.toml` file lists the dependencies of the project:

- `tool.poetry.dependencies` - the main list of dependencies.
- `tool.poetry.group.dev.dependencies` - the development dependencies, for the lint, the test, and the documentation build.

The `poetry shell` command creates a virtual environment and enables it. Each command after that runs in the environment. This is the same as `source venv/bin/activate` with a virtualenv. Run `poetry install` to install the dependencies in the environment. It installs **both** the project and the development dependencies.

For more about Poetry and its commands, read the [online documentation](https://python-poetry.org/docs/).

Poetry version 2 moved the shell command into a plugin. For more about that plugin, read its [GitHub repository](https://github.com/python-poetry/poetry-plugin-shell).

## Full Docker Development Environment

This project has a set of **Invoke** tasks. Use them as CLI commands to start your environment quickly.

### Copy the credentials file for Nautobot

First, create the `development/creds.env` file. It holds private data, such as the passwords and the tokens of your local Nautobot install. Copy `development/creds.example.env` and edit the copy.

```shell
cp development/creds.example.env development/creds.env
```

### Invoke - Building the Docker Image

First, build the Docker image for Nautobot. The image installs the version in `nautobot_ver`. Docker Compose uses this image for Nautobot and for the Celery worker service.

```bash
➜ invoke build
... <omitted for brevity>
#14 exporting to image
#14 sha256:e8c613e07b0b7ff33893b694f7759a10d42e180f2b4dc349fb57dc6b71dcab00
#14 exporting layers
#14 exporting layers 1.2s done
#14 writing image sha256:2d524bc1665327faa0d34001b0a9d2ccf450612bf8feeb969312e96a2d3e3503 done
#14 naming to docker.io/ai-models/nautobot:3.1.0-py3.12 done
```

### Invoke - Starting the Development Environment

Next, start your Docker containers.

```bash
➜ invoke start
Starting Nautobot in detached mode...
Running docker-compose command "up --detach"
Creating network "nautobot_ai_models_default" with the default driver
Creating volume "nautobot_ai_models_postgres_data" with default driver
Creating nautobot_ai_models_redis_1 ...
Creating nautobot_ai_models_docs_1  ...
Creating nautobot_ai_models_postgres_1 ...
Creating nautobot_ai_models_postgres_1 ... done
Creating nautobot_ai_models_redis_1    ... done
Creating nautobot_ai_models_nautobot_1 ...
Creating nautobot_ai_models_docs_1     ... done
Creating nautobot_ai_models_nautobot_1 ... done
Creating nautobot_ai_models_worker_1   ...
Creating nautobot_ai_models_worker_1   ... done
Docker Compose is now in the Docker CLI, try `docker compose up`
```

This starts each Docker container that hosts Nautobot. After `invoke start` finishes, these containers run:

```bash
➜ docker ps
****CONTAINER ID   IMAGE                            COMMAND                  CREATED          STATUS          PORTS                                       NAMES
ee90fbfabd77   ai-models/nautobot:3.1.0-py3.12  "nautobot-server rqw…"   16 seconds ago   Up 13 seconds                                               nautobot_ai_models_worker_1
b8adb781d013   ai-models/nautobot:3.1.0-py3.12  "/docker-entrypoint.…"   20 seconds ago   Up 15 seconds   0.0.0.0:8080->8080/tcp, :::8080->8080/tcp   nautobot_ai_models_nautobot_1
d64ebd60675d   ai-models/nautobot:3.1.0-py3.12  "mkdocs serve -v -a …"   25 seconds ago   Up 18 seconds   0.0.0.0:8001->8080/tcp, :::8001->8080/tcp   nautobot_ai_models_docs_1
e72d63129b36   postgres:13-alpine               "docker-entrypoint.s…"   25 seconds ago   Up 19 seconds   0.0.0.0:5432->5432/tcp, :::5432->5432/tcp   nautobot_ai_models_postgres_1
96c6ff66997c   redis:6-alpine                   "docker-entrypoint.s…"   25 seconds ago   Up 21 seconds   0.0.0.0:6379->6379/tcp, :::6379->6379/tcp   nautobot_ai_models_redis_1
```

After the containers start, open a web browser and go to:

- The Nautobot homepage at [http://localhost:8080](http://localhost:8080)
- A live version of the documentation at [http://localhost:8001](http://localhost:8001)

!!! note
	Sometimes the containers take a minute to fully spin up. If the page doesn't load right away, wait a minute and try again.

### Invoke - Creating a Superuser

The Nautobot development image creates a superuser when `creds.env` sets these variables. A copy of `creds.example.env` sets them by default.

- `NAUTOBOT_CREATE_SUPERUSER=true`
- `NAUTOBOT_SUPERUSER_API_TOKEN=0123456789abcdef0123456789abcdef01234567`
- `NAUTOBOT_SUPERUSER_PASSWORD=admin`

!!! note
	The default username is **admin**, but can be overridden by specifying **NAUTOBOT_SUPERUSER_USERNAME**.

To create another superuser, run these commands.

```bash
➜ invoke createsuperuser
Running docker-compose command "ps --services --filter status=running"
Running docker-compose command "exec nautobot nautobot-server createsuperuser --username admin"
Error: That username is already taken.
Username: ntc
Email address: ntc@networktocode.com
Password:
Password (again):
Superuser created successfully.
```

### Invoke - Stopping the Development Environment

The last command to learn is `invoke stop`.

```bash
➜ invoke stop
Stopping Nautobot...
Running docker-compose command "down"
Stopping nautobot_ai_models_worker_1   ...
Stopping nautobot_ai_models_nautobot_1 ...
Stopping nautobot_ai_models_docs_1     ...
Stopping nautobot_ai_models_redis_1    ...
Stopping nautobot_ai_models_postgres_1 ...
Stopping nautobot_ai_models_worker_1   ... done
Stopping nautobot_ai_models_nautobot_1 ... done
Stopping nautobot_ai_models_postgres_1 ... done
Stopping nautobot_ai_models_redis_1    ... done
Stopping nautobot_ai_models_docs_1     ... done
Removing nautobot_ai_models_worker_1   ...
Removing nautobot_ai_models_nautobot_1 ...
Removing nautobot_ai_models_docs_1     ...
Removing nautobot_ai_models_redis_1    ...
Removing nautobot_ai_models_postgres_1 ...
Removing nautobot_ai_models_postgres_1 ... done
Removing nautobot_ai_models_docs_1     ... done
Removing nautobot_ai_models_worker_1   ... done
Removing nautobot_ai_models_redis_1    ... done
Removing nautobot_ai_models_nautobot_1 ... done
Removing network nautobot_ai_models_default
```

This stops each running Docker container of this project safely. To start them again, run `invoke start`, [as above](#invoke-starting-the-development-environment).

!!! warning
	If you're wanting to reset the database and configuration settings, you can use the `invoke destroy` command, but **you will lose any data stored in those containers**, so make sure that is what you want to do.

### Real-Time Updates? How Cool!

Your environment is now set up. The Docker containers run, and you are signed in to Nautobot in your web browser.

You can now develop your app in the project folder.

The root directory is mounted in the Docker containers. Thus **each** change to a file here goes straight to the app code that runs in Docker.

!!! warning
	There are a few exceptions to this, as outlined in the section [To Rebuild or Not To Rebuild](#to-rebuild-or-not-to-rebuild).

The Django process reloads itself when you save a file. It takes a few seconds. For example, save a change to `tables.py`, and your web browser shows the result at once.

!!! note
	You may get connection refused while Django reloads, but it should be refreshed fairly quickly.

### Docker Logs

To debug a problem, read the logs in the Docker containers.

```bash
➜ docker logs <name of container> -f
```

!!! note
	The `-f` tag will keep the logs open, and output them in realtime as they are generated.

!!! info
    Want to limit the log output even further? Use the `--tail <#>` command line argument in conjunction with `-f`.

This app is named `ai-models`, so the command is usually `docker logs nautobot_ai_models_nautobot_1 -f`. `docker ps` gives the name of each running container.

To read the logs of the worker container, use the name of that container.

## To Rebuild or Not to Rebuild

Usually you do not rebuild the images. `invoke start` and `invoke stop` are enough.

Two cases need a rebuild.

### Updating Environment Variables

To add an environment variable for Nautobot to use, add it to the `development/development.env` file. This changes the container shell, not Django. Django restarts itself on a change; the container shell does not.

To apply a new environment variable, stop the running images, rebuild them, and start them again. Three commands do this:

```bash
➜ invoke stop
➜ invoke build
➜ invoke start
```

The new environment variable is then live.

### Installing Additional Python Packages

To use another Nautobot app or another Python package, add it to your Docker environment.

```bash
➜ poetry add <package_name>
```

After Poetry resolves the dependencies, stop the containers, rebuild the Docker image, and start the containers again.

```bash
➜ invoke stop
➜ invoke build
➜ invoke start
```

### Installing Additional Nautobot Apps

For example, your new app must work with Slack. To do this, use the Nautobot ChatOps App.

```bash
➜ poetry add nautobot-chatops
```

Activate the virtual environment with Poetry. Then tell Poetry to install the new app.

Before you continue, edit `development/nautobot_config.py`. Add the name of the new app to `PLUGINS`, and add its settings to `PLUGINS_CONFIG`. You change the operating system, not only a Django file, so you must rebuild the image. This is the same process as the one for an environment variable above.

```bash
➜ invoke stop
➜ invoke build
➜ invoke start
```

After the containers start, your Nautobot instance shows the new app.

!!! note
    You can even launch an `ngrok` service locally on your laptop, pointing to port 8080 (such as for chatops development), and it will point traffic directly to your Docker images.

### Updating Python Version

To change the Python version, edit `tasks.py`.

```python
namespace = Collection("nautobot_ai_models")
namespace.configure(
    {
        "nautobot_ai_models": {
            ...
            "python_ver": "3.12",
	    ...
        }
    }
)
```

You can also set the `INVOKE_NAUTOBOT_AI_MODELS_PYTHON_VER` variable.

### Updating Nautobot Version

To change the Nautobot version, edit `tasks.py`.

```python
namespace = Collection("nautobot_ai_models")
namespace.configure(
    {
        "nautobot_ai_models": {
            ...
            "nautobot_ver": "3.1.0",
	    ...
        }
    }
)
```

You can also set the `INVOKE_NAUTOBOT_AI_MODELS_NAUTOBOT_VER` variable.

## Other Miscellaneous Commands To Know

### Python Shell

To drop into a Django shell for Nautobot (in the Docker container) run:

```bash
➜ invoke nbshell
```

This is the same as running:

```bash
➜ invoke cli
➜ nautobot-server nbshell
```

### iPython Shell Plus

Django also has a richer shell. It uses iPython and imports each model for you:

```bash
➜ invoke shell-plus
```

This is the same as running:

```bash
➜ invoke cli
➜ nautobot-server shell_plus
```

### Tests

To test your code, run each test that CI runs against a new PR:

```bash
➜ invoke tests
```

To run one test, use one of these commands:

```bash
➜ invoke unittest
➜ invoke ruff
➜ invoke pylint
```

### App Configuration Schema

The package holds `nautobot_ai_models/app-config-schema.json`, in the [JSON Schema](https://json-schema.org/) format. The CI pipeline uses this file to validate the configuration of the app.

After you change `PLUGINS_CONFIG` or the schema, run this command to validate the schema:

```bash
invoke validate-app-config
```

To generate `app-config-schema.json` from the current `PLUGINS_CONFIG`, run this command:

```bash
invoke generate-app-config-schema
```

The command can only guess the schema. Correct the result by hand.

### Documentation Screenshots

The images under `docs/images/` and `docs/media/` come from a running development instance, through
[Playwright](https://playwright.dev/python/). Capture them again after you change the UI, then
commit the new files.

Install the capture tool once. It is not a dependency of the app.

```bash
pip install playwright
python -m playwright install chromium
```

Start the environment and populate it:

```bash
invoke start
invoke createsuperuser
nautobot-server generate_nautobot_ai_models_test_data
```

Then capture:

```bash
python development/bin/take_screenshots.py --url http://localhost:8080
```

The script signs in, sets each color theme through the `theme` and `theme_choice` cookies, removes
the Django Debug Toolbar, hides the development banner, and writes one file for each view. Use
`--username` and `--password` to change the defaults.

The job-result screenshot needs a **Discover AI Models** job result. Before you capture, run the
job once against a provider whose endpoint answers `GET /v1/models`.

The **Run Discovery** button on an MCP Server detail page appears only when the **MCP Server
Discovery** job is installed and enabled. Enable the job before you capture. If you do not, the
button is missing from the screenshot.
