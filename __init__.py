import os
import time
import git
import shutil
import subprocess
import yaml
import pathlib
import logging
logging.basicConfig(level=logging.INFO)

class Dispatcher():
    '''Monitors config file and commits in remote repositories'''
    def __init__(self, config_file, apps_folder):
        logging.info("Creating new dispatcher in {f}".format(f=apps_folder))
        self.apps_folder = apps_folder
        self.config_file = config_file
        os.makedirs(apps_folder, exist_ok=True)
    def start(self):
        logging.info("Starting Dispatcher")
        self.remove_dangling()
        apps_info = yaml.load(open(self.config_file))['apps']
        if apps_info == None: apps_info = []
        self.current_bank = AppBank(apps_info, self.apps_folder)
        for app in self.current_bank:
            app.start()
        self.loop()
    def remove_dangling(self):
        logging.info("Checking for dangling containers and folders")
        for entry in os.scandir(self.apps_folder):
            if entry.is_dir():
                folder = Folder(entry.path)
                container = Container(folder)
                container.kill()
                folder.delete()
    def update_from_config(self):
        apps_info = yaml.load(open(self.config_file))['apps']
        if apps_info == None: apps_info = []
        new_bank = AppBank(apps_info, self.apps_folder)
        for app in self.current_bank:
            if app not in new_bank:
                app.kill()
        for app in new_bank:
            if app not in self.current_bank:
                app.start()
        self.current_bank = new_bank
    def update_from_commits(self):
        for app in self.current_bank:
            if not app.remote.uptodate():
                app.restart()
    def loop(self):
        logging.info("Starting to watch for updates")
        while True:
            self.update_from_config()
            self.update_from_commits()
            time.sleep(30)

class AppBank():
    '''Lists the apps with some syntactic sugar'''
    def __init__(self, apps_info, apps_folder):
        self.apps = []
        for name in apps_info:
            self.apps.append(App(
                    os.path.join(apps_folder, name), 
                    apps_info[name]['url'], 
                    apps_info[name]['branch'],
                    apps_info[name]['compose'],
                    ))
    def __iter__(self):
       for app in self.apps:
          yield app
    def __contains__(self, item):
        for running_app in self.apps:
            if item == running_app:
                return True
        return False
        
class App():
    '''Centralizes the remote repository local folder and container information'''
    def __init__(self, path, url, branch, compose):
        self.folder = Folder(path)
        self.remote = Remote(self.folder, url, branch)
        self.container = Container(self.folder)
        self.compose = compose
        self.hash = hash(
                self.folder.path +
                self.remote.url +
                self.remote.branch +
                yaml.dump(self.compose)
                )
    def start(self):
        logging.info("Starting an app in {f}".format(f=self.folder.path))
        self.remote.clone()
        self.folder.overwrite('docker-compose.yml', yaml.dump(self.compose))
        self.folder.overwrite('docker-compose.override.yml', yaml.dump(self.compose))
        self.container.start()
        logging.info("App started")
    def kill(self):
        logging.info("Killing the app from {f}".format(f=self.folder.path))
        self.container.kill()
        self.folder.delete()
        logging.info("App killed")
    def restart(self):
        self.kill()
        self.start()
    def __eq__(self, other): # Override the == operator
        if isinstance(other, self.__class__):
            return self.hash == other.hash
        return NotImplemented
    def __ne__(self, other): # Override the != operator
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

class Folder():
    '''Manages the local folder'''
    def __init__(self, path):
        self.path = path
    def overwrite(self, filename, content):
        logging.info("Overwriting {f}".format(f=filename))
        with open(os.path.join(self.path, filename), 'w') as f:
            f.write(content)
    def delete(self):
        logging.info("Deleting {f}".format(f=self.path))
        shutil.rmtree(self.path)

class Remote():
    '''Manages the remote repository'''
    def __init__(self, folder, url, branch):
        self.folder = folder
        self.url = url
        self.branch = branch
    def clone(self):
        logging.info("Cloning {u}#{b} into {f}".format(u=self.url, b=self.branch, f=self.folder.path))
        os.chdir(str(pathlib.Path(self.folder.path).parent))
        command = ["git", "clone", "-b", self.branch, self.url, self.folder.path]
        subprocess.run(command)
        logging.info("Waiting for cloning to finish")
        # The run command finishes but the files are not always created by git yet 
        for _ in range(300): 
            try:
                if self.uptodate():
                    logging.info("Cloning finished")
                    break
            except(git.exc.NoSuchPathError):
                pass
            time.sleep(2)
        else:
            raise TimeoutError("Moon killed - Cloning process timed out for {u}#{b} into {f}".format(u=self.url, b=self.branch, f=self.folder.path))
    def uptodate(self):
        repo = git.Repo(self.folder.path)
        origin = repo.remotes.origin
        fetch_result = origin.fetch()[0]
        return fetch_result.flags == 4 # 4 means UPTODATE

class Container():
    '''Manages the Docker container(s)'''
    def __init__(self, folder):
        self.folder = folder
    def start(self):
        logging.info("Running docker-compose up on {f}".format(f=self.folder.path))
        os.chdir(self.folder.path)
        subprocess.Popen(["docker-compose", "up", "--build", "-d"])
    def kill(self):
        logging.info("Running docker-compose stop/rm on {f}".format(f=self.folder.path))
        os.chdir(self.folder.path)
        subprocess.run(["docker-compose", "stop"])
        subprocess.run(["docker-compose", "rm", "-f"])

if __name__ == "__main__":
    config_file = '/var/moon/configuration.yml'
    apps_folder = '/var/moon/repository/'
    log_folder = '/var/moon/log'
    try:
        dispatcher = Dispatcher(config_file, apps_folder)
        dispatcher.start()
    except Exception:
                logging.exception("Uncaught exception:")
