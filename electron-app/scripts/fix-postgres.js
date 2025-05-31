const { execSync } = require("child_process");
const path = require("path");

module.exports = async (ctx) => {
  // Resolve the built .app directory using the product name
  const appName = ctx.packager.appInfo.productFilename || "Theseus Insight";
  const app = path.join(ctx.appOutDir, `${appName}.app`);

  const libDir = path.join(app, "Contents/Resources/app/postgres/darwin/lib");
  const binDir = path.join(app, "Contents/Resources/app/postgres/darwin/bin");
  const libpqPath = path.join(libDir, "libpq.5.dylib");

  // Ensure libpq itself uses an rpath-based ID
  execSync(`install_name_tool -id @rpath/libpq.5.dylib "${libpqPath}"`);

  // Get list of executable files under postgres/bin
  const binFiles = execSync(`find "${binDir}" -type f -perm +111`, {
    encoding: "utf8",
  })
    .trim()
    .split("\n");

  binFiles.forEach((file) => {
    // Inspect current library references to find any path containing libpq.5.dylib
    const deps = execSync(`otool -L "${file}"`, { encoding: "utf8" })
      .split("\n")
      .map((line) => line.trim().split(" ")[0])
      .filter((line) => line.includes("libpq.5.dylib") && !line.startsWith("@rpath"));

    deps.forEach((oldPath) => {
      try {
        execSync(`install_name_tool -change "${oldPath}" @rpath/libpq.5.dylib "${file}"`);
      } catch {
        // ignore if install_name_tool fails for a given path
      }
    });

    try {
      execSync(`install_name_tool -add_rpath @loader_path/../lib "${file}"`);
    } catch {
      // rpath may already exist; ignore errors
    }
  });
};