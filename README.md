
# `bamboo-ci-health`

Health reporting tool for Bamboo CI builds.


## What For? 

The reports are aimed at helping Developer Experience (DX) and DevOps team
members identify where mismanaged build plans are bogging down the Bamboo Master
e.g. excessive retention of build results, inefficient use of build artifacts
(unspecific or too big/bloated archives), and more.


## Getting Started

Create a local Bamboo-PostgreSQL deployment using Docker:

    docker-compose build && docker-compose up -d
    docker ps  # Verify Bamboo and PostgreSQL are both up and healthy

Have Python 3.8+ installed on MacOS or Linux and create a virtualenv:

    python3 -m venv venv
    . venv/bin/activate
    pip install -r requirements.txt
    ./generate_reports.py --help


## Contact

Do you want to help? Welcome!
