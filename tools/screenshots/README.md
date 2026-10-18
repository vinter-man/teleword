# README screenshots

The screenshots in `img/readme_images` that show the current bot are rendered with
[Remotion](https://www.remotion.dev/) from real data:

1. `capture.py` runs the real dispatcher, handlers, services and a SQLite database with a fake
   Telegram network layer and saves what the bot sent, its log lines and `sqlite3` output to
   `public/data/` (part-of-speech lookups go to the real dictionaryapi.dev).
2. `server/` holds output copied from the production server.
3. `render.mjs` draws them as Telegram Desktop (night theme) and terminal windows.

```
npm install
npm run capture   # needs uv and sqlite3
npm run render    # or: node render.mjs lesson1 lesson2
```
