// 风格包 K1 · 证据桌 —— 借 huashu-art-motion 的 Vox 拼贴语法（y2）与纸片的标注层：
// 整页是一张桌面（纸纹静态、不闪），人脸画面像一张撕边照片压在桌上；屏上的说法以「剪报／原文」的样子放上来，
// 关键词用荧光笔扫、赢的那个数字画红圈、标签是黑底白字条。适合：政策、新闻、报告、「谁说了什么」——观众要亲眼看到出处。
// 红色与荧光是这套语法本身，不跟账号主题变；页脚跟主题。
import React from 'react';
import {Cap, Shot, prog, wipe} from './common';
import {FigureCore, PhotoCore, Mixed, CoverForm, PhoneFrameCore, phonePushK, fitSize} from './parts';
import {InfoCore, InfoStyle} from './info';
import {F, TH, ease} from '../theme';
import tlRaw from '../timeline.json';

const K = {desk: '#E4DDCF', red: '#B8433F', ink: '#1B1B1A', clip: '#F3EFE6', mute: '#6B6358', hl: 'rgba(218,207,8,0.82)', foot: TH.foot};
const WIN = {x: 0, y: 312, w: 1080, h: 1100};
const SEAM = WIN.y + WIN.h; // 1412
const FOOT = 1760;
const DUR = Number((tlRaw as any).durationInFrames || 0);
const ACCT = String((tlRaw as any).account || '');
const FOOT_L = String((tlRaw as any).footer_left || '复星财富IFA');
const FOOT_R = String((tlRaw as any).footer_right || '');
const FOOTER = String((tlRaw as any).footer || 'paper') as 'plate' | 'paper';
const COL_Y = FOOTER === 'paper' ? 1812 : 1712;
const BAR_Y = FOOTER === 'paper' ? 1902 : FOOT - 2;

// 纸纹：SVG 噪声（静态，不逐帧变——Vox 实测停留段帧差 0.0–0.1）
const tex = (r: number, g: number, b: number, a: number, freq = 0.85) =>
  `url("data:image/svg+xml;utf8,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='540' height='540'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='${freq}' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 ${r} 0 0 0 0 ${g} 0 0 0 0 ${b} 0 0 0 ${a} 0'/></filter><rect width='100%' height='100%' filter='url(#n)'/></svg>`)}")`;
const DESK_BG = `${tex(0.33, 0.27, 0.18, 0.13)}, ${tex(0.30, 0.25, 0.18, 0.07, 0.05)}`;
const CLIP_BG = tex(0.40, 0.35, 0.25, 0.08);

// 可复现的伪随机：同一张卡每一帧撕边一样
const rnd = (seed: number) => { let t = seed * 9301 + 49297; return () => { t = (t * 9301 + 49297) % 233280; return t / 233280; }; };
export const torn = (w: number, h: number, seed: number, amp = 7, step = 15, sides = 'tb') => {
  const r = rnd(seed);
  const pts: string[] = [];
  for (let x = 0; x <= w; x += step * (0.6 + r() * 0.8)) pts.push(`${x.toFixed(1)}px ${(sides.includes('t') ? r() * amp : 0).toFixed(1)}px`);
  pts.push(`${w}px 0px`);
  for (let x = w; x >= 0; x -= step * (0.6 + r() * 0.8)) pts.push(`${x.toFixed(1)}px ${(h - (sides.includes('b') ? r() * amp : 0)).toFixed(1)}px`);
  pts.push(`0px ${h}px`);
  return `polygon(${pts.join(',')})`;
};

const Tape: React.FC<{x: number; y: number; w?: number}> = ({x, y, w = 120}) => (
  <div style={{position: 'absolute', left: x, top: y, width: w, height: 34, background: 'rgba(236,228,206,0.74)'}} />
);
// 剪报：撕边、纸纹、一条胶带
const Clip: React.FC<{x: number; y: number; w: number; h: number; seed: number; on?: boolean}> = ({x, y, w, h, seed, on = true}) => (
  <>
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, backgroundColor: K.clip, backgroundImage: CLIP_BG,
      clipPath: torn(w, h, seed), opacity: on ? 1 : 0.86}} />
    <Tape x={x + w * 0.42} y={y - 16} />
  </>
);
// 黑底白字标签条（Borders 式）
const Lab: React.FC<{text: string; size?: number; style?: React.CSSProperties}> = ({text, size = 24, style}) => (
  <div style={{position: 'absolute', background: K.ink, color: '#EEEAE2', fontFamily: F.sans, fontWeight: 600, fontSize: size, letterSpacing: '0.14em',
    padding: '8px 16px 10px', whiteSpace: 'nowrap', ...style}}>{text}</div>
);
// 手画红圈：略不闭合、描线随 p 画出
const ring = (w: number, h: number) => {
  const pts: string[] = [];
  const n = 90, cx = w / 2, cy = h / 2, rx = w / 2 - 6, ry = h / 2 - 6;
  for (let i = 0; i <= n * 1.12; i++) {
    const t = (i / n) * Math.PI * 2 - 0.6;
    const k = 1 + 0.05 * Math.sin(3 * t + 0.7) + (i / n) * 0.04;
    pts.push(`${(cx + rx * k * Math.cos(t)).toFixed(1)} ${(cy + ry * k * Math.sin(t)).toFixed(1)}`);
  }
  return 'M' + pts.join(' L');
};
const Circle: React.FC<{x: number; y: number; w: number; h: number; p: number}> = ({x, y, w, h, p}) => (
  <svg width={w} height={h} style={{position: 'absolute', left: x, top: y, overflow: 'visible'}}>
    <path d={ring(w, h)} fill="none" stroke={K.red} strokeWidth={6} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} opacity={0.92} />
  </svg>
);

const Under: React.FC = () => (
  <>
    <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: FOOT, backgroundColor: K.desk, backgroundImage: DESK_BG}} />
    {FOOTER === 'plate' ? <div style={{position: 'absolute', left: 0, top: FOOT, width: 1080, height: 1920 - FOOT, background: K.foot}} /> : null}
  </>
);
const WIN_CLIP = torn(WIN.w, WIN.h, 11, 9, 18);
const Over: React.FC = () => (<><Tape x={60} y={WIN.y - 14} w={130} /><Tape x={890} y={WIN.y - 12} w={130} /></>);

const Masthead: React.FC<{f: number; series: string; episode: string; end: any; coverEnd?: number}> = ({f, series, episode, end, coverEnd = 0}) => {
  const nxt = end && f >= end.from;
  const r = coverEnd ? wipe(f - coverEnd, 0, 8) : 0;
  const hide = f < coverEnd;
  const title = nxt ? String(end.line).replace(/\n/g, '，') : episode;
  return (
    <>
      <Lab text={nxt ? end.kicker : series} style={{left: 72, top: 172}} />
      {hide ? null : (
        <div style={{position: 'absolute', left: 72, right: 72, top: 226, fontFamily: F.serif, fontWeight: 900, fontSize: fitSize(title, 936, nxt ? 48 : 62, 40),
          lineHeight: 1.1, color: K.ink, whiteSpace: 'nowrap', clipPath: `inset(-10% ${nxt ? wipe(f - end.from, 4, 10) : r}% -10% 0)`}}>
          <Mixed t={title} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.06em'}} />
        </div>
      )}

      {/* 报尾：左品牌、右日期，不加分隔线、不加进度底轨（10-27 用户意见，六套统一） */}
      <div style={{position: 'absolute', left: 72, top: COL_Y, fontFamily: F.sans, fontWeight: 500, fontSize: 20,
        letterSpacing: '0.14em', color: 'rgba(27,27,26,0.55)'}}>{FOOT_L}</div>
      <div style={{position: 'absolute', right: 72, top: COL_Y + 2}}>
        <span style={{fontFamily: F.sans, fontSize: 20, color: 'rgba(27,27,26,0.48)', letterSpacing: '0.08em'}}>{FOOT_R}</span>
      </div>

    </>
  );
};

// 字幕：桌面上的墨字；关键词说到时荧光笔从左扫过去（色块层 scaleX，字不动）
const Caption: React.FC<{cap: Cap; f: number}> = ({cap, f}) => (
  <div style={{position: 'absolute', left: 72, right: 132, top: SEAM + 34}}>
    {cap.lines.map((l: any, i: number) => {
      if (f < l.from && !(cap.animate && i === 0)) return null;
      const r = cap.animate && i === 0 ? wipe(f - cap.from, 0, 4) : 0;
      const parts: React.ReactNode[] = [];
      let k = 0;
      const rs = (l.hl || []).map((h: [number, number], j: number) => ({a: h[0], b: h[1], at: (l.hlAt || [])[j] ?? l.from})).sort((x: any, y: any) => x.a - y.a);
      rs.forEach((h: any, j: number) => {
        if (h.a < k) return;
        if (h.a > k) parts.push(<span key={'n' + j}>{l.text.slice(k, h.a)}</span>);
        const p = prog(f - h.at, 0, 6);
        parts.push(
          <span key={'h' + j} style={{position: 'relative', fontWeight: 600}}>
            <span style={{position: 'absolute', left: -3, right: -3, top: '18%', bottom: '6%', background: K.hl, mixBlendMode: 'multiply',
              transform: `scaleX(${p})`, transformOrigin: '0% 50%'}} />
            <span style={{position: 'relative'}}>{l.text.slice(h.a, h.b)}</span>
          </span>
        );
        k = h.b;
      });
      if (k < l.text.length) parts.push(<span key="t">{l.text.slice(k)}</span>);
      return (
        <div key={i} style={{fontFamily: F.sans, fontWeight: 400, fontSize: 56, lineHeight: 1.3, color: K.ink, whiteSpace: 'nowrap',
          clipPath: `inset(-10% ${r}% -20% 0)`}}>{parts}</div>
      );
    })}
  </div>
);

const NameTag: React.FC<{f: number; d: any}> = ({f, d}) => {
  const local = f - d.from;
  if (local < 0 || f >= d.to) return null;
  const up = prog(local, 0, 8) - prog(local, d.to - d.from - 6, d.to - d.from, ease.in);
  return (
    <div style={{position: 'absolute', left: 72, top: SEAM - 150 - 14, clipPath: `inset(${(1 - up) * 100}% 0 0 0)`}}>
      <div style={{background: K.ink, padding: '16px 30px 18px 24px'}}>
        <div style={{fontFamily: F.serif, fontWeight: 900, fontSize: 40, color: '#F3EFE6', whiteSpace: 'nowrap'}}>{d.name}</div>
        <div style={{marginTop: 6, fontFamily: F.sans, fontWeight: 400, fontSize: 24, letterSpacing: '0.12em', color: 'rgba(243,239,230,0.75)', whiteSpace: 'nowrap'}}>
          {(d.lines || []).join('　·　')}
        </div>
      </div>
    </div>
  );
};

const Tag: React.FC<{f: number; t: any}> = ({f, t}) => {
  const d = prog(f - t.from, 0, 7);
  const ln = prog(f - t.from, 6, 18);
  const pt = t.point;
  const x0 = 72 + 40, y0 = WIN.y + 66;
  const x1 = pt ? pt[0] * WIN.w : 0, y1 = pt ? WIN.y + pt[1] * WIN.h : 0;
  const len = pt ? Math.hypot(x1 - x0, y1 - y0) : 0;
  return (
    <>
      {pt ? (
        <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0}}>
          <line x1={x0} y1={y0} x2={x1} y2={y1} stroke={K.red} strokeWidth={4} strokeLinecap="round" strokeDasharray={len} strokeDashoffset={(1 - ln) * len} />
        </svg>
      ) : null}
      {pt ? <Circle x={x1 - 34} y={y1 - 34} w={68} h={68} p={prog(f - t.from, 16, 26)} /> : null}
      <div style={{position: 'absolute', left: 72, top: WIN.y + 30, clipPath: `inset(0 ${(1 - d) * 100}% 0 0)`}}>
        <Lab text={t.text} size={26} style={{position: 'relative'}} />
      </div>
    </>
  );
};

const Label: React.FC<{f: number; from: number; text: string}> = ({f, from, text}) => {
  const d = prog(f - from, 2, 9);
  return (
    <div style={{position: 'absolute', right: 64, top: WIN.y + 28, opacity: d}}>
      <div style={{background: K.clip, backgroundImage: CLIP_BG, padding: '8px 16px 10px', fontFamily: F.sans, fontWeight: 500, fontSize: 22, letterSpacing: '0.12em',
        color: K.mute, whiteSpace: 'nowrap'}}>{text}</div>
    </div>
  );
};
const SplitLabels: React.FC<{f: number; at: number; labels: string[]}> = ({f, at, labels}) => (
  <>{labels.map((l, i) => (
    <div key={i} style={{position: 'absolute', left: i === 0 ? 72 : 580, top: WIN.y + 90, clipPath: `inset(0 ${wipe(f - at - (i === 0 ? 2 : 8), 0, 7)}% 0 0)`}}>
      <Lab text={l} size={28} style={{position: 'relative', letterSpacing: '0.3em'}} />
    </div>
  ))}</>
);

// 封面：画面窗下半压一张大剪报（标题宋体＋红色手画下划线）；其它形式同样放在剪报上
const Cover: React.FC<{f: number; d: any}> = ({f, d}) => {
  if (f >= d.frames) return null;
  const form = d.form && d.form !== 'title';
  const y = WIN.y + 600, h = 460;
  return (
    <>
      <Clip x={54} y={y} w={940} h={h} seed={5} />
      {d.kicker ? <Lab text={d.kicker} size={22} style={{left: 100, top: y + 36}} /> : null}
      <div style={{position: 'absolute', left: 100, top: y + 96, width: 850}}>
        {form ? <CoverForm d={{...d, kicker: ''}} t={{ink: K.ink, soft: K.mute, accent: K.red, numFont: F.didot, numWeight: 700, titleFont: F.serif, w: 850, numMax: 220}} />
          : (d.title || []).map((t: string, i: number) => (
            <div key={i} style={{fontFamily: F.serif, fontWeight: 900, fontSize: fitSize(t, 850, 108, 70), lineHeight: 1.14, color: K.ink, whiteSpace: 'nowrap'}}>
              {t.split(/(□)/).map((part, j) => part === '□'
                ? <span key={j} style={{display: 'inline-block', width: '0.86em', height: '0.86em', margin: '0 0.06em', verticalAlign: '-0.08em',
                    border: `5px solid ${K.red}`, boxSizing: 'border-box'}} />
                : <Mixed key={j} t={part} num={{fontFamily: F.didot, fontWeight: 700, fontSize: '1.08em', color: K.red}} />)}
            </div>
          ))}
      </div>
      {!form ? (
        <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0}}>
          <path d={`M 104 ${y + h - 64} C 300 ${y + h - 78}, 560 ${y + h - 52}, 760 ${y + h - 70}`} fill="none" stroke={K.red} strokeWidth={6} strokeLinecap="round"
            pathLength={1} strokeDasharray={1} strokeDashoffset={1 - prog(f, 10, 26)} />
        </svg>
      ) : null}
    </>
  );
};

// 大字卡：虚化的她上面压一张剪报，数字是红的
const Figure: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <>
    <div style={{position: 'absolute', left: 0, top: 0, width: WIN.w, height: WIN.h, clipPath: `inset(0 0 ${wipe(f - s.from, 0, 6)}% 0)`}}>
      <Clip x={80} y={330} w={920} h={660} seed={s.from} />
    </div>
    <FigureCore f={f} s={s} win={WIN} top={420} label={K.mute} value={K.red} word={K.ink} box={K.ink} />
  </>
);
const Photo: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhotoCore f={f} s={s} win={WIN} credit={K.mute} />;

const PHONE = {x: 290, y: 60, w: 500, h: 980, r: 60, bezel: 14, k: 0.92, faceY: 0.4, color: K.clip};
const PhoneFrame: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhoneFrameCore f={f} s={s} win={WIN} ph={PHONE} />;

const DeskBg: React.FC = () => <div style={{position: 'absolute', inset: 0, backgroundColor: K.desk, backgroundImage: DESK_BG}} />;
const INFO: InfoStyle = {
  area: {x: 70, y: 70, w: 940, h: 730}, ink: K.ink, mute: K.mute, accent: K.red, accent2: '#A79E90', card: K.clip,
  mark: 'marker', titleFont: F.serif, titleWeight: 900, numFont: F.didot, numWeight: 700, radius: 0, pad: 44, gap: 36,
  presenter: {mode: 'polaroid', rect: {x: 770, y: 840, w: 250, h: 230}, border: `10px solid ${K.clip}`},
  Surface: Clip, WindowBg: DeskBg, Circle, areaCard: ['timeline', 'chart'],
};
const Info: React.FC<{f: number; s: Shot; face: any; src: string}> = (p) => <InfoCore {...p} st={INFO} />;

export const evidence = {
  name: 'evidence', win: WIN, faceY: 0.47, canvas: K.desk, under: true, winClip: WIN_CLIP, Info, info: INFO,
  Under, Over, Masthead, Caption, NameTag, EndCard: null as any, Tag, Cover, Figure, Photo, SplitLabels, Label, PhoneFrame,
  phone: PHONE, phonePush: phonePushK, coverInWindow: true, halftone: 0.18, seam: K.clip,
};
