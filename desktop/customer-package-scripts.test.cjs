const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

test('Kiem-Tra-Cai-Dat.bat correctly succeeds on complete package and fails when chatterbox missing', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'voca-verify-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));

  // Create mock package layout
  const vocaBasicDir = path.join(root, 'Voca Basic');
  const aiPackagesDir = path.join(vocaBasicDir, 'ai-packages');
  const resourcesDir = path.join(vocaBasicDir, 'resources');

  fs.mkdirSync(path.join(resourcesDir, 'bin'), { recursive: true });
  fs.mkdirSync(path.join(resourcesDir, 'backend'), { recursive: true });
  fs.mkdirSync(path.join(resourcesDir, 'frontend'), { recursive: true });
  fs.mkdirSync(path.join(aiPackagesDir, 'runtime-main'), { recursive: true });
  fs.mkdirSync(path.join(aiPackagesDir, 'runtime-chatterbox'), { recursive: true });
  fs.mkdirSync(path.join(aiPackagesDir, 'models', 'huggingface', 'hub'), { recursive: true });

  fs.writeFileSync(path.join(vocaBasicDir, 'Voca Basic.exe'), 'mock');
  fs.writeFileSync(path.join(vocaBasicDir, '7z.exe'), 'mock');
  fs.writeFileSync(path.join(vocaBasicDir, '7z.dll'), 'mock');
  fs.writeFileSync(path.join(resourcesDir, 'bin', 'ffmpeg.exe'), 'mock');
  fs.writeFileSync(path.join(resourcesDir, 'frontend', 'index.html'), 'mock');
  fs.writeFileSync(path.join(aiPackagesDir, 'runtime-main', 'python.exe'), 'mock');
  fs.writeFileSync(path.join(aiPackagesDir, 'runtime-chatterbox', 'python.exe'), 'mock');

  // Read actual template from assemble script or generated customer folder
  const assembleScript = fs.readFileSync(path.resolve(__dirname, '../scripts/assemble_customer_package.ps1'), 'utf8');
  const match = assembleScript.match(/\$kiemTraBat = @'([\s\S]*?)'@/);
  assert.ok(match, 'Failed to extract $kiemTraBat template from assemble_customer_package.ps1');

  const batContent = match[1].replace(/\r?\n/g, '\r\n');
  const batPath = path.join(vocaBasicDir, 'Kiem-Tra-Cai-Dat.bat');
  fs.writeFileSync(batPath, batContent, 'ascii');

  // Case 1: Complete package -> MUST exit code 0
  const passOutput = execFileSync('cmd.exe', ['/c', 'Kiem-Tra-Cai-Dat.bat'], {
    cwd: vocaBasicDir,
    input: '\n',
    encoding: 'utf8',
  });
  assert.match(passOutput, /\[OK\] ai-packages\\runtime-chatterbox\\python\.exe/);
  assert.match(passOutput, /TRANG THAI: SAN SANG SU DUNG/);

  // Case 2: Missing runtime-chatterbox python -> MUST exit code 1
  fs.rmSync(path.join(aiPackagesDir, 'runtime-chatterbox', 'python.exe'));
  assert.throws(
    () => {
      execFileSync('cmd.exe', ['/c', 'Kiem-Tra-Cai-Dat.bat'], {
        cwd: vocaBasicDir,
        input: '\n',
        encoding: 'utf8',
      });
    },
    (err) => {
      assert.equal(err.status, 1);
      assert.match(err.stdout, /\[LOI\] Khong tim thay ai-packages\\runtime-chatterbox\\python\.exe/);
      assert.match(err.stdout, /TRANG THAI: CHUA HOAN THIEN/);
      return true;
    }
  );
});

test('HUONG-DAN.txt documents correct production contract without false CPU fallback claim', () => {
  const assembleScript = fs.readFileSync(path.resolve(__dirname, '../scripts/assemble_customer_package.ps1'), 'utf8');
  const match = assembleScript.match(/\$huongDan = @'([\s\S]*?)'@/);
  assert.ok(match, 'Failed to extract $huongDan from assemble_customer_package.ps1');

  const doc = match[1];
  assert.doesNotMatch(
    doc,
    /Nếu không có GPU rời, phần mềm tự động sử dụng giọng VieNeu trên CPU/,
    'Must NOT claim automatic fallback from Chatterbox to VieNeu CPU'
  );
  assert.match(doc, /Chatterbox KHÔNG hỗ trợ chạy trên CPU/, 'Must document that Chatterbox does not run on CPU');
  assert.match(doc, /KHÔNG tự\s*động fallback/, 'Must document no silent provider fallback');
  assert.match(doc, /Bắt buộc trang bị card đồ họa rời NVIDIA hỗ trợ/, 'Must document NVIDIA CUDA requirement');
});
