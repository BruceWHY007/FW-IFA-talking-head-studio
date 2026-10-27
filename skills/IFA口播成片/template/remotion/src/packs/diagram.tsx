// 风格包 K2 · 图解 —— 瑞士网格＋财经图表语法（huashu-art-motion t3：先坐标、再数据、最后只标一件事；柱从 0 起）
// 与 Signal Proof 证据层：浅灰底、竖向网格线、墨色细规线、单一强调色、等宽字的图号与来源。
// 适合：数字、对比、走势、清单——观众会截图较真的内容。数据镜头里她进右下角的讲解框，嘴型不断。
// 强调色：账号指定了主题就用主题的纸上强调色，没指定用本包的信号蓝。
import React from 'react';
import {Cap, Shot, prog, wipe} from './common';
import {FigureCore, PhotoCore, Mixed, CoverForm, PhoneFrameCore, phonePushK, fitSize} from './parts';
import {InfoCore, InfoStyle} from './info';
import {F, TH, ease} from '../theme';
import tlRaw from '../timeline.json';

const ACC = TH.custom ? TH.accent : '#2F5EA7';
const K = {bg: '#F4F5F7', sur: '#FFFFFF', ink: '#15181D', mute: '#6C7580', line: '#DCE3EE', acc: ACC, grey: '#AEB6C1', foot: TH.custom ? TH.foot : '#15181D'};
const WIN = {x: 0, y: 320, w: 1080, h: 1100};
const SEAM = WIN.y + WIN.h; // 1420
const FOOT = 1760;
const DUR = Number((tlRaw as any).durationInFrames || 0);
const ACCT = String((tlRaw as any).account || '');
const FOOT_L = String((tlRaw as any).footer_left || '复星财富IFA');
const FOOT_R = String((tlRaw as any).footer_right || '');
const FOOTER = String((tlRaw as any).footer || 'paper') as 'plate' | 'paper';
const COL_Y = FOOTER === 'paper' ? 1812 : 1712;
const BAR_Y = FOOTER === 'paper' ? 1902 : FOOT - 2;
const HELV = '"Helvetica Neue", Helvetica, Arial, sans-serif';
const MONO = '"SF Mono", Menlo, monospace';

const GRID: React.CSSProperties = {backgroundImage: `linear-gradient(90deg, ${K.line} 1px, transparent 1px)`, backgroundSize: '90px 100%'};
const Under: React.FC = () => (
  <>
    <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: SEAM, background: K.bg}} />
    <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: SEAM, ...GRID, opacity: 0.55}} />
    <div style={{position: 'absolute', left: 0, top: SEAM, width: 1080, height: FOOT - SEAM, background: K.sur}} />
    {FOOTER === 'plate' ? <div style={{position: 'absolute', left: 0, top: FOOT, width: 1080, height: 1920 - FOOT, background: K.foot}} /> : null}
  </>
);
const Over: React.FC = () => <div style={{position: 'absolute', left: 0, top: SEAM - 1 - 14, width: 1080, height: 3, background: K.ink}} />;

const Masthead: React.FC<{f: number; series: string; episode: string; end: any; coverEnd?: number}> = ({f, series, episode, end, coverEnd = 0}) => {
  const nxt = end && f >= end.from;
  const title = nxt ? String(end.line).replace(/\n/g, '，') : episode;
  const r = nxt ? wipe(f - end.from, 4, 10) : coverEnd ? wipe(f - coverEnd, 0, 8) : 0;
  if (f < coverEnd) return null;  // 封面自带图号行，刊头等封面收掉再出
  return (
    <>
      <div style={{position: 'absolute', left: 72, right: 72, top: 176, display: 'flex', justifyContent: 'space-between', fontFamily: MONO, fontSize: 21,
        letterSpacing: '0.12em', color: K.mute}}>
        <span>{nxt ? 'NEXT · ' + end.kicker : 'FIG · ' + series}</span><span>No.01</span>
      </div>
      {f < coverEnd ? null : (
        <div style={{position: 'absolute', left: 72, right: 72, top: 222, fontFamily: F.sans, fontWeight: 600, fontSize: fitSize(title, 936, 58, 40), lineHeight: 1.15,
          color: K.ink, whiteSpace: 'nowrap', clipPath: `inset(-10% ${r}% -10% 0)`}}>
          <Mixed t={title} num={{fontFamily: HELV, fontWeight: 700, color: K.acc}} />
        </div>
      )}

      {/* 报尾：左品牌、右日期，不加分隔线、不加进度底轨（10-27 用户意见，六套统一） */}
      <div style={{position: 'absolute', left: 72, top: COL_Y, fontFamily: F.sans, fontWeight: 500, fontSize: 20,
        letterSpacing: '0.14em', color: 'rgba(21,24,29,0.55)'}}>{FOOT_L}</div>
      <div style={{position: 'absolute', right: 72, top: COL_Y + 2}}>
        <span style={{fontFamily: F.sans, fontSize: 20, color: 'rgba(21,24,29,0.48)', letterSpacing: '0.08em'}}>{FOOT_R}</span>
      </div>

    </>
  );
};

// 字幕：白色字幕带里的墨字；关键词换强调色、下面画一道 5px 规线
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
        const on = prog(f - h.at, 0, 3), ln = prog(f - h.at, 1, 8);
        parts.push(
          <span key={'h' + j} style={{position: 'relative', color: on > 0.5 ? K.acc : K.ink, fontWeight: on > 0.5 ? 600 : 400}}>{l.text.slice(h.a, h.b)}
            <span style={{position: 'absolute', left: 0, right: 0, bottom: -4, height: 5, background: K.acc, transform: `scaleX(${ln})`, transformOrigin: '0% 50%'}} />
          </span>
        );
        k = h.b;
      });
      if (k < l.text.length) parts.push(<span key="t">{l.text.slice(k)}</span>);
      return <div key={i} style={{fontFamily: F.sans, fontWeight: 400, fontSize: 56, lineHeight: 1.3, color: K.ink, whiteSpace: 'nowrap',
        clipPath: `inset(-10% ${r}% -20% 0)`}}>{parts}</div>;
    })}
  </div>
);

const NameTag: React.FC<{f: number; d: any}> = ({f, d}) => {
  const local = f - d.from;
  if (local < 0 || f >= d.to) return null;
  const up = prog(local, 0, 8) - prog(local, d.to - d.from - 6, d.to - d.from, ease.in);
  return (
    <div style={{position: 'absolute', left: 72, top: SEAM - 140 - 14, clipPath: `inset(0 ${(1 - up) * 100}% 0 0)`}}>
      <div style={{background: K.sur, padding: '18px 30px 18px 34px', borderLeft: `10px solid ${K.acc}`}}>
        <div style={{fontFamily: F.sans, fontWeight: 600, fontSize: 42, color: K.ink, whiteSpace: 'nowrap'}}>{d.name}</div>
        <div style={{marginTop: 4, fontFamily: MONO, fontSize: 21, letterSpacing: '0.08em', color: K.mute, whiteSpace: 'nowrap'}}>{(d.lines || []).join('  /  ')}</div>
      </div>
    </div>
  );
};

const Chip: React.FC<{text: string; style?: React.CSSProperties; mono?: boolean}> = ({text, style, mono}) => (
  <div style={{position: 'absolute', background: K.sur, padding: '9px 16px 10px', fontFamily: mono ? MONO : F.sans, fontWeight: mono ? 400 : 600, fontSize: mono ? 21 : 26,
    letterSpacing: '0.1em', color: K.ink, whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 12, ...style}}>
    <span style={{width: 12, height: 12, background: K.acc}} />{text}
  </div>
);
const Tag: React.FC<{f: number; t: any}> = ({f, t}) => {
  const d = prog(f - t.from, 0, 7), ln = prog(f - t.from, 6, 18);
  const pt = t.point;
  const x0 = 100, y0 = WIN.y + 80, x1 = pt ? pt[0] * WIN.w : 0, y1 = pt ? WIN.y + pt[1] * WIN.h : 0;
  const len = pt ? Math.hypot(x1 - x0, y1 - y0) : 0;
  return (
    <>
      {pt ? (
        <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0}}>
          <line x1={x0} y1={y0} x2={x1} y2={y1} stroke="#fff" strokeWidth={6} strokeDasharray={len} strokeDashoffset={(1 - ln) * len} />
          <line x1={x0} y1={y0} x2={x1} y2={y1} stroke={K.ink} strokeWidth={2} strokeDasharray={len} strokeDashoffset={(1 - ln) * len} />
          <rect x={x1 - 9} y={y1 - 9} width={18} height={18} fill={K.acc} stroke="#fff" strokeWidth={3} opacity={prog(f - t.from, 16, 22)} />
        </svg>
      ) : null}
      <div style={{position: 'absolute', left: 72, top: WIN.y + 30, clipPath: `inset(0 ${(1 - d) * 100}% 0 0)`, width: 900, height: 60}}>
        <Chip text={t.text} style={{left: 0, top: 0}} />
      </div>
    </>
  );
};
const Label: React.FC<{f: number; from: number; text: string}> = ({f, from, text}) => (
  <div style={{position: 'absolute', right: 72, top: WIN.y + 28, opacity: prog(f - from, 2, 9)}}>
    <div style={{background: K.sur, padding: '7px 14px 8px', fontFamily: MONO, fontSize: 20, letterSpacing: '0.08em', color: K.mute, whiteSpace: 'nowrap'}}>{text}</div>
  </div>
);
const SplitLabels: React.FC<{f: number; at: number; labels: string[]}> = ({f, at, labels}) => (
  <>{labels.map((l, i) => (
    <div key={i} style={{position: 'absolute', left: i === 0 ? 72 : 580, top: WIN.y + 96, width: 400, height: 60,
      clipPath: `inset(0 ${wipe(f - at - (i === 0 ? 2 : 8), 0, 7)}% 0 0)`}}><Chip text={l} style={{left: 0, top: 0, letterSpacing: '0.24em'}} /></div>
  ))}</>
);

// 封面：上方一块浅灰板（盖住画面窗上部）放大标题，墨色粗规线收住，下面露出她
const Cover: React.FC<{f: number; d: any}> = ({f, d}) => {
  if (f >= d.frames) return null;
  const form = d.form && d.form !== 'title';
  const lines: string[] = d.title || [];
  return (
    <>
      <div style={{position: 'absolute', left: 0, top: 160, width: 1080, height: form ? 640 : 560, background: K.bg}} />
      <div style={{position: 'absolute', left: 0, top: 160, width: 1080, height: form ? 640 : 560, ...GRID, opacity: 0.55}} />
      <div style={{position: 'absolute', left: 72, top: 176, fontFamily: MONO, fontSize: 21, letterSpacing: '0.12em', color: K.mute}}>{'FIG.00 · ' + (d.kicker || '')}</div>
      <div style={{position: 'absolute', left: 72, top: 226, width: 936}}>
        {form ? <CoverForm d={{...d, kicker: ''}} t={{ink: K.ink, soft: K.mute, accent: K.acc, numFont: HELV, numWeight: 700, titleFont: F.sans, w: 936}} />
          : lines.map((t, i) => (
            <div key={i} style={{fontFamily: F.sans, fontWeight: 600, fontSize: fitSize(t, 936, 120, 76), lineHeight: 1.1, letterSpacing: '-0.02em', whiteSpace: 'nowrap',
              color: i === lines.length - 1 ? K.acc : K.ink}}>
              {t.split(/(□)/).map((part, j) => part === '□'
                ? <span key={j} style={{display: 'inline-block', width: '0.84em', height: '0.84em', margin: '0 0.05em', verticalAlign: '-0.08em',
                    border: `6px solid ${K.acc}`, boxSizing: 'border-box'}} />
                : <Mixed key={j} t={part} num={{fontFamily: HELV, fontWeight: 700}} />)}
            </div>
          ))}
      </div>
      <div style={{position: 'absolute', left: 72, top: (form ? 800 : 720) - 8, width: 936, height: 5, background: K.ink, transform: `scaleX(${prog(f, 4, 18)})`,
        transformOrigin: '0% 50%'}} />
    </>
  );
};

const Figure: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <>
    <div style={{position: 'absolute', left: 72, top: 330, width: 936, height: 640, background: K.sur, borderTop: `5px solid ${K.ink}`,
      clipPath: `inset(0 0 ${wipe(f - s.from, 0, 6)}% 0)`}} />
    <FigureCore f={f} s={s} win={WIN} top={420} label={K.mute} value={K.acc} word={K.ink} box={K.ink} numFont={HELV} wordFont={F.sans} />
  </>
);
const Photo: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhotoCore f={f} s={s} win={WIN} credit={K.mute} />;
const PHONE = {x: 290, y: 60, w: 500, h: 980, r: 60, bezel: 14, k: 0.92, faceY: 0.4, color: K.sur};
const PhoneFrame: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhoneFrameCore f={f} s={s} win={WIN} ph={PHONE} />;

const Panel: React.FC<{x: number; y: number; w: number; h: number}> = ({x, y, w, h}) => (
  <div style={{position: 'absolute', left: x, top: y, width: w, height: h, background: K.sur, borderTop: `5px solid ${K.ink}`}} />
);
const GridBg: React.FC = () => (<><div style={{position: 'absolute', inset: 0, background: K.bg}} /><div style={{position: 'absolute', inset: 0, ...GRID, opacity: 0.55}} /></>);
const INFO: InfoStyle = {
  area: {x: 112, y: 96, w: 856, h: 560}, ink: K.ink, mute: K.mute, accent: K.acc, accent2: K.grey, card: K.sur,
  mark: 'underline', titleFont: F.sans, titleWeight: 600, numFont: HELV, numWeight: 700, radius: 0, pad: 40, gap: 28,
  presenter: {mode: 'box', rect: {x: 628, y: 712, w: 380, h: 370}, topBar: K.acc},
  Surface: Panel, WindowBg: GridBg, areaCard: ['quote', 'compare', 'list', 'timeline', 'chart'],
};
const Info: React.FC<{f: number; s: Shot; face: any; src: string}> = (p) => <InfoCore {...p} st={INFO} />;

export const diagram = {
  name: 'diagram', win: WIN, faceY: 0.47, coverFaceY: 0.74, canvas: K.bg, under: true, Info, info: INFO,
  Under, Over, Masthead, Caption, NameTag, EndCard: null as any, Tag, Cover, Figure, Photo, SplitLabels, Label, PhoneFrame,
  phone: PHONE, phonePush: phonePushK, coverInWindow: true, halftone: 0, seam: K.sur,
};
