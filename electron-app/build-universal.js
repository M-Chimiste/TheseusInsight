const builder = require('electron-builder');

async function buildUniversal() {
  console.log('🔄 Building Universal macOS App with custom postgres handling...');
  
  const config = {
    appId: 'com.theseusinsight.desktop',
    productName: 'Theseus Insight',
    directories: {
      output: 'dist'
    },
    // Unpack native PostgreSQL binaries so they are real files on disk
    asarUnpack: ["**/postgres/**/*"],
    files: [
      '**/*',
      '!node_modules/*/{CHANGELOG.md,README.md,readme.md,example,examples,**/test/**}'
    ],
    extraResources: [
      {
        from: 'postgres',
        to: 'app/postgres'
      },
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
      // Configure x64ArchFiles to handle postgres binaries that are the same across architectures
      target: [
        {
          target: 'dmg',
          arch: ['universal']
        }
      ]
    },
    // Patch postgres binaries after they're copied but before signing
    afterPack: './scripts/fix-postgres.js',
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