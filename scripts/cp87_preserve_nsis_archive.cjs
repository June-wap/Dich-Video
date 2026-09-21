'use strict';

// Loaded only by the CP8.7 repair build. electron-builder deletes the
// completed app-*.nsis.7z after makensis consumes it; preserve an exact copy
// immediately after archive creation and before NSIS compilation.
const fs = require('node:fs');
const path = require('node:path');
const { NsisTarget } = require('app-builder-lib/out/targets/nsis/NsisTarget');

const original = NsisTarget.prototype.buildAppPackage;
NsisTarget.prototype.buildAppPackage = async function patchedBuildAppPackage(...args) {
  const result = await original.apply(this, args);
  const evidenceDir = process.env.CP87_NSIS_ARCHIVE_EVIDENCE_DIR;
  if (evidenceDir && result?.path) {
    fs.mkdirSync(evidenceDir, { recursive: true });
    const destination = path.join(evidenceDir, path.basename(result.path));
    fs.copyFileSync(result.path, destination);
    const hash = await new Promise((resolve, reject) => {
      const digest = require('node:crypto').createHash('sha256');
      const stream = fs.createReadStream(destination);
      stream.on('data', (chunk) => digest.update(chunk));
      stream.on('error', reject);
      stream.on('end', () => resolve(digest.digest('hex')));
    });
    fs.writeFileSync(`${destination}.sha256`, `${hash}\n`);
    process.stderr.write(`CP87 preserved completed NSIS archive: ${destination}\n`);
  }
  return result;
};
