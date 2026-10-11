const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function browser(saved, systemDark = false, blocked = false) {
  const events = {};
  const attributes = {};
  const button = {hidden:true, setAttribute:(key,value)=>attributes[key]=value, addEventListener:(key,fn)=>events[key]=fn};
  const root = {dataset:{}};
  const storage = {value:saved, getItem(){if(blocked)throw Error(); return this.value;}, setItem(key,value){if(blocked)throw Error(); this.value=value;}};
  const media = {matches:systemDark, addEventListener:(key,fn)=>events.system=fn};
  const document = {documentElement:root, addEventListener:(key,fn)=>events[key]=fn, getElementById:()=>button};
  const source = fs.existsSync(path.join(__dirname,'../django_project/static/js/theme.js')) ? fs.readFileSync(path.join(__dirname,'../django_project/static/js/theme.js'),'utf8') : '';
  vm.runInNewContext(source,{document,window:{localStorage:storage,matchMedia:()=>media}});
  events.DOMContentLoaded?.();
  return {root,storage,attributes,button,events};
}
test('restores an explicit preference before page content loads',()=>{
  const b=browser('light',true);assert.equal(b.root.dataset.theme,'light');assert.equal(b.attributes['aria-checked'],'false');
});
test('uses system appearance when there is no saved choice',()=>{
  const b=browser(null,true);assert.equal(b.root.dataset.theme,'dark');assert.equal(b.button.hidden,false);
});
test('toggle updates the theme, accessible state and persisted preference',()=>{
  const b=browser('light');b.events.click?.();assert.equal(b.root.dataset.theme,'dark');assert.equal(b.storage.value,'dark');assert.equal(b.attributes['aria-checked'],'true');b.events.click();assert.equal(b.storage.value,'light');
});
test('unavailable storage does not break the toggle',()=>{
  const b=browser(null,false,true);b.events.click?.();assert.equal(b.root.dataset.theme,'dark');
});
test('system changes apply only until the visitor makes a choice',()=>{
  const b=browser('invalid');b.events.system?.({matches:true});assert.equal(b.root.dataset.theme,'dark');b.events.click();b.events.system({matches:true});assert.equal(b.root.dataset.theme,'light');
});
