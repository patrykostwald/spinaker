// Istniejące lokalne pliki Montserrat, bez pobierania Google Fonts.
const fs = require('node:fs');
const path = require('node:path');
const base = 'C:/Users/User/spin-clinic/.local/spinaker-mvp-frontend/frontend-spin/.next/static';
const css = fs.readFileSync(path.join(base, 'css/app/layout.css'), 'utf8');
const faces = [...css.matchAll(/@font-face\s*\{[^}]*src: url\([^}]+\}/g)].map(m => m[0]).filter(s => s.includes('Montserrat'));
const fixture = faces.join('\n').replace(/__Montserrat_[a-z0-9]+/g, 'Montserrat').replace(/\/_next\/static\/media\//g, `${base}/media/`);
module.exports = new Proxy({}, { get: () => fixture });
