const fs=require('node:fs');
const path=require('node:path');

// Evaluate the workspace UI without running its initial network requests.
// Windows checkouts may contain CRLF; normalize only this in-memory test copy.
function withoutStartup(text) {
  const source=text.replace(/\r\n?/g,'\n').replace(/^import .+;$/gm,'');
  const boundary=source.lastIndexOf('\nrender();\nrun(async');
  if(boundary<0)throw new Error('Studio startup boundary not found. Update the test harness before evaluating application code.');
  return source.slice(0,boundary);
}

function readStudio(root=process.cwd()) {
  return withoutStartup(fs.readFileSync(path.join(root,'palladio/web/studio.js'),'utf8'));
}

module.exports={readStudio,withoutStartup};
