# Teleword
* Publication date: 2022-05-27 

## Installation on the server

Let's make sure the linux machine is up-to-date.
```
sudo apt update && sudo apt upgrade -y
```
Installing useful packages
```
sudo apt install git openssh
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
Host <NAME>
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

