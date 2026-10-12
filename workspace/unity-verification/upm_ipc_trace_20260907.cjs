const fs = require('node:fs');
const net = require('node:net');
const { spawn } = require('node:child_process');

const [upm, traceFile, suffix = '20260907'] = process.argv.slice(2);
if (!upm || !traceFile) throw new Error('Expected UPM executable and trace file.');
const front = `Unity-UpmTrace-${suffix}`;
const back = `Unity-UpmBackend-${suffix}`;
const pipe = name => `\\\\.\\pipe\\${name}`;
const record = data => fs.appendFileSync(traceFile, JSON.stringify(data) + '\n');
const child = spawn(upm, ['-s', String(process.pid), '-ipc', '-ipc-path', back, '-l', '4'], {
  windowsHide: true,
  stdio: 'ignore',
});
const sockets = new Set();

function observe(socket, direction) {
  let pending = '';
  socket.on('data', data => {
    pending += data.toString('utf8');
    let end;
    while ((end = pending.indexOf('\f')) >= 0) {
      const raw = pending.slice(0, end);
      pending = pending.slice(end + 1);
      try {
        const message = JSON.parse(raw);
        const body = message.data || {};
        const headers = body.headers || {};
        const paths = Object.fromEntries(Object.entries(headers).filter(([key]) =>
          /^(x-project-path|x-editor-path|x-builtin-packages-path|x-dotnet-runtime-path|x-unity-version)$/i.test(key)));
        record({ direction, type: message.type, data_keys: Object.keys(body),
          header_keys: Object.keys(headers), paths, status: body.status });
      } catch (error) {
        record({ direction, parse_error: error.name, byte_length: raw.length });
      }
    }
  });
}

const server = net.createServer(client => {
  const upstream = net.connect(pipe(back));
  sockets.add(client);
  sockets.add(upstream);
  observe(client, 'editor_to_upm');
  observe(upstream, 'upm_to_editor');
  client.pipe(upstream).pipe(client);
  for (const socket of [client, upstream]) {
    socket.on('error', error => record({ connection_error: error.code }));
    socket.on('close', () => sockets.delete(socket));
  }
});
server.listen(pipe(front), () => console.log(`Trace ready: -upmIpcPath UpmTrace-${suffix}`));
server.on('error', error => { console.error(error.message); finish(1); });

function finish(code) {
  for (const socket of sockets) socket.destroy();
  server.close();
  child.kill();
  process.exit(code);
}
setTimeout(() => finish(0), 180000);
process.on('SIGINT', () => finish(0));
process.on('SIGTERM', () => finish(0));
