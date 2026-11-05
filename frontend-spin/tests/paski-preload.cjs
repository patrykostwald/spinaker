// Podgląd offline: Next nie czyta .env, fonty i API są lokalnymi mockami.
const Module = require('node:module');
const original = Module._load;
Module._load = function(name, ...args) {
  const value = original.call(this, name, ...args);
  if (name === '@next/env') return { ...value, loadEnvConfig: () => ({ combinedEnv: process.env, parsedEnv: {}, loadedEnvFiles: [] }) };
  return value;
};
