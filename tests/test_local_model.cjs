const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');

const html = fs.readFileSync('учебник.html', 'utf8');
const script = html.split('<script>', 2)[1].split('</script>', 1)[0];
const logic = script.split('const log=document.getElementById("log");', 1)[0];
const sandbox = {console};
vm.createContext(sandbox);
vm.runInContext(`${logic}\nglobalThis.searchForTest=search;globalThis.answerForTest=answerLine;`, sandbox);

const theses = sandbox.searchForTest('95 тезисов');
assert.ok(theses.evidence?.some(row => row.page === 63 && row.text.includes('Мартин Лютер') && row.text.includes('индульгенций')),
  '“95 тезисов” should resolve to the textbook passage about Luther in 1517');
assert.match(sandbox.answerForTest(theses.evidence[0], theses.kind, '95 тезисов'), /не приводит сами 95 тезисов/,
  'the answer must distinguish inferred topic from facts actually stated in the textbook');

const place = sandbox.searchForTest('в каком месте османы победили чешско-венгерское войско?');
assert.ok(place.evidence?.[0]?.text.includes('Мохаче'), 'paraphrased place question should find Mohács');

const date = sandbox.searchForTest('когда началась реформация в Германии?');
assert.ok(date.evidence?.[0]?.text.includes('1517'), 'date question should find 1517');

const timeline = sandbox.searchForTest('напиши всю хронологию по учебнику');
assert.equal(timeline.timeline?.length, 42, 'full timeline should return 42 supported entries');

const unknown = sandbox.searchForTest('что такое квантовая механика?');
assert.equal(unknown.hits.length, 0, 'unrelated out-of-curriculum query should abstain');
assert.equal(unknown.evidence, undefined, 'unrelated out-of-curriculum query should not invent evidence');

console.log('PASS local concept expansion for “95 тезисов”');
console.log('PASS sourced place/date/timeline retrieval');
console.log('PASS abstention for unsupported topic');
