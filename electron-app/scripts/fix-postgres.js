const { execSync } = require("child_process");
const path = require("path");

module.exports = async (ctx) => {
  // Resolve the built .app directory using the product name
  const appName = ctx.packager.appInfo.productFilename || "Theseus Insight";
  const app = path.join(ctx.appOutDir, `${appName}.app`);

  const libDir = path.join(app, "Contents/Resources/app/postgres/darwin/lib");
  const binDir = path.join(app, "Contents/Resources/app/postgres/darwin/bin");
  const libpqPath = path.join(libDir, "libpq.5.dylib");

  // Update library ID for libpq
  execSync(`install_name_tool -id @rpath/libpq.5.dylib "${libpqPath}"`);

  // Update binaries to reference libpq using a relative path
  const binFiles = execSync(`find "${binDir}" -type f -perm +111`, { encoding: "utf8" })
    .trim()
    .split("\n");

  binFiles.forEach((file) => {
    execSync(`install_name_tool -change "${libpqPath}" @rpath/libpq.5.dylib "${file}"`);
    try {
      execSync(`install_name_tool -add_rpath @loader_path/../lib "${file}"`);
    } catch {
      // rpath may already exist; ignore errors
    }
  });
};