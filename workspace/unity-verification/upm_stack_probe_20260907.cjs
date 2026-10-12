const fs = require('node:fs');
const Module = require('node:module');
const [app, ...args] = process.argv.slice(2);
const anchor = 'function handleErrorResponse(error,responseToolkit){';
const source = fs.readFileSync(app, 'utf8');
if (source.split(anchor).length !== 2) throw new Error('Expected one UPM error handler.');
// Add stack logging only in memory; installed Unity files remain unchanged.
const traced = source.replace(anchor, anchor + 'console.error("UPM_STACK_PROBE",error.stack);');
process.argv = [process.execPath, app, ...args];
const target = new Module(app, module);
target.filename = app;
target.paths = Module._nodeModulePaths(require('node:path').dirname(app));
setTimeout(() => process.exit(0), 120000);
target._compile(traced, app);
