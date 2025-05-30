const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

exports.default = async function(context) {
  console.log('--- Starting afterPack script for PostgreSQL macOS dylib fixing ---');
  console.log('🔧 Running afterPack hook...');
  
  const { electronPlatformName, appOutDir } = context;
  
  if (electronPlatformName !== 'darwin') {
    console.log('⏭️  Skipping PostgreSQL path fixes (not macOS)');
    return;
  }
  
  console.log('🔧 Fixing PostgreSQL paths for distribution...');
  
  // Find the app bundle
  const appName = context.packager.config.productName || context.packager.config.name;
  const appBundle = path.join(appOutDir, `${appName}.app`);
  
  if (!fs.existsSync(appBundle)) {
    console.log('❌ App bundle not found, skipping PostgreSQL fixes');
    return;
  }
  
  // With asar enabled, PostgreSQL binaries are in extraResources
  const postgresDir = path.join(appBundle, 'Contents/Resources/app/postgres/darwin');
  const binDir = path.join(postgresDir, 'bin');
  const libDir = path.join(postgresDir, 'lib');
  
  if (!fs.existsSync(binDir) || !fs.existsSync(libDir)) {
    console.log('📁 PostgreSQL directories not found, skipping path fixes');
    console.log(`   Looked for: ${binDir}`);
    console.log(`   Looked for: ${libDir}`);
    return;
  }
  
  console.log('📁 Found PostgreSQL binaries, fixing hardcoded paths...');
  
  // Function to fix a single binary
  function fixBinary(binaryPath) {
    const binaryName = path.basename(binaryPath);
    
    try {
      // Get current library dependencies with hardcoded paths
      const otoolOutput = execSync(`otool -L "${binaryPath}"`, { encoding: 'utf8' });
      const lines = otoolOutput.split('\n');
      
      let hasChanges = false;
      
      for (const line of lines) {
        const trimmedLine = line.trim();
        
        // Skip the binary itself and system libraries
        if (trimmedLine === '' || 
            trimmedLine.startsWith(binaryPath) || 
            trimmedLine.includes('(compatibility version') ||
            trimmedLine.startsWith('/System/') ||
            trimmedLine.startsWith('/usr/lib/') ||
            trimmedLine.startsWith('@')) {
          continue;
        }
        
        // Look for ANY hardcoded paths that contain our project or absolute paths to postgres
        const pathMatch = trimmedLine.match(/^(\/[^\s]+\.dylib)/);
        if (pathMatch) {
          const libraryPath = pathMatch[1];
          
          // Check if it's a path we need to fix (any absolute path to postgres libraries)
          if (libraryPath.includes('postgres') || 
              libraryPath.includes('TheseusInsight') ||
              libraryPath.includes('/Users/')) {
            
            // Extract the library name from the path
            const libName = path.basename(libraryPath);
            const newPath = `@loader_path/../lib/${libName}`;
            
            console.log(`  🔄 ${binaryName}: Fixing ${libName}`);
            console.log(`    Old: ${libraryPath}`);
            console.log(`    New: ${newPath}`);
            
            try {
              console.log(`    Executing: install_name_tool -change "${libraryPath}" "${newPath}" "${binaryPath}"`);
              execSync(`install_name_tool -change "${libraryPath}" "${newPath}" "${binaryPath}"`, { stdio: 'pipe' });
              hasChanges = true;
            } catch (error) {
              console.log(`    ⚠️  Warning: Could not fix ${libName} in ${binaryName}: ${error.message}`);
            }
          }
        }
      }
      
      if (hasChanges) {
        console.log(`  ✅ ${binaryName}: Fixed library paths`);
      }
      
    } catch (error) {
      console.log(`  ⚠️  Warning: Could not process ${binaryName}: ${error.message}`);
    }
  }
  
  // Function to fix library IDs
  function fixLibraryId(libPath) {
    const libName = path.basename(libPath);
    const newId = `@loader_path/${libName}`;
    
    try {
      console.log(`  🔄 Setting library ID for ${libName}`);
      console.log(`    Executing: install_name_tool -id "${newId}" "${libPath}"`);
      execSync(`install_name_tool -id "${newId}" "${libPath}"`, { stdio: 'pipe' });
      console.log(`  ✅ ${libName}: Library ID updated`);
    } catch (error) {
      console.log(`  ⚠️  Warning: Could not set library ID for ${libName}: ${error.message}`);
    }
  }
  
  // Process all binaries in bin/
  try {
    const binFiles = fs.readdirSync(binDir);
    console.log(`📋 Processing ${binFiles.length} binaries...`);
    
    for (const file of binFiles) {
      const filePath = path.join(binDir, file);
      const stats = fs.statSync(filePath);
      
      if (stats.isFile() && (stats.mode & parseInt('111', 8))) { // Executable
        fixBinary(filePath);
      }
    }
  } catch (error) {
    console.log(`❌ Error processing binaries: ${error.message}`);
  }
  
  // Process all libraries in lib/
  try {
    const libFiles = fs.readdirSync(libDir);
    console.log(`📋 Processing ${libFiles.length} libraries...`);
    
    for (const file of libFiles) {
      if (file.endsWith('.dylib')) {
        const libPath = path.join(libDir, file);
        
        // Fix the library's own ID
        fixLibraryId(libPath);
        
        // Fix any dependencies the library has
        fixBinary(libPath);
      }
    }
  } catch (error) {
    console.log(`❌ Error processing libraries: ${error.message}`);
  }
  
  // Enhanced verification with more detailed output
  console.log('🔍 Verifying fixes for key binaries...');
  const keyBinaries = ['initdb', 'postgres', 'psql', 'pg_ctl'];
  let totalProblematicPaths = 0;

  for (const binaryName of keyBinaries) {
    const binaryPath = path.join(binDir, binaryName);
    if (!fs.existsSync(binaryPath)) {
      console.log(`  ⚠️  Skipping verification for ${binaryName}: File not found at ${binaryPath}`);
      continue;
    }

    console.log(`🔍 Verifying library paths for: ${binaryName}`);
    try {
      const otoolOutput = execSync(`otool -L "${binaryPath}"`, { encoding: 'utf8' });
      const lines = otoolOutput.split('\n');
      
      // First line is the binary itself, skip it.
      // Subsequent lines are dependencies.
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line === '' || line.includes('(compatibility version')) {
          continue;
        }

        const dependencyPath = line.split(' ')[0]; // Get the path part
        let status = '❓'; // Default to potentially problematic

        if (dependencyPath.startsWith('/usr/lib/') || dependencyPath.startsWith('/System/')) {
          status = '✅'; // System path
        } else if (dependencyPath.startsWith('@loader_path/')) {
          status = '✅'; // Loader relative
        } else if (dependencyPath.startsWith('@rpath/')) {
          status = '✅'; // Rpath based
        } else if (dependencyPath.includes('/Users/') ||
                   (dependencyPath.startsWith('/') && dependencyPath.includes('postgres/darwin/lib')) ||
                   (dependencyPath.startsWith('/') && dependencyPath.includes('postgres/darwin/bin'))) {
          status = '❌'; // Clearly problematic (build machine path or absolute bundled path)
          totalProblematicPaths++;
        }
        console.log(`  ${status} ${dependencyPath}`);
      }
    } catch (error) {
      console.log(`  ⚠️  Error verifying ${binaryName}: ${error.message}`);
      totalProblematicPaths++; // Count error in verification as problematic
    }
  }

  if (totalProblematicPaths === 0) {
    console.log('✅ Overall Verification Passed: No problematic paths found in key binaries.');
  } else {
    console.log(`❌ Overall Verification Warning: Found ${totalProblematicPaths} problematic path(s) across key binaries.`);
  }
  
  console.log('🎉 PostgreSQL path fixing completed');
  console.log('--- Finished afterPack script for PostgreSQL macOS dylib fixing ---');
}; 