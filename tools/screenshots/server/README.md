`docker-start.json` is the unedited output of these commands on the production server
(`/srv/teleword`), captured right after a deploy:

```
docker compose build --quiet
docker compose up -d
docker compose ps
docker compose logs bot --tail 3
```
