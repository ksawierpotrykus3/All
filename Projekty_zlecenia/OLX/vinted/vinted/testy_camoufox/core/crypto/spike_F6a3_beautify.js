// F6a.3: Beautify zdeobfuskowanego SDK Incognia
// Wejście:  k7v3q2_DEOBFUSCATED.js
// Wyjście: k7v3q2_BEAUTIFIED.js
const fs = require('fs');
const path = require('path');
const beautify = require('js-beautify');
const beautifyJs = beautify;

const INPUT = path.join(__dirname, 'k7v3q2_DEOBFUSCATED.js');
const OUTPUT = path.join(__dirname, 'k7v3q2_BEAUTIFIED.js');

const src = fs.readFileSync(INPUT, 'utf8');

// Opcje beautify: duże wcięcia, długie linie, ES6+
const opts = {
  indent_size: 2,
  indent_char: ' ',
  indent_with_tabs: false,
  eol: '\n',
  end_with_newline: true,
  preserve_newlines: true,
  max_preserve_newlines: 2,
  space_in_paren: false,
  space_in_empty_paren: false,
  jslint_happy: false,
  space_after_anon_function: true,
  space_after_named_function: false,
  brace_style: 'collapse,preserve-inline',
  unindent_chained_methods: false,
  break_chained_methods: false,
  keep_array_indentation: false,
  space_before_conditional: true,
  space_after_keywords: true,
  space_around_comparator: true,
  space_around_logical: true,
  space_assignment_equation: true,
  break_function: 'auto',
  arrow_space: true,
  space_after_comma: true,
  space_before_function_paren: false,
};

console.log(`Input:  ${src.length} bytes`);
const t0 = Date.now();
const out = beautifyJs(src, opts);
const t1 = Date.now();
console.log(`Output: ${out.length} bytes (took ${t1-t0}ms)`);

fs.writeFileSync(OUTPUT, out, 'utf8');
console.log(`Saved:  ${OUTPUT}`);
