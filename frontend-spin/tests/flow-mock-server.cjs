// Lokalny proxy do next dev, także dla odstepy.js. Żadne API nie trafia do backendu.
const http = require('node:http');
const fixture = require('./flow.fixture.cjs');
http.createServer((req, res) => {
  if (req.url.startsWith('/api/')) {
    res.setHeader('Content-Type', 'application/json');
    const data = req.url.startsWith('/api/przeszlosc/przeplyw/') ? fixture : req.url.startsWith('/api/przeszlosc/funkcje/') ? { beta: true, label: 'Beta', locked: [] } : {};
    res.end(JSON.stringify(data)); return;
  }
  const upstream = http.request({ hostname: '127.0.0.1', port: 3105, path: req.url, method: req.method, headers: req.headers }, response => {
    res.writeHead(response.statusCode, response.headers); response.pipe(res);
  });
  upstream.on('error', () => { res.statusCode = 502; res.end('Next dev nie działa'); }); req.pipe(upstream);
}).listen(3106, '127.0.0.1', () => console.log('Mock offline: http://127.0.0.1:3106/przeszlosc/przeplyw/osoba:1'));
