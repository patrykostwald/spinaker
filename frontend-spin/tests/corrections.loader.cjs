const ts = require('typescript');
module.exports = function (source) {
  if (this.resourcePath.endsWith('.css')) return `const style=document.createElement('style');style.textContent=${JSON.stringify(source)};document.head.appendChild(style);`;
  return ts.transpileModule(source, { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  } }).outputText;
};
