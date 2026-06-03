const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: null });
  const file = 'file://' + process.cwd() + '/index.html';
  await page.goto(file, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);

  for (let i = 1; i <= 18; i++) {
    const id = String(i).padStart(2, '0');
    const sel = `#xhs-${id}`;
    const name = `xhs-${id}.png`;
    const el = await page.$(sel);
    if (el) {
      await el.screenshot({ path: 'output/' + name, type: 'png' });
      console.log('OK: ' + name);
    } else {
      console.log('MISSING: ' + sel);
    }
  }

  await browser.close();
  console.log('Done. All 18 posters rendered.');
})();
