const fs = require('fs');
const content = fs.readFileSync('/Users/nikos/Desktop/VNStudio/src/App.tsx', 'utf8');
const lines = content.split('\n');
let balance = 0;
lines.forEach((line, i) => {
  const opens = (line.match(/<div(?!\/)/g) || []).length;
  const closes = (line.match(/<\/div>/g) || []).length;
  const selfCloses = (line.match(/<div[^>]*\/>/g) || []).length;
  balance += opens - closes - selfCloses;
  if (opens || closes) {
    console.log(`${i + 1}: ${line.trim()} [Balance: ${balance}]`);
  }
});
