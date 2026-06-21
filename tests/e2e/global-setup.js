const fs = require('fs');
const path = require('path');

// Real coordinates are gitignored (proprietary-geocoded). For CI/tests, synthesize a
// placeholder coordinates.json from atlas.json so the map can initialize. These are
// not real locations — they only let the UI render for chrome/interaction tests.
module.exports = async () => {
  const dir = path.resolve(__dirname, '../../public/data');
  const coords = path.join(dir, 'coordinates.json');
  if (fs.existsSync(coords)) return;
  const atlas = JSON.parse(fs.readFileSync(path.join(dir, 'atlas.json'), 'utf8'));
  fs.writeFileSync(coords, JSON.stringify({
    plants: atlas.P.map(() => [23.6, -102.5]),
    conns: atlas.P.map(() => null),
    hubs: atlas.H.map(() => [23.6, -102.5]),
  }));
  console.log('global-setup: wrote placeholder coordinates.json');
};
