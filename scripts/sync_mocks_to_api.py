"""
Export frontend mock case data to src/data/synthetic/cases.json.

Reads the TypeScript mock files, extracts JSON-like object literals via
a lightweight eval approach (the mock data is pure data — no logic needed).

Usage:
    cd payment-disputes
    python scripts/sync_mocks_to_api.py
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_SRC = os.path.join(ROOT, "src", "web", "src")
OUT_PATH = os.path.join(ROOT, "src", "data", "synthetic", "cases.json")


def main():
    # Use Vite's build to bundle the mocks into a single JS file we can eval with Node
    # Simpler: use node with a custom resolver script
    script = r"""
const { register } = require('node:module');
const { pathToFileURL } = require('node:url');

// Custom loader that appends .ts extension
register('./ts-loader.mjs', pathToFileURL(__filename));
"""
    # Simplest approach: write a tiny CJS node script that uses require + esbuild transform
    node_script = os.path.join(ROOT, "scripts", "_dump_cases.mjs")
    
    # Write a temporary Node ESM script that bundles with esbuild-like approach
    # Actually let's just use Vite's ssr build or a direct approach
    
    # Most reliable: use the Vite/esbuild toolchain already in the project
    vite_script = f"""
import {{ build }} from 'vite';
import {{ writeFileSync }} from 'node:fs';
import {{ resolve }} from 'node:path';

const root = {json.dumps(WEB_SRC.replace(os.sep, '/'))};

// Use Vite's internal esbuild to transform
import {{ transformWithEsbuild }} from 'vite';

// Actually simpler - just use esbuild directly
import {{ buildSync }} from 'esbuild';

const result = buildSync({{
  entryPoints: [resolve(root, 'mocks/cases.ts')],
  bundle: true,
  write: false,
  format: 'esm',
  platform: 'neutral',
  external: [],
}});

const code = result.outputFiles[0].text;
// Now eval it
const mod = await import('data:text/javascript,' + encodeURIComponent(code));
const cases = Object.values(mod.mockCases);
const outPath = {json.dumps(OUT_PATH.replace(os.sep, '/'))};
writeFileSync(outPath, JSON.stringify(cases, null, 2));
console.log('Wrote ' + cases.length + ' cases to ' + outPath);
"""
    # This is getting complicated. Let's just use esbuild CLI if available, 
    # or fall back to a simple approach: build a temp bundle.
    
    # Simplest possible: use esbuild (already installed as vite dep) to bundle the mocks
    esbuild_bin = os.path.join(ROOT, "src", "web", "node_modules", ".bin", "esbuild.cmd" if sys.platform == "win32" else "esbuild")
    
    if not os.path.exists(esbuild_bin):
        print(f"esbuild not found at {esbuild_bin}")
        sys.exit(1)
    
    # Bundle mocks/cases.ts into a single ESM file
    tmp_bundle = os.path.join(ROOT, "scripts", "_cases_bundle.mjs")
    entry = os.path.join(WEB_SRC, "mocks", "cases.ts")
    
    result = subprocess.run(
        [esbuild_bin, entry, "--bundle", "--format=esm", f"--outfile={tmp_bundle}", "--platform=neutral"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("esbuild failed:", result.stderr)
        sys.exit(1)
    
    # Now run a node script that imports the bundle and dumps JSON
    dump_script = os.path.join(ROOT, "scripts", "_dump_json.mjs")
    with open(dump_script, "w", encoding="utf-8") as f:
        f.write(f"""
import {{ mockCases }} from './_cases_bundle.mjs';
import {{ writeFileSync }} from 'node:fs';

const cases = Object.values(mockCases);
const outPath = {json.dumps(OUT_PATH.replace(os.sep, '/'))};
writeFileSync(outPath, JSON.stringify(cases, null, 2));
console.log('Wrote ' + cases.length + ' cases to ' + outPath);
""")
    
    result = subprocess.run(
        ["node", dump_script],
        capture_output=True, text=True
    )
    
    # Cleanup temp files
    for f in [tmp_bundle, dump_script]:
        if os.path.exists(f):
            os.remove(f)
    
    if result.returncode != 0:
        print("node failed:", result.stderr)
        sys.exit(1)
    
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
