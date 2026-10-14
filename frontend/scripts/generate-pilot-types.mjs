import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const spec = JSON.parse(
  readFileSync(resolve(root, "docs/adaptive-gamified-learning/openapi-pilot-v1.json"), "utf8"),
);
const schemas = spec.components.schemas;

function named(ref) {
  return ref.split("/").at(-1);
}

function typescriptType(schema) {
  if (!schema) return "unknown";
  if (schema.$ref) return named(schema.$ref);
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(" | ");
  if (schema.anyOf) {
    const parts = [...new Set(schema.anyOf.map((part) => typescriptType(part)))];
    return parts.length > 1 ? parts.join(" | ") : parts[0];
  }
  if (schema.type === "array") {
    const item = typescriptType(schema.items);
    return item.includes("|") ? `(${item})[]` : `${item}[]`;
  }
  if (schema.type === "object" && schema.additionalProperties) {
    return `Record<string, ${typescriptType(schema.additionalProperties)}>`;
  }
  if (schema.type === "object") return "Record<string, unknown>";
  if (schema.type === "null") return "null";
  if (schema.type === "integer" || schema.type === "number") return "number";
  if (schema.type === "boolean") return "boolean";
  if (schema.type === "string") return "string";
  return "unknown";
}

const blocks = Object.keys(schemas)
  .sort()
  .map((name) => {
    const schema = schemas[name];
    const required = new Set(schema.required ?? []);
    const fields = Object.entries(schema.properties ?? {}).map(([key, property]) => {
      const optional = required.has(key) ? "" : "?";
      return `  ${key}${optional}: ${typescriptType(property)};`;
    });
    return `export interface ${name} {\n${fields.join("\n")}\n}`;
  });

const output = `/** Generated from docs/adaptive-gamified-learning/openapi-pilot-v1.json. Do not edit. */\n\n${blocks.join("\n\n")}\n`;
writeFileSync(
  resolve(root, "frontend/src/features/gamification/api/generated.ts"),
  output,
);
