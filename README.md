# What is moon?

Moon is a very simple continuous integration/continuous deployment system to spin up docker containers and sync them with their git repositories.

No configuration is needed in your git platform as moon doesn't rely on web hooks to update your apps. Any repository supporting git clone and git fetch will work.

Note: At this point moon only supports public repositories

# Installation

Note that for all the commands below you may need to su/sudo as superuser.
First install Docker on your server. For example on a Debian-based server:
```
apt-get install docker.io
```


Pull the moon image:
```
docker pull bienaimable/moon
```

Create the moon folder:
```
mkdir /var/moon/
```



# Usage

Create the configuration file:
```
nano /var/moon/configuration.yml
```

Write the content of the configuration file, for example:
```
apps:
    my_app:
        url: http://github.com/john.doe/my_app.git
        branch: master
        compose:
            main:
                build: .
                volumes:
                    - /var/moon/storage/scopealerts:/var/storage
```

Each app will need a name (my_app here), a HTTP URL to a public Git repository, the branch to use, and the content of the docker-compose.yml file under compose.

Now run the container:
```
docker run \
	--volume /var/run/docker.sock:/var/run/docker.sock \
	--volume /var/moon:/var/moon \
	--restart=always \
	--detach=true \
	--name=moon \
	bienaimable/moon
```

That's it. Moon has started all the apps in the configuration.
It is now watching its configuration file for changes and the repositories for new commits.
Every time there is a change in the repository or the configuration, Moon will kill the app (stop and remove the container, then clean the repository folder) and start it again.

To stop moon:
```
docker stop moon
docker rm moon
```

Please note that stopping moon doesn't stop the apps.
To stop the apps, empty the apps section in the configuration file and let moon kill them.
Alternatively, stop the apps manually by using:
```
docker stop yourappname
docker rm -f yourappname
```

# Advanced example
If you wanted to add some logging capabilities to your moon stack you could add a log driver to moon when you load it:
```

docker run \
	--volume /var/run/docker.sock:/var/run/docker.sock \
	--volume /var/moon:/var/moon \
	--restart=always \
	--detach=true \
    --log-driver=gelf
    --log-opt gelf-address="udp://localhost:12201"
	--name=moon \
	bienaimable/moon
```

And then have moon load an ELK/elastic stack:

```
apps:
    elastic_stack:
        url: http://gitlab.x.com/x/moon_config.git
        branch: master
        compose:
            kibana:
                image: kibana
                ports:
                    - "5601:5601"
                links:
                    - elasticsearch:elasticsearch
            elasticsearch:
                image: elasticsearch
                ports:
                    - "9200:9200"
                    - "9300:9300"
            logstash:
                build: logstash
                ports:
                    - "12201:12201"
                    - "12201:12201/udp"
                links:
                    - elasticsearch:elasticsearch
    scopealerts:
        url: http://gitlab.x.com/x/scopealerts.git
        branch: production
        compose:
            main:
                build: .
                volumes:
                    - /var/moon/storage/scopealerts:/var/storage
                net: host
                log_driver: gelf
                log_opt:
                    gelf-address: "udp://localhost:12201"
    testing_ci_master2:
        url: http://gitlab.x.com/x/testing_ci.git
        branch: master
        compose: 
            main:
                build: .
                volumes:
                    - /var/moon/storage/testing_ci_master2:/var/storage
                net: host
                log_driver: gelf
                log_opt:
                    gelf-address: "udp://localhost:12201"
```


Where the moon_config.git repository would contain the following Dockerfile in the 'logtash' folder:
```
FROM logstash
COPY logstash.conf /
RUN chmod a+rwx /logstash.conf
RUN logstash-plugin install logstash-output-slack
CMD ["-f", "/logstash.conf"]
```

And also this kind of logstash.conf file:
```
input {
  gelf {
    port => 12201
  }
}
output {
  elasticsearch { hosts => ["elasticsearch:9200"] }
  stdout { codec => rubydebug }
  slack { url => "https://hooks.slack.com/services/XXX/XXX/xxxxxxx" }
}
```
