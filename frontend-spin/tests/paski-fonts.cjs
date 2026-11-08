module.exports = new Proxy({}, { get: () => '@font-face { font-family: Montserrat; src: local("Arial"); font-weight: 100 900; }' });
