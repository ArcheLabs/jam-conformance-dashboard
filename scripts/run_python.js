const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('Usage: node scripts/run_python.js <script.py> [...args]');
  process.exit(1);
}

function windowsPythonDirs(root) {
  if (!root) return [];
  const pythonRoot = path.join(root, 'Programs', 'Python');
  if (!fs.existsSync(pythonRoot)) return [];

  return fs.readdirSync(pythonRoot)
    .filter(name => /^Python3\d+$/i.test(name))
    .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }))
    .map(name => path.join(pythonRoot, name, 'python.exe'));
}

function candidates() {
  const values = [];
  if (process.env.PYTHON) values.push(process.env.PYTHON);

  values.push(...windowsPythonDirs(process.env.LOCALAPPDATA));
  values.push(...windowsPythonDirs(process.env.ProgramFiles));
  values.push(...windowsPythonDirs(process.env['ProgramFiles(x86)']));

  values.push('python3', 'python');
  return [...new Set(values.filter(Boolean))];
}

function isPython3(command) {
  const result = spawnSync(command, ['-c', 'import sys; print(sys.version_info[0])'], {
    encoding: 'utf8',
  });

  return result.status === 0 && result.stdout.trim() === '3';
}

const python = candidates().find(isPython3);

if (!python) {
  console.error('Python 3 was not found. Install Python 3 or set PYTHON to its executable path.');
  process.exit(1);
}

const result = spawnSync(python, args, {
  stdio: 'inherit',
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
