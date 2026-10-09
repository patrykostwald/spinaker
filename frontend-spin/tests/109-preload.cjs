// Offline launcher preload: nie czyta .env i nie pozwala na połączenia poza loopback.
const Module = require('node:module');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const load = Module._load;
Module._load = function(id, parent, main) {
  const value = load.apply(this, arguments);
  if (id.includes('fetch-font-file')) return { fetchFontFile: async url => require('node:fs').readFileSync(url) };
  if (id === '@next/env') return { ...value, loadEnvConfig: () => ({ combinedEnv: process.env, parsedEnv: {}, loadedEnvFiles: [] }) };
  if (id.endsWith('next.config.js')) return { ...value, webpack(config) {
    config.resolve.alias['@spin-clinic/ui'] = path.join(root, 'packages/ui/src');
    return config;
  } };
  return value;
};
const net = require('node:net');
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function(...args) {
  const normalized = net._normalizeArgs(args)[0];
  if (normalized.host && !['localhost','127.0.0.1','::1'].includes(normalized.host)) throw new Error('109: blocked non-local connection');
  return connect.apply(this, args);
};
