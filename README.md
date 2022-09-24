# Teleword
* Publication date: 2022-05-27 

## Installation on the server

Let's make sure the linux machine is up-to-date.
```
sudo apt update && sudo apt upgrade -y
```
Installing useful packages
```
sudo apt install git openssh python3-venv
```
Let's generate sssh keys using the s4lv [ed25519](https://ru.wikipedia.org/wiki/EdDSA) method
```
ssh-keygen -t ed25519 
```
![img.png](config/ssh-keygen.png)

Setting up access to sssh keys
```
cd /root/.ssh/
touch config
```
```
nano config
```
```
Host <SSH NAME>
 HostName github.com
 IdentityFile ~/.ssh/<KEY>
 IdentitiesOnly yes
```
![img.png](config/ssh-config.png)


Copy the public key and transfer it to github
```
 cat <KEY>.pub
```
![img.png](config/ssh_github_addind.png)

![img.png](config/ssh-key-added.png)

```
cd #
git clone git@<SSH NAME>:vinter-man/teleword.git
```
> yes

![img.png](config/git-establish.png)


```
nano teleword/config/config.py
```
> Do not forget to change the config file for yourself.

Let's move on to setting up a virtual environment
```
apt-get install make libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev
curl https://raw.github.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
. ~/.bashrc
pyenv install 3.10.2
pyenv rehash
sudo apt install python3-venv
cd teleword
pyenv local 3.10.2
python -m venv <VENV NAME>
source <VENV NAME>/bin/activate
pip install -r requirements.txt
```
![img.png](config/py-start.png)
After a successful launch, you can exit

Now you have to decide how it will be most convenient for you to launch your bot for continuous operation.

### Screen
```
sudo apt install screen
screen -S teleword
python teleword.py
```


### Systemd

Let's create and run the service
```
sudo nano /etc/systemd/system/teleword.service
```
```
[Unit]
Description=Teleword
After=network.target

[Service]
Type=simple
User=root
ProtectHome=false
WorkingDirectory=/root/teleword/teleword/
ExecStart=/root/teleword/teleword/teleword/bin/python teleword.py
Restart=on-failure
RestartSec=10
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
```
After saving the service file, let's start Teleword
```
sudo systemctl daemon-reload
sudo systemctl enable teleword
sudo systemctl restart teleword
sudo systemctl status teleword
```
View logs in real time
```
journalctl -u teleword -f
```

### Docker
Let's install the necessary
```
sudo apt install apt-transport-https
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt install docker
```
```
cd teleword
docker build -t teleword .
docker run -d -p  26256:80  teleword
docker ps
```
View logs in real time
```
docker logs <teleword docker ps CONTAINER ID> -f --tail 10
```
