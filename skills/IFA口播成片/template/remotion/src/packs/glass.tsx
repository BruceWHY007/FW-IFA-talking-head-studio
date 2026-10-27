// 风格包 B · 雾金玻璃 —— 借自雾金宣传片与《虚位以待》：满幅画面，底部一层雾把画面渐隐成可读的字区，
// 刊头、名字条、标注是液态玻璃浮层（亮上缘＋同色细边＋背景模糊），字幕不加底条，靠雾托住。
// 比雾金片好在：玻璃只给「栏目」与「人物」两类信息，字幕回到雾上，不再满屏玻璃卡。
import React from 'react';
import {interpolate} from 'remotion';
import {Cap, Shot, Spans, prog, wipe} from './common';
import {FigureCore, PhotoCore, Mixed, CoverForm, PhoneFrameCore, phonePushK} from './parts';
import {InfoCore, InfoStyle} from './info';
import {F, TH, ease} from '../theme';

// 强调色跟账号主题走（暗底那一档 TH.dark）；默认琥珀金＝原来的雾金
const K = {paper: '#F7F1E8', soft: 'rgba(247,241,232,0.78)', gold: TH.dark, line: TH.dark, ink: '#0D1216'};
const WIN = {x: 0, y: 0, w: 1080, h: 1920};

const glass = (r = 22): React.CSSProperties => ({
  // 玻璃里掺一层墨：亮窗、白墙上也压得住白字（浅色半透明叠在浅色上，可读性会塌）
  background: 'linear-gradient(160deg, rgba(255,255,255,0.14), rgba(255,255,255,0.03)), rgba(13,18,22,0.42)',
  backdropFilter: 'blur(26px) saturate(140%)', WebkitBackdropFilter: 'blur(26px) saturate(140%)',
  borderRadius: r, boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.55), inset 0 0 0 1px rgba(255,255,255,0.16)',
});

// 雾：底部 0→78% 墨色渐隐（字区），顶部一小段（刊头区）。是材质边缘，不是一块色板
const Over: React.FC = () => (
  <>
    {/* 雾：字幕区（1300–1550）压到 0.82 以上——亮的 B-roll（白纸、窗）上白字原来只有 1.9:1（第 6 轮样片实测） */}
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 1000,
      background: 'linear-gradient(180deg, rgba(13,18,22,0) 0%, rgba(13,18,22,0.55) 26%, rgba(13,18,22,0.82) 38%, rgba(13,18,22,0.88) 70%, rgba(13,18,22,0.9) 100%)'}} />
    <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 460,
      background: 'linear-gradient(180deg, rgba(13,18,22,0.50) 0%, rgba(13,18,22,0.18) 60%, rgba(13,18,22,0) 100%)'}} />
  </>
);

const Masthead: React.FC<{f: number; series: string; episode: string; end: any}> = ({series, episode}) => (
  <div style={{position: 'absolute', left: 56, top: 166, ...glass(24), padding: '20px 30px 22px 28px', maxWidth: 900}}>
    <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
      <span style={{fontFamily: F.didot, fontSize: 30, fontWeight: 500, color: K.gold}}>01</span>
      <span style={{width: 26, height: 1, background: K.line}} />
      <span style={{fontFamily: F.sans, fontWeight: 300, fontSize: 24, letterSpacing: '0.24em', color: K.soft, whiteSpace: 'nowrap'}}>{series}</span>
    </div>
    <div style={{marginTop: 10, fontFamily: F.serif, fontWeight: 900, fontSize: 46, lineHeight: 1.14, color: K.paper, letterSpacing: '0.005em', whiteSpace: 'nowrap'}}>
      <Mixed t={episode} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.08em', color: K.gold}} />
    </div>
  </div>
);

// 字幕：雾上的白字，苹方 Medium、字距略放（玻璃与雾上的字要更重一档），关键词金；入场＝材料落位（模糊收拢）
const Caption: React.FC<{cap: Cap; f: number}> = ({cap, f}) => {
  const top = cap.variant === 'g' || cap.variant === 'p' ? 1400 : 1300;
  return (
    <div style={{position: 'absolute', left: 60, right: 140, top, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
      {cap.lines.map((l, i) => {
        if (f < l.from && !(cap.animate && i === 0)) return null;
        const p = cap.animate && i === 0 ? prog(f - cap.from, 0, 4) : 1;
        return (
          <div key={i} style={{fontFamily: F.sans, fontWeight: 500, fontSize: 52, lineHeight: 1.38, color: K.paper, letterSpacing: '0.025em',
            whiteSpace: 'nowrap', opacity: p, filter: p < 1 ? `blur(${(1 - p) * 6}px)` : 'none'}}>
            <Spans t={l.text} hl={l.hl} hlStyle={{color: K.gold, fontWeight: 600}} />
          </div>
        );
      })}
    </div>
  );
};

const Card: React.FC<{f: number; from: number; to: number; children: React.ReactNode}> = ({f, from, to, children}) => {
  const local = f - from;
  if (local < 0 || f >= to) return null;
  const p = prog(local, 0, 10) * (1 - prog(local, to - from - 6, to - from, ease.in));
  return (
    <div style={{position: 'absolute', left: 56, top: 1060, ...glass(20), padding: '22px 32px 24px 30px', opacity: p, filter: `blur(${(1 - p) * 10}px)`}}>
      {children}
    </div>
  );
};

const NameTag: React.FC<{f: number; d: any}> = ({f, d}) => (
  <Card f={f} from={d.from} to={d.to}>
    <div style={{display: 'flex', alignItems: 'baseline', gap: 16, whiteSpace: 'nowrap', clipPath: `inset(0 ${wipe(f - d.from, 3, 8)}% 0 0)`}}>
      <span style={{fontFamily: F.serif, fontWeight: 900, fontSize: 48, color: K.paper}}>{d.name}</span>
      {d.latin ? <span style={{fontFamily: F.didot, fontSize: 34, color: K.gold}}>{d.latin}</span> : null}
    </div>
    {(d.lines || []).map((l: string, i: number) => (
      <div key={i} style={{marginTop: i === 0 ? 10 : 2, fontFamily: F.sans, fontWeight: 300, fontSize: 26, letterSpacing: '0.12em', color: K.soft,
        whiteSpace: 'nowrap', clipPath: `inset(0 ${wipe(f - d.from, 7 + i * 4, 8)}% 0 0)`}}>{l}</div>
    ))}
  </Card>
);

const EndCard: React.FC<{f: number; d: any}> = ({f, d}) => (
  <Card f={f} from={d.from} to={d.to + 8}>
    <div style={{fontFamily: F.sans, fontWeight: 500, fontSize: 24, letterSpacing: '0.3em', color: K.gold}}>{d.kicker}</div>
    <div style={{marginTop: 8, fontFamily: F.serif, fontWeight: 900, fontSize: 42, lineHeight: 1.26, color: K.paper, whiteSpace: 'pre-line',
      clipPath: `inset(0 ${wipe(f - d.from, 5, 9)}% 0 0)`}}>
      <Mixed t={d.line} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.06em', color: K.gold}} />
    </div>
    {d.cta ? <div style={{marginTop: 12, fontFamily: F.sans, fontWeight: 300, fontSize: 24, letterSpacing: '0.16em', color: K.soft}}>{d.cta}</div> : null}
  </Card>
);

const Tag: React.FC<{f: number; t: any}> = ({f, t}) => {
  const p = prog(f - t.from, 0, 9);
  return (
    <div style={{position: 'absolute', left: 56, top: t.top >= 400 ? 430 : 180, ...glass(999), padding: '10px 22px 11px 18px', display: 'flex',
      alignItems: 'center', gap: 12, opacity: p, filter: `blur(${(1 - p) * 8}px)`}}>
      <span style={{width: 8, height: 8, borderRadius: 8, background: K.gold}} />
      <span style={{fontFamily: F.sans, fontWeight: 500, fontSize: 26, letterSpacing: '0.12em', color: K.paper, whiteSpace: 'nowrap'}}>{t.text}</span>
    </div>
  );
};

const Cover: React.FC<{f: number; d: any}> = ({f, d}) => {
  const out = prog(f - d.frames, 0, d.trans, ease.in);
  if (out >= 1) return null;
  if (d.form && d.form !== 'title') return (
    <div style={{position: 'absolute', left: 72, right: 72, top: 950, opacity: 1 - out, filter: out > 0 ? `blur(${out * 10}px)` : 'none'}}>
      <CoverForm d={d} t={{ink: K.paper, soft: K.soft, accent: K.gold, numFont: F.didot, numWeight: 700, titleFont: F.serif, w: 936, numMax: 140, titleMax: 56, quoteMax: 64, titleLines: 1}} />
    </div>
  );
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: 960, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: 1 - out,
      filter: out > 0 ? `blur(${out * 10}px)` : 'none'}}>
      <div style={{fontFamily: F.sans, fontWeight: 300, fontSize: 30, letterSpacing: '0.46em', color: K.gold}}>{d.kicker}</div>
      {(d.title || []).map((t: string, i: number) => (
        <div key={i} style={{marginTop: i === 0 ? 22 : 4, fontFamily: F.serif, fontWeight: 900, fontSize: 88, lineHeight: 1.14, color: K.paper,
          letterSpacing: '-0.01em', whiteSpace: 'nowrap'}}>
          <Mixed t={t} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.1em', color: K.gold}} />
        </div>
      ))}
      {d.sub ? <div style={{marginTop: 18, fontFamily: F.sans, fontWeight: 300, fontSize: 28, letterSpacing: '0.2em', color: K.soft}}>{d.sub}</div> : null}
    </div>
  );
};

const Figure: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <FigureCore f={f} s={s} win={WIN} top={560} label="rgba(247,241,232,0.82)" value={K.gold} word="#F7F1E8" box={K.line} />
);
const Photo: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhotoCore f={f} s={s} win={{...WIN, y: 420, h: 900}} credit="rgba(247,241,232,0.7)" />;

// 真实性角标、分屏签、手机：都是玻璃小片（第 5 轮整理：B／C 原来没有角标，示意画面会不标就上屏）
const Chip: React.FC<{text: string; p: number; style?: React.CSSProperties}> = ({text, p, style}) => (
  <div style={{position: 'absolute', ...glass(999), padding: '9px 20px 10px', fontFamily: F.sans, fontWeight: 500, fontSize: 24, letterSpacing: '0.14em',
    color: K.paper, whiteSpace: 'nowrap', opacity: p, filter: `blur(${(1 - p) * 6}px)`, ...style}}>{text}</div>
);
const Label: React.FC<{f: number; from: number; text: string}> = ({f, from, text}) => <Chip text={text} p={prog(f - from, 2, 9)} style={{right: 56, top: 176}} />;
const SplitLabels: React.FC<{f: number; at: number; labels: string[]}> = ({f, at, labels}) => (
  <>{labels.map((l, i) => <Chip key={i} text={l} p={prog(f - at - (i === 0 ? 2 : 8), 0, 7)} style={{left: i === 0 ? 56 : 580, top: 430, fontSize: 28, letterSpacing: '0.3em'}} />)}</>
);
const PHONE = {x: 290, y: 330, w: 500, h: 980, r: 60, bezel: 14, k: 0.92, faceY: 0.4, color: 'rgba(247,241,232,0.92)'};
const PhoneFrame: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhoneFrameCore f={f} s={s} win={WIN} ph={PHONE} />;

// 信息卡：一整张深玻璃卡浮在虚化的满幅画面上
const GlassCard: React.FC<{x: number; y: number; w: number; h: number}> = ({x, y, w, h}) => (
  <div style={{position: 'absolute', left: x, top: y, width: w, height: h, ...glass(28)}} />
);
const INFO: InfoStyle = {
  area: {x: 110, y: 440, w: 860, h: 740}, ink: K.paper, mute: K.soft, accent: K.gold, accent2: 'rgba(247,241,232,0.42)', card: 'rgba(13,18,22,0.6)',
  mark: 'color', titleFont: F.serif, titleWeight: 900, numFont: F.didot, numWeight: 700, radius: 28, pad: 46, gap: 26,
  presenter: {mode: 'blur'}, Surface: GlassCard, areaCard: ['quote', 'compare', 'list', 'timeline', 'chart'],
};
const Info: React.FC<{f: number; s: Shot; face: any; src: string}> = (p) => <InfoCore {...p} st={INFO} />;

export const glassPack = {
  name: 'glass', win: WIN, faceY: null, canvas: K.ink, under: false, Info, info: INFO, breathe: 0.05, Label, SplitLabels, PhoneFrame, phone: PHONE, phonePush: phonePushK,
  Under: null as any, Over, Masthead, Caption, NameTag, EndCard, Tag, Cover, Figure, Photo,
  halftone: 0.3, grainOnBands: false, mastheadOnB: false,
};
