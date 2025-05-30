const { notarize } = require('@electron/notarize');

exports.default = async function notarizing(context) {
  const { electronPlatformName, appOutDir } = context;
  
  if (electronPlatformName !== 'darwin') {
    console.log('Skipping notarization - not building for macOS');
    return;
  }

  // Check if we have the required environment variables for notarization
  const appleId = process.env.APPLE_ID;
  const appleIdPassword = process.env.APPLE_ID_PASSWORD;
  const teamId = process.env.APPLE_TEAM_ID;
  
  if (!appleId || !appleIdPassword || !teamId) {
    console.log('⚠️  Skipping notarization - Apple credentials not provided');
    console.log('   For distribution, set these environment variables:');
    console.log('   - APPLE_ID: Your Apple ID email');
    console.log('   - APPLE_ID_PASSWORD: App-specific password');
    console.log('   - APPLE_TEAM_ID: Your Apple Developer Team ID');
    return;
  }

  const appName = context.packager.appInfo.productFilename;
  const appPath = `${appOutDir}/${appName}.app`;

  console.log(`🍎 Notarizing app at: ${appPath}`);
  
  try {
    await notarize({
      appBundleId: 'com.theseusinsight.desktop',
      appPath: appPath,
      appleId: appleId,
      appleIdPassword: appleIdPassword,
      teamId: teamId,
    });
    
    console.log('✅ Notarization completed successfully');
  } catch (error) {
    console.error('❌ Notarization failed:', error);
    throw error;
  }
}; 