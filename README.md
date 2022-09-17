
# `bamboo-ci-health`

Health reporting tool for Bamboo CI builds.


## What For? 

The reports are aimed at helping Developer Experience (DX) and DevOps team
members identify where mismanaged build plans are bogging down the Bamboo Master
e.g. excessive retention of build results, inefficient use of build artifacts
(unspecific or too big/bloated archives), and more.


## Getting Started

Create a local Bamboo-PostgreSQL deployment using Docker:

    cp -v .env-template .env
    vi .env  # Fill out with your own license and secrets, don't track it in Git.
    docker-compose up -d postgresql_server && sleep 5 && docker ps  # Verify it's up.
    docker-compose build
    docker-compose up bamboo_server  # Verify Bamboo is up and healthy.

Open `https://${PROXY_HOSTNAME}/` in your browser and verify that you
can login the using credentials specified by _BAMBOO_ADMIN_USERNAME_ and
_BAMBOO_ADMIN_PASSWORD_ in your `.env` file.

Next, have Python 3.8+ installed on MacOS or Linux and create a virtualenv:

    python3 -m venv venv
    . venv/bin/activate
    pip install -r requirements.txt
    ./generate_reports.py --help


## Contact

Do you want to help? Welcome!
