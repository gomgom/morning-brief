#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [, , inputArg, fontArg, outputArg] = process.argv;

if (!inputArg) {
  console.error("Usage: node inline-font-css.mjs <input.html> [font-css] [output.html]");
  process.exit(1);
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const skillDir = path.resolve(scriptDir, "..");
const inputPath = path.resolve(inputArg);
const fontPath = fontArg
  ? path.resolve(fontArg)
  : path.join(skillDir, "assets", "fonts", "fonts-embedded.css");
const outputPath = outputArg ? path.resolve(outputArg) : inputPath;

const html = fs.readFileSync(inputPath, "utf8");
const css = fs.readFileSync(fontPath, "utf8").trim();
const fontDir = path.dirname(fontPath);
const requiredLicenses = [
  "Fraunces-OFL.txt",
  "MaruBuri-OFL.txt",
  "NotoSerifKR-OFL.txt",
];

if (!html.includes("/* __EMBEDDED_FONT_CSS__ */")) {
  throw new Error("Input HTML is missing /* __EMBEDDED_FONT_CSS__ */.");
}
if (!/@font-face\s*\{/.test(css)) {
  throw new Error("Font CSS must contain at least one @font-face rule.");
}
if (!/data:font\/woff2;base64,/i.test(css)) {
  throw new Error("Font CSS must embed at least one WOFF2 data URI.");
}
if (/https?:\/\//i.test(css)) {
  throw new Error("Remote URLs are not allowed in embedded font CSS.");
}

const licenseSections = requiredLicenses.map((name) => {
  const licensePath = path.join(fontDir, name);
  if (!fs.existsSync(licensePath)) {
    throw new Error(`Required font license is missing: ${name}`);
  }
  const text = fs.readFileSync(licensePath, "utf8").replaceAll("*/", "* /").trim();
  return `===== ${name} =====\n${text}`;
});
const licenseHeader = `/*\nBundled font license notices\n\n${licenseSections.join("\n\n")}\n*/`;
const result = html.replace(
  "/* __EMBEDDED_FONT_CSS__ */",
  `${licenseHeader}\n${css}`,
);
fs.writeFileSync(outputPath, result, "utf8");
console.log(`Embedded font CSS into ${outputPath}`);
