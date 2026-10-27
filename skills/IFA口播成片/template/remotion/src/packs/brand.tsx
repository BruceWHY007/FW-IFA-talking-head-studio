// 风格包 K3 · IFA 品牌刊 —— 和 skill「IFA图文卡」（小红书模板，10-09《走进安盛》定稿）是同一套：
// 蜜桃到奶白的渐变底、左上角复星财富理财师 logo、宋体标题配橙色强调、白色圆角面板、浅橙小标签。
// 人脸画面是一张圆角卡；数据镜头里她缩成右下角的圆形小窗。跨平台一眼认出是复星 IFA。
// 品牌色是这套风格本身，不跟账号主题变（账号主题只给 A／B／C／K2 用）。
import React from 'react';
import {Img, staticFile} from 'remotion';
import {Cap, Shot, prog, wipe} from './common';
import {FigureCore, PhotoCore, Mixed, CoverForm, PhoneFrameCore, phonePushK, fitSize} from './parts';
import {InfoCore, InfoStyle} from './info';
import {F, ease} from '../theme';

const K = {ink: '#1d1611', ink2: '#4a3b31', ink3: '#8a786b', org: '#df5f1e', orgText: '#B5481A', chip: '#fce3cd', chip2: '#fff4ea', foot: '#1d1611',
  panel: '#FFFFFF', edge: 'rgba(223,95,30,0.18)'};
const WIN = {x: 72, y: 280, w: 936, h: 1120};
const SEAM = WIN.y + WIN.h; // 1400
const FOOT = 1600;
const GRAD = 'radial-gradient(95% 62% at 0% 0%, #eeb184 0%, rgba(241,190,146,.85) 28%, rgba(246,214,184,.55) 52%, rgba(250,236,222,0) 78%),' +
  'linear-gradient(180deg, #f4caa3 0%, #f8dfc6 22%, #fcefe2 42%, #fdf8f2 60%, #fcfbf8 100%)';

const Under: React.FC = () => (
  <>
    <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: FOOT, background: GRAD}} />
    <div style={{position: 'absolute', left: 0, top: FOOT, width: 1080, height: 1920 - FOOT, background: K.foot}} />
  </>
);
const ChipEl: React.FC<{text: string; style?: React.CSSProperties; big?: boolean}> = ({text, style, big}) => (
  <div style={{position: 'absolute', background: K.chip, color: K.ink2, fontFamily: F.sans, fontWeight: 500, fontSize: big ? 28 : 24, letterSpacing: '0.12em',
    padding: big ? '8px 20px 9px' : '6px 16px 7px', borderRadius: 28, whiteSpace: 'nowrap', ...style}}>{text}</div>
);
// 刊头：logo＋右上角栏目签。下期预告时栏目签换成「下期预告」
const Masthead: React.FC<{f: number; series: string; episode: string; end: any}> = ({f, series, end}) => {
  const nxt = end && f >= end.from;
  return (
    <>
      <Img src={staticFile('brand/logo.png')} style={{position: 'absolute', left: 72, top: 186, height: 56}} />
      <ChipEl text={nxt ? end.kicker : series} style={{right: 72, top: 194}} />
    </>
  );
};

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
        const on = prog(f - h.at, 0, 3);
        parts.push(<span key={'h' + j} style={{color: on > 0.5 ? K.orgText : K.ink, fontWeight: on > 0.5 ? 600 : 400}}>{l.text.slice(h.a, h.b)}</span>);
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
    <div style={{position: 'absolute', left: 104, top: SEAM - 170, clipPath: `inset(${(1 - up) * 100}% 0 0 0 round 24px)`}}>
      <div style={{background: K.panel, borderRadius: 24, padding: '20px 30px 22px', border: `1.5px solid ${K.edge}`}}>
        <div style={{fontFamily: F.serif, fontWeight: 900, fontSize: 42, color: K.ink, whiteSpace: 'nowrap'}}>{d.name}</div>
        <div style={{marginTop: 10, display: 'flex', gap: 10}}>
          {(d.lines || []).map((l: string, i: number) => <span key={i} style={{background: K.chip2, color: K.ink2, fontFamily: F.sans, fontSize: 22,
            letterSpacing: '0.1em', padding: '5px 14px', borderRadius: 20, whiteSpace: 'nowrap'}}>{l}</span>)}
        </div>
      </div>
    </div>
  );
};

const Tag: React.FC<{f: number; t: any}> = ({f, t}) => {
  const d = prog(f - t.from, 0, 7), ln = prog(f - t.from, 6, 18);
  const pt = t.point;
  const x0 = WIN.x + 60, y0 = WIN.y + 86, x1 = pt ? WIN.x + pt[0] * WIN.w : 0, y1 = pt ? WIN.y + pt[1] * WIN.h : 0;
  const len = pt ? Math.hypot(x1 - x0, y1 - y0) : 0;
  return (
    <>
      {pt ? (
        <svg width={1080} height={1920} style={{position: 'absolute', left: 0, top: 0}}>
          <line x1={x0} y1={y0} x2={x1} y2={y1} stroke="#fff" strokeWidth={6} strokeDasharray={len} strokeDashoffset={(1 - ln) * len} />
          <line x1={x0} y1={y0} x2={x1} y2={y1} stroke={K.org} strokeWidth={2.5} strokeDasharray={len} strokeDashoffset={(1 - ln) * len} />
          <circle cx={x1} cy={y1} r={10} fill={K.org} stroke="#fff" strokeWidth={4} opacity={prog(f - t.from, 16, 22)} />
        </svg>
      ) : null}
      <div style={{position: 'absolute', left: WIN.x + 28, top: WIN.y + 30, opacity: d}}>
        <div style={{background: K.panel, borderRadius: 28, padding: '9px 20px 10px', display: 'flex', alignItems: 'center', gap: 10, fontFamily: F.sans,
          fontWeight: 500, fontSize: 26, letterSpacing: '0.12em', color: K.ink, whiteSpace: 'nowrap'}}>
          <span style={{width: 12, height: 12, borderRadius: 12, background: K.org}} />{t.text}
        </div>
      </div>
    </>
  );
};
const Label: React.FC<{f: number; from: number; text: string}> = ({f, from, text}) => (
  <div style={{position: 'absolute', right: 104, top: WIN.y + 30, opacity: prog(f - from, 2, 9), background: 'rgba(255,255,255,0.9)', borderRadius: 20,
    padding: '6px 16px 7px', fontFamily: F.sans, fontWeight: 500, fontSize: 22, letterSpacing: '0.1em', color: K.ink3, whiteSpace: 'nowrap'}}>{text}</div>
);
const SplitLabels: React.FC<{f: number; at: number; labels: string[]}> = ({f, at, labels}) => (
  <>{labels.map((l, i) => <ChipEl key={i} big text={l} style={{left: i === 0 ? WIN.x + 28 : 540 + 28, top: WIN.y + 96, opacity: prog(f - at - (i === 0 ? 2 : 8), 0, 7),
    letterSpacing: '0.28em', background: K.panel}} />)}</>
);

// 封面：人脸卡下半压一张白色圆角面板，宋体大标题、最后一行橙色（与图文卡封面同一个写法）
const Cover: React.FC<{f: number; d: any}> = ({f, d}) => {
  if (f >= d.frames) return null;
  const form = d.form && d.form !== 'title';
  const lines: string[] = d.title || [];
  const y = form ? 860 : 940;
  return (
    <div style={{position: 'absolute', left: 104, top: y, width: 872, height: SEAM - y - 34, background: K.panel, borderRadius: 32, border: `1.5px solid ${K.edge}`,
      padding: '34px 40px', boxSizing: 'border-box'}}>
      {d.kicker ? <div style={{fontFamily: F.serif, fontWeight: 600, fontSize: 38, color: K.ink2}}>{d.kicker}</div> : null}
      {form ? <div style={{marginTop: 10}}><CoverForm d={{...d, kicker: ''}} t={{ink: K.ink, soft: K.ink3, accent: K.orgText, numFont: F.didot, numWeight: 700, titleFont: F.serif, w: 792}} /></div>
        : lines.map((t, i) => (
          <div key={i} style={{marginTop: i === 0 ? 8 : 0, fontFamily: F.serif, fontWeight: 900, fontSize: fitSize(t, 792, 104, 66), lineHeight: 1.16, whiteSpace: 'nowrap',
            color: i === lines.length - 1 ? K.orgText : K.ink}}>
            {t.split(/(□)/).map((part, j) => part === '□'
              ? <span key={j} style={{display: 'inline-block', width: '0.86em', height: '0.86em', margin: '0 0.06em', verticalAlign: '-0.08em',
                  border: `5px solid ${K.org}`, borderRadius: 10, boxSizing: 'border-box'}} />
              : <Mixed key={j} t={part} num={{fontFamily: F.didot, fontWeight: 700, fontSize: '1.08em'}} />)}
          </div>
        ))}
    </div>
  );
};

const Figure: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <>
    <div style={{position: 'absolute', left: 40, top: 300, width: 856, height: 660, background: K.panel, borderRadius: 32, border: `1.5px solid ${K.edge}`,
      clipPath: `inset(0 0 ${wipe(f - s.from, 0, 6)}% 0 round 32px)`}} />
    <FigureCore f={f} s={s} win={WIN} top={390} label={K.ink3} value={K.orgText} word={K.ink} box={K.org} />
  </>
);
const Photo: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhotoCore f={f} s={s} win={WIN} credit={K.ink3} />;
const PHONE = {x: 218, y: 60, w: 500, h: 980, r: 60, bezel: 14, k: 0.92, faceY: 0.4, color: '#FFFFFF'};
const PhoneFrame: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhoneFrameCore f={f} s={s} win={WIN} ph={PHONE} />;

const Panel: React.FC<{x: number; y: number; w: number; h: number; on?: boolean}> = ({x, y, w, h, on = true}) => (
  <div style={{position: 'absolute', left: x, top: y, width: w, height: h, background: on ? K.panel : 'rgba(255,255,255,0.7)', borderRadius: 28, border: `1.5px solid ${K.edge}`}} />
);
const CardBg: React.FC = () => <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, #FBEADB 0%, #FDF6EF 55%, #FCFAF6 100%)'}} />;
const INFO: InfoStyle = {
  area: {x: 40, y: 60, w: 856, h: 800}, ink: K.ink, mute: K.ink3, accent: K.orgText, accent2: '#E8C9B1', card: K.panel,
  mark: 'color', titleFont: F.serif, titleWeight: 900, numFont: F.didot, numWeight: 700, radius: 28, pad: 40, gap: 24,
  presenter: {mode: 'pip', rect: {x: 936 - 40 - 220, y: 1120 - 40 - 220, w: 220, h: 220}, radius: 110, border: '6px solid #FFFFFF'},
  Surface: Panel, WindowBg: CardBg, areaCard: ['quote', 'timeline', 'chart'],
};
const Info: React.FC<{f: number; s: Shot; face: any; src: string}> = (p) => <InfoCore {...p} st={INFO} />;

export const brand = {
  name: 'brand', win: WIN, faceY: 0.47, canvas: '#fcfbf8', under: true, winRadius: 40, Info, info: INFO,
  Under, Over: null as any, Masthead, Caption, NameTag, EndCard: null as any, Tag, Cover, Figure, Photo, SplitLabels, Label, PhoneFrame,
  phone: PHONE, phonePush: phonePushK, coverInWindow: true, halftone: 0, seam: '#FFFFFF',
};
