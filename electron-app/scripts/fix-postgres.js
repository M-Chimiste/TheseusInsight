const { execSync } = require("child_process");
const path = require("path");

module.exports = async ctx => {
  const app = path.join(ctx.appOutDir, "Theseus Insight.app");
  const lib = path.join(app, "Contents/Resources/app/postgres/darwin/lib");
  const bin = path.join(app, "Contents/Resources/app/postgres/darwin/bin");

  execSync(`install_name_tool -id @rpath/libpq.5.dylib "${lib}/libpq.5.dylib"`);

  execSync(`find "${bin}" -type f -perm +111`, { encoding: "utf8" })
    .trim().split("\n").forEach(f => {
      execSync(`install_name_tool -change \
/Users/c/software_projects/TheseusInsight/electron-app/postgres/darwin/lib/libpq.5.dylib \
@rpath/libpq.5.dylib "${f}"`);
      try { execSync(`install_name_tool -add_rpath @loader_path/../lib "${f}"`); }
      catch {/* rpath already exists */}
    });
};