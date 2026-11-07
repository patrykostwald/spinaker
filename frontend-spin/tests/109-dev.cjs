const http = require('node:http');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { response } = require('./109-fixture.cjs');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req, res) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(response(new URL(req.url, 'http://localhost').pathname.replace(/\/+$/, '/') ))); });
server.listen(3109, '127.0.0.1', () => {
  const child = spawn(process.execPath, [require.resolve('next/dist/bin/next'), 'dev', root, '-p', '3009', '-H', '127.0.0.1'], { cwd: root, stdio: 'inherit', env: { ...process.env,
    NODE_OPTIONS: `--require="${path.join(__dirname, '109-preload.cjs').replaceAll('\\', '/')}"`, NEXT_TELEMETRY_DISABLED: '1',
    NEXT_FONT_GOOGLE_MOCKED_RESPONSES: path.join(__dirname, '109-fonts.cjs'),
    THREADS_ENABLED: 'false', NEXT_PUBLIC_THREADS_ENABLED: 'false', NEXT_PUBLIC_ACCOUNTS_ENABLED: 'true',
    NEXT_PUBLIC_API_URL: 'http://127.0.0.1:3109', API_INTERNAL_URL: 'http://127.0.0.1:3109', NEXT_PUBLIC_PLAUSIBLE_DOMAIN: '',
  } });
  child.on('exit', code => { server.close(); process.exitCode = code; });
});
