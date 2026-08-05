import { readdirSync, readFileSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const workspaceRoot = resolve(process.cwd());

function sourceFiles(path: string): string[] {
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    const child = join(path, entry.name);
    if (entry.isDirectory()) return sourceFiles(child);
    return [".ts", ".tsx"].includes(extname(entry.name)) ? [child] : [];
  });
}

describe("shared policy workspace neutrality", () => {
  it("keeps fixture semantics out of generic workspace source", () => {
    const sharedFiles = [
      resolve(workspaceRoot, "components/project-shell.tsx"),
      ...sourceFiles(resolve(workspaceRoot, "features")),
      ...sourceFiles(resolve(workspaceRoot, "app/projects")),
      ...sourceFiles(resolve(workspaceRoot, "app/reports")),
      ...sourceFiles(resolve(workspaceRoot, "app/runs")),
      ...sourceFiles(resolve(workspaceRoot, "app/scenario-results")),
      resolve(workspaceRoot, "lib/compilation-presentation.ts"),
      resolve(workspaceRoot, "lib/document-presentation.ts"),
      resolve(workspaceRoot, "lib/operations.ts"),
      resolve(workspaceRoot, "lib/run-presentation.ts"),
    ];
    const forbidden = ["northstar", "refund", "appointment", "issue_refund", "acme"];

    const violations = sharedFiles.flatMap((path) => {
      const contents = readFileSync(path, "utf8").toLocaleLowerCase();
      return forbidden
        .filter((term) => contents.includes(term))
        .map((term) => `${path.slice(workspaceRoot.length + 1)}: ${term}`);
    });

    expect(violations).toEqual([]);
  });
});
