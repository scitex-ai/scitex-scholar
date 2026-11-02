// Runs the actual shipped helper without a browser, providers or app stores.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
const order = context.ScholarSearchOrder;
const entries = [
  {paper: {title:'Zulu', year:2020, citation_count:2, impact_factor:9}, index:0},
  {paper: {title:'Alpha', year:2024, citation_count:40, impact_factor:3}, index:1},
  {paper: {title:'Beta', year:2024, citation_count:40, impact_factor:0}, index:2},
  {paper: {title:'Unknown', year:null, citation_count:null, impact_factor:null}, index:3},
];
const original = JSON.stringify(entries);
const ids = mode => Array.from(order.sortEntries(entries,mode), e=>e.index);
assert.deepEqual(ids('citations-desc'),[1,2,0,3]);
assert.deepEqual(ids('citations-asc'),[0,1,2,3]);
assert.deepEqual(ids('impact-desc'),[0,1,2,3]);
assert.deepEqual(ids('impact-asc'),[2,1,0,3]);
assert.deepEqual(ids('year-desc'),[1,2,0,3]);
assert.deepEqual(ids('year-asc'),[0,1,2,3]);
assert.deepEqual(ids('title'),[1,2,3,0]);
assert.deepEqual(ids('relevance'),[0,1,2,3]);
assert.equal(JSON.stringify(entries),original);
for (const [field,prefix] of [['year','year'],['citations','citations'],['impact_factor','impact']]) {
  assert.equal(order.nextOrder('relevance',field),`${prefix}-desc`);
  assert.equal(order.nextOrder(`${prefix}-desc`,field),`${prefix}-asc`);
  assert.equal(order.nextOrder(`${prefix}-asc`,field),'relevance');
  assert.equal(order.direction(`${prefix}-desc`,field),'desc');
  assert.equal(order.direction(`${prefix}-asc`,field),'asc');
}
assert.equal(order.nextOrder('title','title'),'relevance');
assert.throws(()=>order.nextOrder('relevance','unknown'));
assert.throws(()=>order.sortEntries(entries,'unknown'));
const invalid = [null,undefined,'', ' ',true,NaN,Infinity,-1];
for (const value of invalid) {
 const rows=[{paper:{impact_factor:value},index:0},{paper:{impact_factor:0},index:1}];
 for (const direction of ['asc','desc'])assert.deepEqual(Array.from(order.sortEntries(rows,`impact-${direction}`),e=>e.index),[1,0]);
}
console.log('Loaded-result sorting, missing values, stable ties, cycles and input immutability passed');
