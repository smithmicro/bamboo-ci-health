FROM atlassian/bamboo-server:8.2.5

# Linux basics
RUN apt-get update && apt-get install --yes mlocate htop emacs wget tree jq dnsutils traceroute

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
