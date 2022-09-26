
# `bamboo-ci-health`

Health reporting tool for Bamboo CI builds.


## What For? 

The reports are aimed at helping Developer Experience (DX) and DevOps team
members identify where mismanaged build plans are bogging down the Bamboo Master
e.g. excessive retention of build results, inefficient use of build artifacts
(unspecific or too big/bloated archives), and more.


## Getting Started

**Compatibility:** Verified to work on x86 hardware with latest MacOS or CentOS 7.

Create a local Bamboo-PostgreSQL deployment using Docker (version 20.10 or newer):

    cp -v .env-template .env
    vi .env  # Fill out with your own license and secrets, don't track it in Git.
    docker-compose build
    docker-compose up -d
    docker-compose ps  # Verify Bamboo is up and healthy.

    # Optionally, copy the Bamboo application code to local directory:
    docker cp bamboo_server:/opt/atlassian/ ./bamboo_opt

Additional tip for Linux, add a host local account for the Bamboo user:

    useradd -u 2005 -m -G docker bamboo

Open `https://${PROXY_HOSTNAME}/` in your browser and verify that you
can login the using credentials specified by _BAMBOO_ADMIN_USERNAME_ and
_BAMBOO_ADMIN_PASSWORD_ in your `.env` file.

If the server is exposed on the internet, please open _Bamboo administration_ &gt;
_Global permissions_ and disable access for "Anonymuous users" and
(any) "Logged in users".

Next, have Python 3.8+ installed on MacOS or Linux and create a virtualenv:

    python3 -m venv venv
    . venv/bin/activate
    pip install -r requirements.txt
    ./generate_reports.py --help


## Contact

Do you want to help? Welcome!
