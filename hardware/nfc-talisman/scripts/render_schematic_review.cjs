const fs = require('fs');
const path = require('path');
const sharp = require(require.resolve('sharp', {paths:[process.argv[2]]}));
const root = path.resolve(__dirname, '..');
sharp(fs.readFileSync(path.join(root, 'eda/schematic-review.svg')), {density:160})
  .resize({width:2400})
  .flatten({background:'#ffffff'})
  .png()
  .toFile(path.join(root,'eda/schematic-review.png'))
  .then(info=>process.stdout.write(JSON.stringify(info)+'\n'))
  .catch(err=>{process.stderr.write(String(err)+'\n');process.exitCode=1;});
