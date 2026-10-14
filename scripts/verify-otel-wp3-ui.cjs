#!/usr/bin/env node
/* WP3 UI proof: four dashboards and exact Log -> Trace -> Related Logs clicks.
 * Requires an installed "playwright" Node module; see README.otel-lgtm.md.
 * Runs a headless browser, so it does not steal the Mac's foreground window.
 */
const fs = require('fs');
const { randomBytes } = require('crypto');
let chromium;
try {
  chromium = require('playwright').chromium;
} catch {
  console.error('UNVERIFIED WP3 UI: playwright unavailable. Install it or set NODE_PATH.');
  process.exit(2);
}
const host = 'http://127.0.0.1:3300';
const api = 'http://127.0.0.1:8082';
const authorization = 'Basic ' + Buffer.from(
  (process.env.GRAFANA_USER || 'admin') + ':' +
  (process.env.GRAFANA_PASSWORD || 'admin')
).toString('base64');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function backendHasFreshLog(traceId, since) {
  for (let i = 0; i < 40; i++) {
    const params = new URLSearchParams({
      query: '{service_name="demo-api"} | trace_id="' + traceId + '"',
      start: String(BigInt(since - 10000) * 1000000n),
      limit: '10'
    });
    const response = await fetch(
      host + '/api/datasources/proxy/uid/lab-otel-loki/loki/api/v1/query_range?' + params,
      {headers: {Authorization: authorization}});
    if (response.ok) {
      const data = await response.json();
      const count = (data.data?.result || []).reduce(
        (sum, item) => sum + item.values.length, 0);
      if (count === 1) return;
    }
    await delay(1000);
  }
  throw new Error('Fresh Loki trace ID missing or duplicate after bounded retries');
}

function exploreLokiUrl(traceId) {
  const panes = {WP3: {
    datasource: 'lab-otel-loki',
    queries: [{
      refId: 'A', editorMode: 'code', queryType: 'range',
      expr: '{service_name="demo-api"} | trace_id="' + traceId + '"',
      datasource: {type: 'loki', uid: 'lab-otel-loki'}
    }],
    range: {from: 'now-10m', to: 'now'}
  }};
  return host + '/explore?schemaVersion=1&orgId=1&panes=' +
    encodeURIComponent(JSON.stringify(panes));
}

async function main() {
  const executablePath = [
    process.env.WP3_BROWSER_PATH, chromium.executablePath(),
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  ].filter(Boolean).find(path => fs.existsSync(path));
  if (!executablePath) {
    throw new Error('No headless Chromium binary found; set WP3_BROWSER_PATH');
  }

  // Synthetic request only. Do not use production credentials or data.
  const traceId = randomBytes(16).toString('hex');
  const parentId = randomBytes(8).toString('hex');
  const since = Date.now();
  const result = await fetch(api + '/error', {
    headers: {traceparent: '00-' + traceId + '-' + parentId + '-01'}
  });
  if (result.status !== 500) throw new Error('Unexpected demo API status');
  await backendHasFreshLog(traceId, since);

  const browser = await chromium.launch({
    executablePath, headless: true,
    args: ['--disable-extensions', '--no-first-run'], timeout: 30000
  });
  try {
    const context = await browser.newContext({
      viewport: {width: 1440, height: 960},
      extraHTTPHeaders: {Authorization: authorization}
    });
    const page = await context.newPage();
    const dashboards = {
      'prometheus-first-look': 'OTel Collector scrape',
      'demo-api-metrics': 'Per-Endpoint Request Rate',
      'demo-api-logs': 'Request Logs',
      'demo-api-traces': 'Demo API request traces'
    };
    for (const [uid, title] of Object.entries(dashboards)) {
      await page.goto(host + '/d/' + uid + '?from=now-15m&to=now',
        {waitUntil: 'domcontentloaded', timeout: 30000});
      await page.getByText(title, {exact: false}).first()
        .waitFor({timeout: 30000});
      const body = await page.locator('body').innerText();
      if (/failed to load its application files/i.test(body)) {
        throw new Error('Grafana frontend assets failed on dashboard ' + uid);
      }
      console.log('PASS dashboard UI', uid);
    }

    await page.goto(exploreLokiUrl(traceId),
      {waitUntil: 'domcontentloaded', timeout: 30000});
    const log = page.getByText('request_completed', {exact: false}).last();
    await log.waitFor({timeout: 35000});
    await log.click({timeout: 12000});

    const viewTrace = page.getByRole('link', {name: 'View Trace'}).first();
    await viewTrace.waitFor({timeout: 12000});
    const tempoLink = await viewTrace.getAttribute('href');
    if (!decodeURIComponent(tempoLink).includes(traceId) ||
        !decodeURIComponent(tempoLink).includes('lab-otel-tempo')) {
      throw new Error('Log -> Tempo link did not carry exact trace ID and UID');
    }
    await viewTrace.click({timeout: 12000});
    await page.getByText('demo-api: GET /error', {exact: false}).first()
      .waitFor({timeout: 35000});
    if (!decodeURIComponent(page.url()).includes(traceId)) {
      throw new Error('Tempo Explore did not open expected trace');
    }
    console.log('PASS Log -> Trace UI click', traceId);

    await page.getByText('GET /error', {exact: false}).last()
      .click({timeout: 12000});
    const related = page.getByRole('link', {name: 'Related logs'}).first();
    await related.waitFor({timeout: 12000});
    const logLink = await related.getAttribute('href');
    const parsed = new URL(logLink, host);
    const state = JSON.parse(parsed.searchParams.get('left'));
    const expression = state.queries?.[0]?.expr || '';
    if (state.datasource !== 'lab-otel-loki' ||
        !expression.includes('service_name="demo-api"') ||
        !expression.includes(traceId)) {
      throw new Error('Tempo -> Loki link lost service or exact trace-ID filter');
    }
    await related.click({timeout: 12000});
    await page.getByText('request_completed', {exact: false}).last()
      .waitFor({timeout: 35000});
    const body = await page.locator('body').innerText();
    if (!body.includes('1 line displayed') || !body.includes(traceId)) {
      throw new Error('Related Loki log did not return one same-request event');
    }
    console.log('PASS Trace -> Logs UI click', traceId);

    const dir = process.env.WP3_EVIDENCE_DIR;
    if (dir) {
      fs.mkdirSync(dir, {recursive: true});
      const path = require('path').join(dir, 'wp3-related-logs.png');
      await page.screenshot({path, fullPage: true});
      console.log('WP3_UI_SCREENSHOT', path);
    }
    console.log(JSON.stringify({
      result: 'PASS', scope: 'WP3 headless UI',
      dashboards: Object.keys(dashboards).length,
      log_to_trace: true, trace_to_logs: true,
      trace_id: traceId
    }));
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error('FAIL WP3 UI:', error.message);
  process.exitCode = 1;
});
