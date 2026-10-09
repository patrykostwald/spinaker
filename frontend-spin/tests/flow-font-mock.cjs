// Next dev offline: nie pobieraj Google Fonts. Podgląd używa systemowego fontu zastępczego.
module.exports = new Proxy({}, { get: () => '@font-face { font-family: Montserrat; src: local("Arial"); font-style: normal; font-weight: 100 900; }' });
