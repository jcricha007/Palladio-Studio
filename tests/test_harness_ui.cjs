const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {withoutStartup}=require('./helpers/studio-source.cjs');

// Exercise the actual asynchronous UI suites against LF and Windows CRLF source.
// Checking only the loader's returned string would miss unintended startup fetches.
const root=path.resolve(__dirname,'..');
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'palladio-ui-lines-'));
try {
  const directory=path.join(temporary,'palladio','web');fs.mkdirSync(directory,{recursive:true});
  for(const [label,ending] of [['LF','\n'],['CRLF','\r\n']]) {
    for(const name of ['studio.js','site-picker.js','index.html']) {
      const source=fs.readFileSync(path.join(root,'palladio','web',name),'utf8').replace(/\r\n?/g,'\n');
      fs.writeFileSync(path.join(directory,name),source.replace(/\n/g,ending));
    }
    for(const suite of ['test_assembly_ui.cjs','test_agent_ui.cjs']) {
      const result=spawnSync(process.execPath,[path.join(__dirname,suite),temporary],{cwd:root,encoding:'utf8',timeout:30000});
      assert.ifError(result.error);
      assert.equal(result.status,0,`${suite} failed with ${label} source:\n${result.stdout}\n${result.stderr}`);
    }
  }
  assert.throws(()=>withoutStartup('render();\n// Startup moved unexpectedly.'),/startup boundary not found/);
} finally {fs.rmSync(temporary,{recursive:true,force:true});}
console.log('PASS: assembly and agent UI suites with LF/CRLF source; missing startup boundary fails before evaluation');
