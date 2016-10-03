FROM debian:stretch
RUN apt-get update -y
RUN apt-get install -y docker.io git python3.5 python3-pip
RUN pip3 install pyyaml gitpython docker-compose
#ENV COMPOSE_API_VERSION=1.18
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY __init__.py /usr/src/app
CMD [ "python3", "-u", "./__init__.py", "--force" ]
