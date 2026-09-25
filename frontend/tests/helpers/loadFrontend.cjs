const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const { parse, compileScript } = require('vue/compiler-sfc');

const frontendRoot = path.resolve(__dirname, '../..');
const sources = new Map();

// Компилируем настоящие модули; подменяем только переданные внешние границы.
// Кэш экземпляров отдельный для каждой проверки, чтобы состояния не утекали между тестами.
function load(relativePath, imports = {}, globals = {}) {
  const modules = new Map();
  function loadModule(modulePath) {
    if (modules.has(modulePath)) return modules.get(modulePath);
    if (!sources.has(modulePath)) {
      let source = readFileSync(path.join(frontendRoot, modulePath), 'utf8');
      if (modulePath.endsWith('.vue')) {
        source = compileScript(parse(source).descriptor, { id: modulePath }).content;
      }
      sources.set(modulePath, ts.transpileModule(source, {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
      }).outputText);
    }
    const exports = {};
    modules.set(modulePath, exports);
    vm.runInNewContext(sources.get(modulePath), {
      exports, Error, Blob, FormData, Headers, Response, URLSearchParams, DOMException, performance, setTimeout, clearTimeout,
      console: { log() {}, warn() {}, error() {} }, ...globals,
      require(name) {
        if (name in imports) return imports[name];
        if (name.startsWith('@/')) {
          if (name.endsWith('.vue')) return {};
          return loadModule(name.replace('@/', 'src/') + '.ts');
        }
        if (['vue', 'zod'].includes(name)) return require(name);
        assert.fail('Unexpected import: ' + name);
      },
    });
    return exports;
  }
  return loadModule(relativePath);
}

module.exports = { load };
