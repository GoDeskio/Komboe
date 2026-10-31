// Resolve the git tag (or commit) a Komboe client build is made from, for the "Source code" link.
const { execSync } = require("child_process");

module.exports = function komboeSourceRef() {
  if (process.env.KOMBOE_SOURCE_REF) {
    return process.env.KOMBOE_SOURCE_REF;
  }
  const run = (cmd) => {
    try {
      return execSync(cmd, { cwd: __dirname, stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    } catch {
      return "";
    }
  };
  return run("git describe --tags --exact-match HEAD") || run("git rev-parse HEAD") || "main";
};
