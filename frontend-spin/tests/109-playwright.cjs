const playwright = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const launch = playwright.chromium.launch.bind(playwright.chromium);
playwright.chromium.launch = options => launch({ ...options, channel: undefined, headless: true,
  executablePath: 'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe',
  args: ['--window-position=-32000,-32000', '--window-size=1,1'],
});
module.exports = playwright;
