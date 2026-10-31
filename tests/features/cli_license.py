"""CLI bundles license texts into build/ (npm package and pkg binaries embed ./build/**)."""
import json, os, subprocess, sys
CLI = os.path.join(os.path.dirname(__file__), "../../clients/upstream/apps/cli")
if "--build" in sys.argv:
    subprocess.run(["npx", "webpack", "--config", "webpack.config.js"], cwd=CLI, check=True)
b = os.path.join(CLI, "build")
for f in ("LICENSE.txt", "LICENSE_GPL.txt", "THIRD-PARTY-NOTICES.md"):
    p = os.path.join(b, f)
    assert os.path.getsize(p) > 500, f
assert "GNU" in open(os.path.join(b, "LICENSE_GPL.txt")).read()
assert "./build/**/*" in json.load(open(os.path.join(CLI, "package.json")))["pkg"]["assets"]
print("CLI LICENSE PASS")
