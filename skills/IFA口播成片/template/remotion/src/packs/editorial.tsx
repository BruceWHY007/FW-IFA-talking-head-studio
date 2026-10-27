// 风格包 A · 分带刊物（v4）—— 借自 IFA App 展示片 v5「视觉带／文字带硬分开」：
// 上＝刊头带（纸），中＝画面窗，下＝字幕带（纸），最底＝墨色页脚（平台标题与描述叠在这里，白字要有深底）。
// 字永远不压在画面上，所以不需要底板、描边、投影；对比度由纸与墨决定（>12:1）。
//
// v4（10-27 评审）改的是「层次」，不是装饰：
// ① 字号收敛到 4 级并拉开：标题 84（fit 58）／字幕 52／小标 24／页脚 21。v3 同屏 11 个字号、24–28 是五个差 1px 的近重复，
//    标题 68 与字幕 58 只差 1.17 倍，主次立不住。现在标题/字幕 = 1.6，删掉近重复（对比原则：不要「略有不同」，要「截然不同」）。
// ② 刊头改两列栅格：左列 期号＋系列名（≤360px，超出省略），右列 话题条（只显示当前＋后两章，固定 300px 右对齐）。
//    active 只改颜色与 3px 线、不改字重（v3 加粗会让整行左右跳 20px）；下划线与标题留 17px（v3 压到「团队」字头）。
// ③ 版面重排：刊头 176–298（上沿从 166 挪到 176，不再压进平台状态栏 170）；字幕带 1420→1720（加一行 kicker：当前章节）；
//    页脚 1600→1720 起、只留 200px（v3 是 320px 只放了一个页码），页脚里放账号名＋进度条＋页码。
// ④ 名字条缺姓名时收成 76px 单行（v3 是 126px 空模板，姓名行空着、下面 60px 白）。
//
// 两个方向共用这一套栅格，只换 V4：'jia'＝保留上下纸带；'yi'＝画面窗上移到 0，刊头用纸色渐变压在画面顶部。
import React from 'react';
import {Cap, Shot, prog, wipe} from './common';
import {FigureCore, PhotoCore, Mixed, CoverForm, PhoneFrameCore, phonePushK, fitSize} from './parts';
import {InfoCore, InfoStyle} from './info';
import {F, TH, ease} from '../theme';
import tlRaw from '../timeline.json';

// 颜色全部来自账号主题（themes.json）：纸色、纸上强调、细线、暗底强调、页脚
const K = {
  paper: TH.paper, ink: '#191612', inkSoft: '#62584D', gold: TH.line, line: TH.line,
  goldText: TH.accent, // 纸上的强调文字（对纸 ≥4.5:1；琥珀金的 #94673D 只有 4.3:1，所以文字用 #7F5631）
  night: TH.foot, dark: TH.dark,
};

const V4: 'jia' | 'yi' = 'jia';
const WIN = V4 === 'yi' ? {x: 0, y: 0, w: 1080, h: 1420} : {x: 0, y: 300, w: 1080, h: 1120};
const SEAM = WIN.y + WIN.h;   // 1420
const CAP_Y = SEAM + 20;      // kicker 行
const CAP_TXT = SEAM + 80;    // 字幕第一行
const FOOT = 1760;            // 墨色平台板起点：只给平台的账号名／描述／音乐条留 160px
const FOOTER = String((tlRaw as any).footer || 'paper') as 'plate' | 'fade' | 'paper';  // plate＝160px 深底；fade＝深底只 100px，上面 90px 渐变压深；paper＝整页纸
const FOOT_L = String((tlRaw as any).footer_left || '复星财富IFA');
const FOOT_R = String((tlRaw as any).footer_right || '');
const COLOPHON = FOOTER === 'paper' ? 1812 : 1712;  // 报尾：账号名／章节点／页码
const PLATE = FOOTER === 'fade' ? 1820 : FOOT;        // fade 只在最底留 100px
const BAR_Y = FOOTER === 'paper' ? 1902 : (FOOTER === 'fade' ? PLATE - 2 : FOOT - 2);  // 进度条：在纸／墨交界（paper 模式在最底）
const PAD = 72;
const NAV_W = 300;            // 右列固定宽：换章时整组不左右跳
const T = {title: 76, titleMin: 56, cap: 52, meta: 22, micro: 20};
// 刊头整块在纸带里居中：块高 ≈ meta 22 + 间距 36 + 标题 78 = 136，(300-136)/2 ≈ 82
const MAST_Y = 82;            // 期号／系列名／章节位置那一行
const TITLE_Y = 118;          // 标题行
const DUR = Number((tlRaw as any).durationInFrames || 0);
const hexA = (hex: string, a: number) => {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

const Under: React.FC = () => (
  <>
    {WIN.y > 0 ? <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: WIN.y, background: K.paper}} /> : null}
    <div style={{position: 'absolute', left: 0, top: SEAM, width: 1080, height: FOOT - SEAM, background: K.paper}} />
    {FOOTER === 'plate' ? <div style={{position: 'absolute', left: 0, top: FOOT, width: 1080, height: 1920 - FOOT, background: K.night}} /> : null}
    {FOOTER === 'fade' ? (
      <>
        <div style={{position: 'absolute', left: 0, top: PLATE - 96, width: 1080, height: 100,
          background: `linear-gradient(180deg, ${hexA(K.night, 0)} 0%, ${hexA(K.night, 0.30)} 55%, ${hexA(K.night, 0.72)} 82%, ${K.night} 100%)`}} />
        <div style={{position: 'absolute', left: 0, top: PLATE, width: 1080, height: 1920 - PLATE, background: K.night}} />
      </>
    ) : null}
  </>
);

const Over: React.FC = () => (
  <>
    {/* 乙方向：画面窗顶到 0，刊头用纸色渐变压在画面顶上（画在 Over 层，否则 B-roll／大字卡的底会把它盖住） */}
    {V4 === 'yi' ? <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 400,
      background: `linear-gradient(180deg, ${hexA(K.paper, 0.98)} 0%, ${hexA(K.paper, 0.96)} 58%, ${hexA(K.paper, 0.88)} 74%, ${hexA(K.paper, 0)} 100%)`}} /> : null}
    {/* 画面窗的 1px 细边：纸上的一张照片要有边界（不描边不投影，只借纸色压出一道极细的线） */}
    <div style={{position: 'absolute', left: 0, top: WIN.y, width: 1080, height: WIN.h, boxShadow: 'inset 0 0 0 1px rgba(25,22,18,0.10)'}} />
    <div style={{position: 'absolute', left: 0, top: SEAM, width: 1080, height: 1, background: K.line, opacity: 0.55}} />
    <div style={{position: 'absolute', left: PAD, top: SEAM - 1, width: 44, height: 3, background: K.gold}} />
    
  </>
);

// 顶部右侧只放章节位置「02 / 05」：五个章节名挤在一行会把系列名挤掉，字面信息交给字幕带顶上的章节小标
const Chapters: React.FC<{f: number; chapters: any[]; top: number}> = ({f, chapters, top}) => {
  if (!chapters || !chapters.length) return null;
  const names: string[] = [];
  chapters.forEach((c) => { if (!names.includes(c.title)) names.push(c.title); });
  let idx = 0;
  chapters.forEach((c, i) => { if (f >= (c.from || 0)) idx = i; });
  const cur = Math.max(0, names.indexOf((chapters[idx] || chapters[0]).title));
  const two = (n: number) => String(n + 1).padStart(2, '0');
  return (
    <div style={{position: 'absolute', right: PAD, top, height: 30, display: 'flex', alignItems: 'baseline', gap: 6}}>
      <span style={{fontFamily: F.didot, fontWeight: 600, fontSize: T.meta + 2, letterSpacing: '0.04em', color: K.ink}}>{two(cur)}</span>
      <span style={{fontFamily: F.didot, fontSize: T.meta + 2, letterSpacing: '0.04em', color: 'rgba(25,22,18,0.34)'}}>/ {two(names.length - 1)}</span>
    </div>
  );
};

// 报尾与章节小标：字幕带顶上一行「现在讲哪一章」；纸带底部是报尾（账号名／章节圆点／页码），
// 墨色只剩最底 160px 那一块——它是给平台自己的账号名与描述压白字用的，不是设计元素。
const Furniture: React.FC<{f: number; end: any; chapters: any[]}> = ({f, end, chapters}) => {
  let idx = 0;
  (chapters || []).forEach((c, i) => { if (f >= (c.from || 0)) idx = i; });
  const names: string[] = [];
  (chapters || []).forEach((c) => { if (!names.includes(c.title)) names.push(c.title); });
  const cur = chapters && chapters[idx] ? chapters[idx].title : '';
  const acct = String((tlRaw as any).account || '');
  const p = DUR ? Math.min(1, Math.max(0, f / DUR)) : 0;
  return (
    <>
      <div style={{position: 'absolute', left: PAD, top: CAP_Y, height: 30, display: 'flex', alignItems: 'center', gap: 14}}>
        <span style={{width: 40, height: 2, background: K.gold}} />
        <span style={{fontFamily: F.sans, fontWeight: 500, fontSize: T.meta, letterSpacing: '0.3em', color: K.goldText}}>{cur}</span>
      </div>
      <div style={{position: 'absolute', left: PAD, top: COLOPHON, fontFamily: F.sans, fontWeight: 500, fontSize: T.micro,
        letterSpacing: '0.14em', color: 'rgba(25,22,18,0.62)'}}>{FOOT_L}</div>
      {/* 五个章节圆点：当前那一颗用主题色并拉长 */}
      <div style={{position: 'absolute', left: 0, right: 0, top: COLOPHON + 7, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9}}>
        {names.map((n, i) => (
          <span key={n} style={{width: i === idx ? 20 : 6, height: 6, borderRadius: 3,
            background: i === idx ? K.goldText : 'rgba(25,22,18,0.20)'}} />
        ))}
      </div>
      <div style={{position: 'absolute', right: PAD, top: COLOPHON - 1}}>
        <span style={{fontFamily: F.sans, fontSize: T.micro, color: 'rgba(25,22,18,0.52)', letterSpacing: '0.08em'}}>{FOOT_R}</span>
      </div>
      {/* 报尾不要横线（10-27 用户意见）：只留左右两行小字 */}
      {FOOTER === 'plate' ? <div style={{position: 'absolute', left: 0, top: BAR_Y, width: 1080, height: 2, background: K.gold, opacity: 0.9, transform: `scaleX(${p})`, transformOrigin: '0% 50%'}} /> : null}
    </>
  );
};

// 刊头：两列栅格＋一个标题槽。期号／系列名／话题条是「页面固定件」，一直在；只有标题槽在讲到「下期」时换内容，
// 所以 66 秒之后那 16 秒里顶上不会变成一条空白纸（v3 是整块刊头一起换，中间还有 5 帧什么都没有）。
const Masthead: React.FC<{f: number; series: string; episode: string; end: any; chapters?: any[]; coverEnd?: number}> = ({f, series, episode, end, chapters, coverEnd = 0}) => {
  const out = end ? prog(f - end.from, 0, 5, ease.in) : 0;
  const reveal = coverEnd ? wipe(f - coverEnd, 0, 8) : 0;
  const inn = end ? prog(f - end.from, 3, 13) : 0;
  const hidden = f < coverEnd ? 100 : reveal;
  return (
    <>
      <div style={{position: 'absolute', left: PAD, top: MAST_Y, height: 30, display: 'flex', alignItems: 'center', gap: 16}}>
        <span style={{fontFamily: F.didot, fontSize: 24, fontWeight: 500, color: K.gold, letterSpacing: '0.06em'}}>No.01</span>
        <span style={{width: 1, height: 20, background: K.line, opacity: f < coverEnd ? 0 : 0.55}} />
        <span style={{fontFamily: F.sans, fontWeight: 400, fontSize: T.meta, letterSpacing: '0.14em', color: K.inkSoft,
          maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          clipPath: `inset(0 ${hidden}% 0 0)`}}>{series}</span>
      </div>
      <Chapters f={f} chapters={chapters || []} top={MAST_Y} />
      {/* 标题槽：本期标题 ↔ 下期预告，同一块位置互换，固定件不动 */}
      <div style={{position: 'absolute', left: PAD, right: PAD, top: TITLE_Y, height: 90, overflow: 'hidden'}}>
        {out < 1 ? (
          <div style={{opacity: 1 - out, fontFamily: F.serif, fontWeight: 900,
            fontSize: fitSize(episode, 936, T.title, T.titleMin), lineHeight: 1.02, color: K.ink,
            letterSpacing: '-0.015em', whiteSpace: 'nowrap', clipPath: `inset(-12% ${hidden}% -12% 0)`}}>
            <Mixed t={episode} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.06em', letterSpacing: '-0.01em'}} />
          </div>
        ) : null}
        {end && inn > 0 ? (
          <div style={{position: 'absolute', left: 0, right: 0, top: 0, clipPath: `inset(0 ${(1 - inn) * 100}% 0 0)`}}>
            <div style={{fontFamily: F.sans, fontWeight: 500, fontSize: T.meta, letterSpacing: '0.3em', color: K.goldText}}>{end.kicker}</div>
            <div style={{marginTop: 8, fontFamily: F.serif, fontWeight: 900, fontSize: fitSize(String(end.line).replace(/\n/g, '，'), 880, 32, 22), lineHeight: 1.1, color: K.ink, whiteSpace: 'nowrap'}}>
              <Mixed t={String(end.line).replace(/\n/g, '，')} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.06em'}} />
            </div>
          </div>
        ) : null}
      </div>
      <Furniture f={f} end={end} chapters={chapters || []} />
    </>
  );
};

// 字幕：字幕带里左对齐，墨色苹方 Regular 52。关键词「跟着嘴走」：说到它的那一帧变铜金色、放大 1.15 倍、
// 数字换 Didot、下面画出一道 6px 细线——行内强调也用它，让核心信息在字幕里立起来；一段话的第一张用 4 帧遮罩揭开
const KeyWord: React.FC<{t: string; at: number; f: number}> = ({t, at, f}) => {
  const on = prog(f - at, 0, 3);
  const line = prog(f - at, 1, 8);
  const num = /\d/.test(t);
  return (
    <span style={{position: 'relative', display: 'inline-block', fontSize: '1.15em', lineHeight: 1.16,
      color: on > 0.5 ? K.goldText : K.ink, fontWeight: on > 0.5 ? 700 : 400}}>
      {num ? <Mixed t={t} num={{fontFamily: F.didot, fontWeight: 700, fontSize: '1.02em'}} /> : t}
      <span style={{position: 'absolute', left: 0, right: 0, bottom: 2, height: 6, background: K.gold,
        transform: `scaleX(${line})`, transformOrigin: '0% 50%'}} />
    </span>
  );
};
const Caption: React.FC<{cap: Cap; f: number}> = ({cap, f}) => (
  <div style={{position: 'absolute', left: PAD, right: 140, top: CAP_TXT}}>
    {cap.lines.map((l: any, i) => {
      if (f < l.from && !(cap.animate && i === 0)) return null;
      const r = cap.animate && i === 0 ? wipe(f - cap.from, 0, 4) : 0;
      const parts: React.ReactNode[] = [];
      let k = 0;
      const rs = (l.hl || []).map((h: [number, number], j: number) => ({a: h[0], b: h[1], at: (l.hlAt || [])[j] ?? l.from}))
        .sort((x: any, y: any) => x.a - y.a);
      rs.forEach((h: any, j: number) => {
        if (h.a < k) return;
        if (h.a > k) parts.push(<span key={'n' + j}>{l.text.slice(k, h.a)}</span>);
        parts.push(<KeyWord key={'h' + j} t={l.text.slice(h.a, h.b)} at={h.at} f={f} />);
        k = h.b;
      });
      if (k < l.text.length) parts.push(<span key="tail">{l.text.slice(k)}</span>);
      return (
        <div key={i} style={{fontFamily: F.sans, fontWeight: 400, fontSize: T.cap, lineHeight: 1.34, color: K.ink, letterSpacing: '0.01em',
          whiteSpace: 'nowrap', clipPath: `inset(-10% ${r}% -20% 0)`}}>{parts}</div>
      );
    })}
  </div>
);

// 名字条：一张从接缝上「长出来」的纸签，挂在画面窗底边——是版面的一部分，不是浮在画面上的贴纸。
// v4：没有姓名时收成 76px 单行（只有身份行），不留空模板
const NameTag: React.FC<{f: number; d: any}> = ({f, d}) => {
  const local = f - d.from;
  if (local < 0 || f >= d.to) return null;
  const up = prog(local, 0, 8) - prog(local, d.to - d.from - 6, d.to - d.from, ease.in);
  const hasName = !!(d.name && String(d.name).trim());
  const h = hasName ? 126 : 76;
  return (
    <div style={{position: 'absolute', left: PAD, top: SEAM - h - 14, height: h, clipPath: `inset(${(1 - up) * 100}% 0 0 0)`}}>
      <div style={{background: K.paper, padding: hasName ? '16px 34px 0 28px' : '22px 30px 0 28px', height: h, boxSizing: 'border-box',
        borderTop: `3px solid ${K.gold}`}}>
        {hasName ? (
          <>
            <div style={{display: 'flex', alignItems: 'baseline', gap: 14, whiteSpace: 'nowrap'}}>
              <span style={{fontFamily: F.serif, fontWeight: 900, fontSize: 44, color: K.ink}}>{d.name}</span>
              {d.latin ? <span style={{fontFamily: F.didot, fontSize: 28, color: K.gold}}>{d.latin}</span> : null}
            </div>
            <div style={{marginTop: 8, fontFamily: F.sans, fontWeight: 400, fontSize: T.meta, letterSpacing: '0.14em', color: K.inkSoft, whiteSpace: 'nowrap'}}>
              {(d.lines || []).join('　·　')}
            </div>
          </>
        ) : (
          <div style={{fontFamily: F.sans, fontWeight: 500, fontSize: 26, letterSpacing: '0.18em', color: K.ink, whiteSpace: 'nowrap'}}>
            {(d.lines || []).join('　·　')}
          </div>
        )}
      </div>
    </div>
  );
};

// 标注签：从画面窗上沿垂下来的小纸签；给了 point（画面窗内 0–1 坐标）就画一条细线指过去，末端一个小圆
const Tag: React.FC<{f: number; t: any}> = ({f, t}) => {
  const d = prog(f - t.from, 0, 7);
  const ln = prog(f - t.from, 6, 18);
  const pt = t.point;
  const x0 = 72 + 30, y0 = WIN.y + 62;
  const x1 = pt ? pt[0] * WIN.w : 0, y1 = pt ? WIN.y + pt[1] * WIN.h : 0;
  const len = pt ? Math.hypot(x1 - x0, y1 - y0) : 0;
  const ring = prog(f - t.from, 16, 22);
  return (
    <>
      {pt ? (
        <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0, pointerEvents: 'none'}}>
          {/* 指引线用墨色细线＋纸色描边：亮窗、暗墙上都看得见（纯白线画在亮窗上会消失，10-22 实测） */}
          <line x1={x0} y1={y0} x2={x1} y2={y1} stroke={K.paper} strokeWidth={5} strokeDasharray={len} strokeDashoffset={(1 - ln) * len} opacity={0.9} />
          <line x1={x0} y1={y0} x2={x1} y2={y1} stroke={K.ink} strokeWidth={2} strokeDasharray={len} strokeDashoffset={(1 - ln) * len} />
          <circle cx={x1} cy={y1} r={12} fill="none" stroke={K.paper} strokeWidth={5} opacity={0.9 * ring} />
          <circle cx={x1} cy={y1} r={12} fill="none" stroke={K.ink} strokeWidth={2} opacity={ring} />
          <circle cx={x1} cy={y1} r={4} fill={K.ink} opacity={ring} />
        </svg>
      ) : null}
      <div style={{position: 'absolute', left: PAD, top: WIN.y + 18, clipPath: `inset(0 0 ${(1 - d) * 100}% 0)`}}>
        <div style={{background: K.paper, padding: '12px 22px 14px', display: 'flex', alignItems: 'center', gap: 12}}>
          <span style={{width: 18, height: 2, background: K.gold}} />
          <span style={{fontFamily: F.sans, fontWeight: 500, fontSize: T.meta, letterSpacing: '0.16em', color: K.ink, whiteSpace: 'nowrap'}}>{t.text}</span>
        </div>
      </div>
    </>
  );
};

// 真实性角标：AI 画面写「AI 生成」，免费实拍写「示意画面」，挂在画面窗右上（借自 talk-workbench 的真实性标签）
const Label: React.FC<{f: number; from: number; text: string}> = ({f, from, text}) => {
  const d = prog(f - from, 2, 9);
  return (
    <div style={{position: 'absolute', right: PAD, top: WIN.y + 18, clipPath: `inset(0 0 ${(1 - d) * 100}% 0)`}}>
      <div style={{background: 'rgba(243,237,227,0.94)', padding: '8px 16px 10px', fontFamily: F.sans, fontWeight: 500, fontSize: T.micro,
        letterSpacing: '0.14em', color: K.inkSoft, whiteSpace: 'nowrap'}}>{text}</div>
    </div>
  );
};

// 分屏两边的小纸签（「事业」「家庭」），挂在画面窗上沿下方一点（左上角让给标注签）
const SplitLabels: React.FC<{f: number; at: number; labels: string[]}> = ({f, at, labels}) => (
  <>
    {labels.map((l, i) => {
      const d = prog(f - at - (i === 0 ? 2 : 8), 0, 7);
      return (
        <div key={i} style={{position: 'absolute', left: i === 0 ? 72 : 540 + 40, top: WIN.y + 64, clipPath: `inset(0 0 ${(1 - d) * 100}% 0)`}}>
          <div style={{background: K.paper, padding: '9px 18px 11px', fontFamily: F.sans, fontWeight: 500, fontSize: T.meta, letterSpacing: '0.3em',
            color: K.ink}}>{l}</div>
        </div>
      );
    })}
  </>
);

// 封面：画在画面窗下部（底部渐暗＋两行宋体大标题），字幕带照常走——第一句字幕从第 2 帧就出（10-22 评审第 2 轮）。
// 停满 frames 后硬切掉（不擦除，不和字幕叠）
const Cover: React.FC<{f: number; d: any}> = ({f, d}) => {
  if (f >= d.frames) return null;
  const form = d.form && d.form !== 'title';
  return (
    <div style={{position: 'absolute', left: 0, top: WIN.y, width: WIN.w, height: WIN.h}}>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: form ? 700 : 600,
        background: 'linear-gradient(180deg, rgba(13,18,22,0) 0%, rgba(13,18,22,0.66) 50%, rgba(13,18,22,0.86) 100%)'}} />
      {form ? (
        <div style={{position: 'absolute', left: 72, right: 72, bottom: 64}}>
          <CoverForm d={d} t={{ink: '#F5F0E6', soft: 'rgba(245,240,230,0.72)', accent: K.dark, numFont: F.didot, numWeight: 700, titleFont: F.serif, w: 936}} />
        </div>
      ) : (
      <div style={{position: 'absolute', left: 72, right: 72, bottom: 64}}>
        <div style={{fontFamily: F.sans, fontWeight: 300, fontSize: 28, letterSpacing: '0.44em', color: K.dark}}>{d.kicker}</div>
        {(d.title || []).map((t: string, i: number) => (
          // v3：封面字 84→116（信息流里第一眼要读得出来，第 5 轮评审：标题弱于参考片）
          <div key={i} style={{marginTop: i === 0 ? 14 : 0, fontFamily: F.serif, fontWeight: 900, fontSize: fitSize(t, 936, 116, 80), lineHeight: 1.12, color: '#F5F0E6',
            letterSpacing: '-0.01em', whiteSpace: 'nowrap'}}>
            {/* 标题里的「□」画成金色空方格：和后面大字卡的方格是同一个东西，开场埋、揭晓时落字 */}
            {t.split(/(□)/).map((part, j) => part === '□'
              ? <span key={j} style={{display: 'inline-block', width: '0.86em', height: '0.86em', margin: '0 0.06em', verticalAlign: '-0.08em',
                  border: `4px solid ${K.dark}`, boxSizing: 'border-box'}} />
              : <Mixed key={j} t={part} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.1em', color: K.dark}} />)}
          </div>
        ))}
      </div>
      )}
    </div>
  );
};

// 「手机里的她」：讲「录视频、出镜」时，把她本人的原片放进一部手机里（不用别人当替身，10-22 评审第 2 轮）
const PHONE = {x: 290, y: 70, w: 500, h: 980, r: 60, bezel: 14, k: 0.92, faceY: 0.4, color: K.paper};
export const phonePush = phonePushK;
const PhoneFrame: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhoneFrameCore f={f} s={s} win={WIN} ph={PHONE} />;
// top 520：放在脸下方，方格不框住虚化的眼睛（第 4 轮评审）
const Figure: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <FigureCore f={f} s={s} win={WIN} top={470} label="rgba(245,240,230,0.82)" value={K.dark} word="#F5F0E6" box={K.dark} />
);
const Photo: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhotoCore f={f} s={s} win={WIN} credit="rgba(245,240,230,0.7)" />;

// 信息卡：象牙纸卡压在虚化的她上面（和大字卡同一个底），顶边一道主题细线
const PaperCard: React.FC<{x: number; y: number; w: number; h: number}> = ({x, y, w, h}) => (
  <div style={{position: 'absolute', left: x, top: y, width: w, height: h, background: K.paper, borderTop: `4px solid ${K.gold}`}} />
);
const INFO: InfoStyle = {
  area: {x: 120, y: 170, w: 840, h: 760}, ink: K.ink, mute: K.inkSoft, accent: K.goldText, accent2: '#B9AE9E', card: K.paper,
  mark: 'underline', titleFont: F.serif, titleWeight: 900, numFont: F.didot, numWeight: 700, radius: 0, pad: 48, gap: 28,
  presenter: {mode: 'blur'}, Surface: PaperCard, areaCard: ['quote', 'compare', 'list', 'timeline', 'chart'],
};
const Info: React.FC<{f: number; s: Shot; face: any; src: string}> = (p) => <InfoCore {...p} st={INFO} />;

export const editorial = {
  name: 'editorial', win: WIN, faceY: 0.49, canvas: K.paper, under: true, Info, info: INFO,
  Under, Over, Masthead, Caption, NameTag, EndCard: null as any, Tag, Cover, Figure, Photo, SplitLabels, Label, PhoneFrame,
  phone: PHONE, phonePush, coverInWindow: true,
  halftone: 0.22, grainOnBands: true, seam: K.paper,
};
