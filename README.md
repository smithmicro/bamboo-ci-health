
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
    docker cp bamboo_server:/opt/atlassian/ ./data/bamboo_opt

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


## Live Deployment

In order to deploy the Bamboo stack to a live server, you need a DNS hostname,
SSL certificate/key, and a Linux OS with Git and Docker (version 20.10 or newer).

Step 1: Clone the repo to `/opt/bamboo-ci-health/`:

    cd /opt/ && git clone git@.../bamboo-ci-health.git

Step 2: Fill in your config secrets in the environment file:

    cd /opt/bamboo-ci-health/
    cp -v .env-template .env
    vi .env
    # Fill out with license and hostname, e.g. `PROXY_HOSTNAME=bamboo.mkdevops.se` and so on
    cp -v ~/my-ssl-certificate.crt ./bamboo_nginx/certs/bamboo.mkdevops.se.crt 
    cp -v ~/my-ssl-certificate.key ./bamboo_nginx/certs/bamboo.mkdevops.se.key 
    docker-compose build
    docker-compose up -d
    docker-compose ps  # Verify all services are up and healthy.

Step 3: Configure Bamboo by opening `https://${PROXY_HOSTNAME}/` in your browser
and switch to the _Bamboo administration_ view, for example ...

1. Restrict access under _Global permissions_
2. Add a local agent under _Agents_
3. Link GitHub/Bitbucket repositories under _Linked repositories_
4. Add Git SSH key under _Shared credentials_
5. Configure Crowd authentication under _User directories_
6. ...


## Contact

Do you want to help? Welcome!
