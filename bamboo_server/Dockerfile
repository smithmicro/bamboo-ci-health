FROM atlassian/bamboo-server:8.2.5

RUN curl -sL https://dev.mysql.com/get/Downloads/Connector-J/mysql-connector-java-8.0.30.tar.gz | tar xvz -C /tmp \
    && cp -va /tmp/mysql-connector-java-8.0.30/mysql-connector-java-8.0.30.jar /opt/atlassian/bamboo/lib/ \
    && rm -rf /tmp/mysql-connector-java-8.0.30*
