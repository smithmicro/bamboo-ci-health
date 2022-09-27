FROM atlassian/bamboo-server:8.2.5

# Linux basics
RUN apt-get update && apt-get install --yes mlocate htop emacs wget tree jq dnsutils traceroute psmisc

# Docker Engine (https://docs.docker.com/engine/install/ubuntu/)
RUN apt-get install --yes ca-certificates curl gnupg lsb-release

RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

RUN echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN apt-get update && apt-get install --yes docker-ce-cli docker-compose

# Python development
RUN apt-get install --yes python3-venv python3-pandas python3-sqlalchemy libmysqlclient-dev ipython3

# Node development
RUN curl -fsSL https://deb.nodesource.com/setup_14.x | bash - \
    && apt-get install --yes nodejs \
    && npm install -g npm@6

# Java/Scala/Kotlin development
RUN apt-get install --yes openjdk-8-jdk openjdk-11-jdk gradle scala kotlin

# Ruby and Provisioning/CD
RUN apt-get install --yes ruby rubygems ansible awscli

# Add custom logo
ADD attachments /opt/atlassian/etc/attachments

# Allow unprivileged `bamboo` user to interact with Docker engine
ARG DOCKER_GID=2005
RUN groupmod -g $DOCKER_GID bamboo
