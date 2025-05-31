const builder = require('electron-builder');

async function buildUniversal() {
  console.log('🔄 Building Universal macOS App...');
  
  const config = {
    appId: 'com.theseusinsight.desktop',
    productName: 'Theseus Insight',
    directories: {
      output: 'dist'
    },
    asarUnpack: [],
    files: [
      '**/*',
      '!node_modules/*/{CHANGELOG.md,README.md,readme.md,example,examples,**/test/**}'
    ],
    extraResources: [
      {
        from: '../',
        to: 'app',
        filter: [
          'theseus_insight/**', 
          'theseus-ui/dist/**', 
          'config/**', 
          'run_theseus_insight.py', 
          'requirements.txt'
        ]
      },
      {
        from: 'env.template',
        to: '.env'
      }
    ],
    mac: {
      icon: 'icons/mac/icon.icns',
      hardenedRuntime: true,
      gatekeeperAssess: false,
      entitlements: 'build/entitlements.mac.plist',
      entitlementsInherit: 'build/entitlements.mac.plist',
      category: 'public.app-category.productivity',
      target: [
        {
          target: 'dmg',
          arch: ['universal']
        }
      ]
    },
    afterPack: null,
  };

  try {
    await builder.build({
      targets: builder.Platform.MAC.createTarget(),
      config: config,
      publish: 'never'
    });
    console.log('✅ Universal build completed successfully!');
  } catch (error) {
    console.error('❌ Universal build failed:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  buildUniversal();
}

module.exports = { buildUniversal };