// Renders the README screenshots from the data written by capture.py.
//   npm run capture && npm run render
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const output = path.join(root, "img/readme_images");
const raw = path.join(here, ".cache/raw");
mkdirSync(raw, { recursive: true });

// name -> composition and width (close to the original screenshots); the height is cropped to content.
const SHOTS = {
  "first-steps-front": ["Chat", 660],
  "first-steps-back": ["Terminal", 1310],
  "first-steps-back2": ["Terminal", 1100],
  addlogs: ["Terminal", 1150],
  addsql: ["Terminal", 1400],
  lesson1: ["Chat", 560],
  lesson2: ["Chat", 560],
  "statistic-front": ["Chat", 560],
  "statistic-back": ["Terminal", 1150],
  "data-cmd": ["Chat", 620],
  "change-cmd": ["Chat", 520],
  "api-request": ["Chat", 600],
  "api-admin": ["Chat", 600],
  "api-doc": ["Chat", 680],
  "docker-start": ["Terminal", 1000],
};

const only = process.argv.slice(2);
const serveUrl = await bundle({ entryPoint: path.join(here, "src/index.ts") });

for (const [name, [id, width]] of Object.entries(SHOTS)) {
  if (only.length && !only.includes(name)) continue;
  // server/ holds output copied from the production server (see the README there); the rest comes from capture.py.
  const source = [path.join(here, "public/data", `${name}.json`), path.join(here, "server", `${name}.json`)].find(existsSync);
  const data = JSON.parse(readFileSync(source, "utf8"));
  const inputProps = { ...data, width };
  const composition = await selectComposition({ serveUrl, id, inputProps });
  const file = path.join(raw, `${name}.png`);
  await renderStill({ composition, serveUrl, output: file, inputProps });
  const ext = name.startsWith("add") ? "jpg" : "png"; // keep the file names the README already uses
  execFileSync(path.join(root, ".venv/bin/python"), [
    path.join(here, "crop.py"),
    file,
    path.join(output, `${name}.${ext}`),
  ]);
  console.log("rendered", name);
}
