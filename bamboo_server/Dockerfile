FROM atlassian/bamboo-server:8.2.5

# Linux basics
RUN apt-get update && apt-get install --yes mlocate htop emacs

# Python dependencies
RUN apt-get install --yes python3-venv python3-pandas python3-sqlalchemy 

# Node development
RUN apt-get install --yes nodejs npm yarnpkg

# Provisioning/CD
RUN apt-get install --yes ansible awscli
