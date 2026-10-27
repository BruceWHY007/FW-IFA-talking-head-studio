// 风格包 C · 港刊大字 —— 满幅画面，左侧一条金色书脊线＋竖排刊头；字幕是宋体大字直接落在画面下部的墨色渐隐上，
// 关键词单独放大一级、换成金色重宋（字幕本身就是排版，不是字幕条）。数字和题眼字出血。
import React from 'react';
import {interpolate} from 'remotion';
import {Cap, Shot, prog, wipe} from './common';
import {FigureCore, PhotoCore, Mixed, CoverForm, PhoneFrameCore, phonePushK} from './parts';
import {InfoCore, InfoStyle} from './info';
import {F, TH, ease} from '../theme';

const K = {paper: '#F6F0E6', soft: 'rgba(246,240,230,0.76)', gold: TH.dark, line: TH.dark, ink: '#0D1216'};
const WIN = {x: 0, y: 0, w: 1080, h: 1920};
const SPINE_X = 58;

const Over: React.FC = () => (
  <>
    {/* 字幕区（1270–1560）要压到 0.8 以上：原片两侧是亮窗，0.3 的雾上白字只有 1:1（第 6 轮样片实测） */}
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 1080,
      background: 'linear-gradient(180deg, rgba(13,18,22,0) 0%, rgba(13,18,22,0.62) 28%, rgba(13,18,22,0.84) 42%, rgba(13,18,22,0.9) 70%, rgba(13,18,22,0.94) 100%)'}} />
    <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 300,
      background: 'linear-gradient(90deg, rgba(13,18,22,0.55) 0%, rgba(13,18,22,0.22) 55%, rgba(13,18,22,0) 100%)'}} />
    <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 420,
      background: 'linear-gradient(180deg, rgba(13,18,22,0.62) 0%, rgba(13,18,22,0.3) 55%, rgba(13,18,22,0) 100%)'}} />
    <div style={{position: 'absolute', left: SPINE_X, top: 170, width: 3, height: 1300, background: K.line}} />
  </>
);

// 刊头：本期标题横排在书脊线右上；书脊线上竖排的只有中文系列名（竖排里不混英文和数字，10-22 风格帧实测会散）
const Masthead: React.FC<{f: number; series: string; episode: string; end: any}> = ({series, episode}) => (
  <>
    <div style={{position: 'absolute', left: SPINE_X + 26, top: 172}}>
      <div style={{fontFamily: F.didot, fontSize: 26, color: K.gold, letterSpacing: '0.1em'}}>No.01</div>
      <div style={{marginTop: 6, fontFamily: F.serif, fontWeight: 900, fontSize: 44, lineHeight: 1.15, color: K.paper, whiteSpace: 'nowrap'}}>
        <Mixed t={episode} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.08em', color: K.gold}} />
      </div>
    </div>
    <div style={{position: 'absolute', left: SPINE_X + 22, top: 330, writingMode: 'vertical-rl', fontFamily: F.sans, fontWeight: 300, fontSize: 24,
      letterSpacing: '0.42em', color: K.soft, lineHeight: 1}}>{series.replace(/[，,]/g, ' ')}</div>
  </>
);

// 字幕：宋体大字左对齐落在书脊线右边；关键词放大 1.22 倍、金色重宋——一句话里自带重音
const KSpans: React.FC<{t: string; hl: [number, number][]}> = ({t, hl}) => {
  const out: React.ReactNode[] = [];
  let i = 0;
  [...hl].sort((a, b) => a[0] - b[0]).forEach(([a, b], k) => {
    if (a < i) return;
    if (a > i) out.push(<span key={'n' + k}>{t.slice(i, a)}</span>);
    out.push(<span key={'h' + k} style={{color: K.gold, fontWeight: 900, fontSize: '1.22em'}}>{t.slice(a, b)}</span>);
    i = b;
  });
  if (i < t.length) out.push(<span key="t">{t.slice(i)}</span>);
  return <>{out}</>;
};
const Caption: React.FC<{cap: Cap; f: number}> = ({cap, f}) => {
  const top = cap.variant === 'g' || cap.variant === 'p' ? 1380 : 1270;
  return (
    <div style={{position: 'absolute', left: SPINE_X + 40, right: 140, top}}>
      {cap.lines.map((l, i) => {
        if (f < l.from && !(cap.animate && i === 0)) return null;
        const r = cap.animate && i === 0 ? wipe(f - cap.from, 0, 4) : 0;
        return (
          <div key={i} style={{fontFamily: F.serif, fontWeight: 600, fontSize: 58, lineHeight: 1.3, color: K.paper, letterSpacing: '0.01em',
            whiteSpace: 'nowrap', clipPath: `inset(-20% ${r}% -20% 0)`}}>
            <KSpans t={l.text} hl={l.hl} />
          </div>
        );
      })}
    </div>
  );
};

// 名字条：人像刊物的署名——大号宋体名字＋细体身份，从书脊线里「抽」出来
const NameTag: React.FC<{f: number; d: any}> = ({f, d}) => {
  const local = f - d.from;
  if (local < 0 || f >= d.to) return null;
  const o = 1 - prog(local, d.to - d.from - 6, d.to - d.from, ease.in);
  return (
    <div style={{position: 'absolute', left: SPINE_X + 40, top: 1020, opacity: o}}>
      <div style={{fontFamily: F.serif, fontWeight: 900, fontSize: 84, lineHeight: 1.05, color: K.paper, whiteSpace: 'nowrap',
        clipPath: `inset(0 ${wipe(local, 2, 10)}% 0 0)`}}>{d.name}{d.latin ? <span style={{fontFamily: F.didot, fontWeight: 500, fontSize: 52, color: K.gold, marginLeft: 18}}>{d.latin}</span> : null}</div>
      <div style={{marginTop: 12, fontFamily: F.sans, fontWeight: 300, fontSize: 26, letterSpacing: '0.2em', color: K.soft, whiteSpace: 'nowrap',
        clipPath: `inset(0 ${wipe(local, 8, 10)}% 0 0)`}}>{(d.lines || []).join('　/　')}</div>
    </div>
  );
};

const EndCard: React.FC<{f: number; d: any}> = ({f, d}) => {
  const local = f - d.from;
  if (local < 0) return null;
  return (
    <div style={{position: 'absolute', left: SPINE_X + 40, top: 1000}}>
      <div style={{fontFamily: F.sans, fontWeight: 500, fontSize: 24, letterSpacing: '0.34em', color: K.gold, clipPath: `inset(0 ${wipe(local, 0, 8)}% 0 0)`}}>{d.kicker}</div>
      <div style={{marginTop: 10, fontFamily: F.serif, fontWeight: 900, fontSize: 52, lineHeight: 1.22, color: K.paper, whiteSpace: 'pre-line',
        clipPath: `inset(0 ${wipe(local, 4, 10)}% 0 0)`}}>
        <Mixed t={d.line} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.08em', color: K.gold}} />
      </div>
    </div>
  );
};

const Tag: React.FC<{f: number; t: any}> = ({f, t}) => (
  <div style={{position: 'absolute', left: SPINE_X - 4, top: t.top >= 400 ? 980 : 980, display: 'flex', alignItems: 'center', gap: 16,
    clipPath: `inset(0 ${wipe(f - t.from, 0, 8)}% 0 0)`}}>
    <span style={{width: 11, height: 11, background: K.gold, transform: 'rotate(45deg)'}} />
    <span style={{fontFamily: F.sans, fontWeight: 400, fontSize: 28, letterSpacing: '0.2em', color: K.paper, whiteSpace: 'nowrap'}}>{t.text}</span>
  </div>
);

const Cover: React.FC<{f: number; d: any}> = ({f, d}) => {
  const out = prog(f - d.frames, 0, d.trans, ease.in);
  if (out >= 1) return null;
  if (d.form && d.form !== 'title') return (
    <div style={{position: 'absolute', left: SPINE_X + 40, right: 80, top: 920, clipPath: `inset(0 ${out * 100}% 0 0)`}}>
      <CoverForm d={d} t={{ink: K.paper, soft: K.soft, accent: K.gold, numFont: F.didot, numWeight: 700, titleFont: F.serif, w: 880, numMax: 140, titleMax: 56, quoteMax: 64, titleLines: 1}} />
    </div>
  );
  return (
    <div style={{position: 'absolute', left: SPINE_X + 40, right: 80, top: 960, clipPath: `inset(0 ${out * 100}% 0 0)`}}>
      <div style={{fontFamily: F.sans, fontWeight: 300, fontSize: 28, letterSpacing: '0.46em', color: K.gold}}>{d.kicker}</div>
      {(d.title || []).map((t: string, i: number) => (
        <div key={i} style={{marginTop: i === 0 ? 18 : 0, fontFamily: F.serif, fontWeight: 900, fontSize: 96, lineHeight: 1.12, color: K.paper,
          letterSpacing: '-0.015em', whiteSpace: 'nowrap'}}>
          <Mixed t={t} num={{fontFamily: F.didot, fontWeight: 600, fontSize: '1.12em', color: K.gold}} />
        </div>
      ))}
      {d.sub ? <div style={{marginTop: 18, fontFamily: F.sans, fontWeight: 300, fontSize: 28, letterSpacing: '0.22em', color: K.soft}}>{d.sub}</div> : null}
    </div>
  );
};

const Figure: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <FigureCore f={f} s={s} win={WIN} top={520} label="rgba(246,240,230,0.82)" value={K.gold} word="#F6F0E6" box={K.line} scale={1.18} />
);
const Photo: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhotoCore f={f} s={s} win={{...WIN, y: 380, h: 900}} credit="rgba(246,240,230,0.7)" />;

// 角标与分屏签：书脊线语言（金色菱形＋细体字），不加底（C 的字本来就落在暗化的画面上）
const Label: React.FC<{f: number; from: number; text: string}> = ({f, from, text}) => (
  <div style={{position: 'absolute', right: 64, top: 180, display: 'flex', alignItems: 'center', gap: 10, clipPath: `inset(0 0 0 ${wipe(f - from, 2, 8)}%)`,
    background: 'rgba(13,18,22,0.55)', padding: '8px 16px 9px'}}>
    <span style={{width: 8, height: 8, background: K.gold, transform: 'rotate(45deg)'}} />
    <span style={{fontFamily: F.sans, fontWeight: 400, fontSize: 24, letterSpacing: '0.16em', color: K.paper, whiteSpace: 'nowrap'}}>{text}</span>
  </div>
);
const SplitLabels: React.FC<{f: number; at: number; labels: string[]}> = ({f, at, labels}) => (
  <>{labels.map((l, i) => (
    <div key={i} style={{position: 'absolute', left: i === 0 ? SPINE_X + 30 : 580, top: 440, fontFamily: F.serif, fontWeight: 900, fontSize: 52, color: K.paper,
      letterSpacing: '0.2em', clipPath: `inset(-10% ${wipe(f - at - (i === 0 ? 2 : 8), 0, 7)}% -10% 0)`, background: 'rgba(13,18,22,0.5)', padding: '4px 16px 8px'}}>{l}</div>
  ))}</>
);
const PHONE = {x: 290, y: 330, w: 500, h: 980, r: 60, bezel: 14, k: 0.92, faceY: 0.4, color: K.paper};
const PhoneFrame: React.FC<{f: number; s: Shot}> = ({f, s}) => <PhoneFrameCore f={f} s={s} win={WIN} ph={PHONE} />;

// 信息卡：整页翻成墨色，大字直接落在页面上（C 的语法：字本身就是版面）；她进右上角的栏目小像（金色细框），嘴型不断
// 第 6 轮样片：字压在虚化的她身上，碰到亮窗只有 2:1；满幅画面大半是静止的窗，卡片期间被判冻结
const InkPage: React.FC = () => (
  <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(120% 80% at 30% 40%, #1A2026 0%, #0D1216 70%)'}} />
);
const INFO: InfoStyle = {
  area: {x: SPINE_X + 40, y: 580, w: 880, h: 640}, ink: K.paper, mute: K.soft, accent: K.gold, accent2: 'rgba(246,240,230,0.38)', card: K.ink,
  mark: 'color', titleFont: F.serif, titleWeight: 900, numFont: F.didot, numWeight: 700, radius: 0, pad: 0, gap: 40,
  presenter: {mode: 'box', rect: {x: 736, y: 196, w: 280, h: 330}, border: `2px solid ${K.gold}`}, WindowBg: InkPage,
};
const Info: React.FC<{f: number; s: Shot; face: any; src: string}> = (p) => <InfoCore {...p} st={INFO} />;

export const kinetic = {
  name: 'kinetic', win: WIN, faceY: null, canvas: K.ink, under: false, Info, info: INFO, breathe: 0.05, Label, SplitLabels, PhoneFrame, phone: PHONE, phonePush: phonePushK,
  Under: null as any, Over, Masthead, Caption, NameTag, EndCard, Tag, Cover, Figure, Photo,
  halftone: 0.3, grainOnBands: false, mastheadOnB: true,
};
