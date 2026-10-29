#!/usr/bin/env node
// 官方原文截图：打开一页公开网页（政府公告、监管通知、官方新闻稿），找到要引用的那句话，截一张高清图，并返回那句话在图里的位置。
// 产物给 F 包的 `layout: "doc"` 用：纸面缓慢上移，说到那句时荧光带扫过（R2 政策原文页的做法）。
//
//   node scripts/webshot.mjs --url <网址> --out <工程>/broll/img/doc_xxx.png --find "新办法自2026年12月1日起施行" [--width 900] [--scale 2] [--clean]
//
// 输出：图片＋同名 .json（url、页面标题、抓取时间、hl=[x,y,w,h] 原图像素、截取范围）。stdout 打印 decompose 里能直接贴的一行。
// 规矩（references/03 §二·六）：只截官方原文与官方新闻稿；页眉（机构名、网址栏下的标题）尽量留在画面里；登记出处；不截他人的成片和付费内容。
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, '..', 'runtime', 'package.json'));
let chromium;
try { ({chromium} = require('playwright-core')); } catch (e) {
  console.error('✗ 缺 playwright-core：cd <skill>/runtime && npm install --registry=https://registry.npmjs.org/（setup.sh 会装）');
  process.exit(2);
}

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, arr) => {
  if (x.startsWith('--')) a.push([x.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return a;
}, []));
if (!args.url || !args.out) {
  console.error('用法：node webshot.mjs --url <网址> --out <图片.png> [--find "原话"] [--width 900] [--scale 2] [--height 2400] [--above 320] [--clean]');
  process.exit(1);
}
const width = Number(args.width || 900), scale = Number(args.scale || 2), cropH = Number(args.height || 2400);

// 浏览器：环境变量 CHROME_PATH → 本机 Chrome → Playwright 缓存里的 Chrome for Testing（都不用联网下载）
const home = process.env.HOME || '';
const cands = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'];
const pw = path.join(home, 'Library/Caches/ms-playwright');
if (fs.existsSync(pw)) for (const d of fs.readdirSync(pw).filter((x) => x.startsWith('chromium-')).sort().reverse()) {
  cands.push(path.join(pw, d, 'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'));
  cands.push(path.join(pw, d, 'chrome-mac/Chromium.app/Contents/MacOS/Chromium'));
  cands.push(path.join(pw, d, 'chrome-linux/chrome'));
}
const exe = cands.find((p) => p && fs.existsSync(p));
if (!exe) { console.error('✗ 找不到 Chrome：装 Google Chrome，或设 CHROME_PATH'); process.exit(2); }

const browser = await chromium.launch({executablePath: exe, headless: true, args: ['--hide-scrollbars']});
const ctx = await browser.newContext({viewport: {width, height: 1600}, deviceScaleFactor: scale, locale: 'zh-CN',
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'});
const page = await ctx.newPage();
try {
  await page.goto(args.url, {waitUntil: 'domcontentloaded', timeout: 45000});
  await page.waitForLoadState('networkidle', {timeout: 15000}).catch(() => null);
  await page.waitForTimeout(800);
  if (args.clean) {
    // 去掉悬浮的分享条、登录弹层、回到顶部按钮（只隐藏 fixed／sticky，不动正文）
    await page.evaluate(() => {
      for (const el of Array.from(document.querySelectorAll('body *'))) {
        const cs = getComputedStyle(el);
        if ((cs.position === 'fixed' || cs.position === 'sticky') && el.getBoundingClientRect().height < window.innerHeight * 0.5) el.style.visibility = 'hidden';
      }
      // 广告位：iframe、带 ad／adv／banner／guanggao 的块（新华网页眉的银行横幅 10-29 实测）——品牌广告进画面就是事故
      for (const el of Array.from(document.querySelectorAll('iframe, ins, [id*="adv" i], [class*="adv" i], [id*="banner" i], [class*="banner" i], [id*="guanggao" i], [class*="guanggao" i], [id^="ad_" i], [class^="ad-" i]'))) {
        el.style.visibility = 'hidden';
      }
    });
  }
  const title = await page.title();
  let box = null;
  if (args.find) {
    // 在正文文本里找这句话（忽略空白），找到后取它的包围盒（页面坐标，CSS 像素）
    box = await page.evaluate((needle) => {
      const norm = (s) => s.replace(/\s+/g, '');
      const want = norm(needle);
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const nodes = [];
      let all = '';
      while (walker.nextNode()) {
        const n = walker.currentNode;
        const t = n.textContent || '';
        for (let i = 0; i < t.length; i++) if (!/\s/.test(t[i])) { nodes.push([n, i]); all += t[i]; }
      }
      const k = all.indexOf(want);
      if (k < 0) return null;
      const [n0, i0] = nodes[k], [n1, i1] = nodes[k + want.length - 1];
      const r = document.createRange();
      r.setStart(n0, i0); r.setEnd(n1, i1 + 1);
      const rects = Array.from(r.getClientRects());
      const x0 = Math.min(...rects.map((q) => q.left)), y0 = Math.min(...rects.map((q) => q.top));
      const x1 = Math.max(...rects.map((q) => q.right)), y1 = Math.max(...rects.map((q) => q.bottom));
      return {x: x0 + scrollX, y: y0 + scrollY, w: x1 - x0, h: y1 - y0, lines: rects.length};
    }, args.find);
    if (!box) console.error('⚠ 页面里没找到「' + args.find + '」：截了页面顶部，hl 为空（换一句原文，或这页是图片版公告）');
  }
  const docH = await page.evaluate(() => document.documentElement.scrollHeight);
  // 截取范围：有命中就让那句话落在截图上部 30% 处（页眉在上方时尽量带上）；没命中就截页面顶部
  // 截取范围：有命中就从那句话上方 --above（默认 320 CSS 像素，够带上标题和日期）开始截，页眉的导航和广告不进画面；没命中就截页面顶部
  const y0 = box ? Math.max(0, Math.round(box.y - Number(args.above || 320))) : 0;
  const h = Math.min(cropH, docH - y0);
  fs.mkdirSync(path.dirname(path.resolve(args.out)), {recursive: true});
  await page.screenshot({path: args.out, clip: {x: 0, y: y0, width, height: h}, fullPage: true});
  const hl = box ? [Math.round(box.x * scale), Math.round((box.y - y0) * scale), Math.round(box.w * scale), Math.round(box.h * scale)] : null;
  const meta = {url: args.url, title, captured_at: new Date().toISOString(), w: width * scale, h: Math.round(h * scale), crop_y_css: y0,
    find: args.find || null, hl, browser: path.basename(exe),
    licence: '官方原文／新闻稿截图：引用出处可见、只截所需段落；中国法律法规与国家机关文件不受著作权保护（著作权法第五条），新闻稿版权归发布机构，作评论引用并注明来源'};
  fs.writeFileSync(args.out.replace(/\.(png|jpg|jpeg)$/i, '') + '.json', JSON.stringify(meta, null, 1));
  console.log('✓ ' + args.out + '  ' + meta.w + 'x' + meta.h + (hl ? '  hl=' + JSON.stringify(hl) : '  （未定位到原话）'));
  console.log('  decompose: {"layout": "doc", "image": "' + path.relative(process.cwd(), args.out) + '"' + (hl ? ', "hl": ' + JSON.stringify(hl) + ', "hl_at": "<说到哪句时扫亮>"' : '') + '}');
} finally {
  await browser.close();
}
