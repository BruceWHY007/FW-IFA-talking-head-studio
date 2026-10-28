// 三套风格包共用的零件：数字/大字卡、照片卡、中文与 Didot 数字混排。颜色与位置由包传入。
import React from 'react';
import {Img, interpolate, staticFile} from 'remotion';
import {Rect, Shot, clamp, prog} from './common';
import {F, ease} from '../theme';

// 标题里的阿拉伯数字换成 Didot（中文宋体旁放一个高对比拉丁数字，是最直接的混排手法——App 展示片 v5）
export const Mixed: React.FC<{t: string; num: React.CSSProperties}> = ({t, num}) => {
  const parts = t.split(/(\d+(?:\.\d+)?)/);
  // 紧跟在英文词后面的数字（Band 1）保持原字体：Didot 的「1」小字号下像字母 l（10-22 风格帧实测）
  return <>{parts.map((p, i) => (/^\d/.test(p) && !/[A-Za-z]\s*$/.test(parts[i - 1] || '') ? <span key={i} style={num}>{p}</span> : <span key={i}>{p}</span>))}</>;
};

// 预备 → 揭开：说到那个词之前是预备动作（方格画出、暖光涨满／金线画满），说到那个词的那一帧落字；不做 count-up
export const FigureCore: React.FC<{f: number; s: Shot; win: Rect; top: number; label: string; value: string; word: string; box: string;
  scale?: number; numFont?: string; wordFont?: string}> = ({f, s, win, top, label, value, word, box, scale = 1, numFont = F.didot, wordFont = F.serif}) => {
  const fig = s.figure || {};
  const local = f - s.from;
  // 揭开帧离镜头开头太近时，interpolate 的区间会塌成 [4,4] 直接报错（10-27 实测）——下限抬到 8
  const rv = Math.max((fig.revealFrom ?? s.from + 6) - s.from, 8);
  const lab = interpolate(local, [2, 10], [100, 0], {...clamp, easing: ease.out});
  const rule = interpolate(local, [4, Math.max(rv, 14)], [0, 1], {...clamp, easing: ease.inOut});
  const sheen = interpolate(local, [rv + 10, Math.max(s.to - s.from, rv + 30)], [-30, 130], {...clamp, easing: ease.inOut});
  const sheenBg = `linear-gradient(100deg, rgba(255,255,255,0) ${sheen - 14}%, rgba(255,246,226,0.6) ${sheen}%, rgba(255,255,255,0) ${sheen + 14}%)`;
  const chars = Array.from(String(fig.value || ''));
  const labelEl = fig.label ? (
    <div style={{clipPath: `inset(0 ${lab}% 0 0)`, fontFamily: F.sans, fontWeight: 400, fontSize: 26, letterSpacing: '0.3em', color: label,
      whiteSpace: 'nowrap'}}>{fig.label}</div>
  ) : null;
  if (fig.kind !== 'number' && chars.length <= 4) {
    const size = (chars.length > 2 ? 190 : 236) * scale;
    const bx = size + 36;
    const fill = interpolate(local, [4, Math.max(rv, 9)], [0, 1], {...clamp, easing: ease.inOut});
    const draw = interpolate(local, [2, Math.min(rv, 20)], [0, 1], {...clamp, easing: ease.out});
    return (
      <div style={{position: 'absolute', left: 0, top, width: win.w, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        {labelEl}
        <div style={{display: 'flex', gap: 24, marginTop: 34}}>
          {chars.map((ch, i) => {
            // 所有字在开口那一帧一起落下（6 帧扫开），不逐字填——逐字填会把可读时间吃掉（10-22 评审第 3 轮）
            const v = interpolate(local, [rv - 3, rv + 1], [100, 0], {...clamp, easing: ease.out});  // 开口前 3 帧起扫、开口后 1 帧扫完
            const settle = interpolate(local, [rv, rv + 12], [1, 0.22], clamp);
            const per = 2 * (bx + bx + 16);
            return (
              <div key={i} style={{position: 'relative', width: bx, height: bx + 16}}>
                <svg width={bx} height={bx + 16} style={{position: 'absolute', inset: 0, opacity: settle}}>
                  <rect x={1.5} y={1.5} width={bx - 3} height={bx + 13} fill="none" stroke={box} strokeWidth={2.5}
                    strokeDasharray={per} strokeDashoffset={(1 - draw) * per} />
                </svg>
                <div style={{position: 'absolute', left: 3, right: 3, bottom: 3, height: `calc(${fill * 100}% - 6px)`, opacity: settle * 0.9,
                  background: `linear-gradient(180deg, rgba(216,168,99,0.08), rgba(216,168,99,0.30))`}} />
                <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  clipPath: `inset(-10% ${v}% -10% 0)`, fontFamily: wordFont, fontWeight: 900, fontSize: size, lineHeight: 1, color: word}}>
                  <span style={{position: 'relative'}}>{ch}
                    <span aria-hidden style={{position: 'absolute', inset: 0, backgroundImage: sheenBg, WebkitBackgroundClip: 'text',
                      backgroundClip: 'text', color: 'transparent'}}>{ch}</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        <div style={{marginTop: 30, width: 200, height: 2, background: box, transform: `scaleX(${rule})`}} />
      </div>
    );
  }
  const val = interpolate(local, [rv - 3, rv + 1], [100, 0], {...clamp, easing: ease.out});
  // 数字也按宽度 fit：5 个字符的「1-1.5」在 380px 下宽过 1200，会冲出卡面（10-27 实测）
  const unitW = fig.unit ? 1.9 : 0;
  const numSize = Math.max(120, Math.min(380 * scale, Math.floor((win.w - 200) / Math.max(emW(String(fig.value || '')) + unitW, 0.8))));
  const ns: React.CSSProperties = {fontFamily: numFont, fontWeight: 700, fontSize: numSize, lineHeight: 1, letterSpacing: '-0.02em'};
  return (
    <div style={{position: 'absolute', left: 0, top, width: win.w, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
      {labelEl}
      <div style={{clipPath: `inset(-10% ${val}% -10% 0)`, display: 'flex', alignItems: 'baseline', gap: 18, marginTop: 20, whiteSpace: 'nowrap'}}>
        <span style={{position: 'relative', ...ns, color: value}}>{fig.value}
          <span aria-hidden style={{position: 'absolute', inset: 0, backgroundImage: sheenBg, WebkitBackgroundClip: 'text',
            backgroundClip: 'text', color: 'transparent'}}>{fig.value}</span>
        </span>
        {fig.unit ? <span style={{fontFamily: wordFont, fontWeight: 900, fontSize: Math.round(numSize * 0.29), color: word}}>{fig.unit}</span> : null}
      </div>
      <div style={{marginTop: 30, width: 200, height: 2, background: box, transform: `scaleX(${rule})`}} />
    </div>
  );
};

export const PhotoCore: React.FC<{f: number; s: Shot; win: Rect; credit: string}> = ({f, s, win, credit}) => {
  const local = f - s.from;
  const inP = prog(local, 0, 10);
  const push = interpolate(local, [0, s.to - s.from], [1, 1.04], {...clamp, easing: ease.inOut});
  const maxW = win.w - 144, maxH = win.h - 200;
  const k = Math.min(maxW / (s.iw || 1600), maxH / (s.ih || 1000));
  const cw = Math.round((s.iw || 1600) * k), ch = Math.round((s.ih || 1000) * k);
  return (
    <div style={{position: 'absolute', left: (win.w - cw) / 2, top: (win.h - ch) / 2 - 20, width: cw}}>
      <div style={{width: cw, height: ch, overflow: 'hidden', opacity: inP, filter: `blur(${(1 - inP) * 12}px)`,
        transform: `scale(${0.965 + 0.035 * inP})`, boxShadow: 'inset 0 0 0 1px rgba(245,240,230,0.35)'}}>
        <Img src={staticFile(s.image!)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${push})`}} />
      </div>
      {s.credit ? <div style={{marginTop: 12, textAlign: 'right', fontFamily: F.sans, fontWeight: 300, fontSize: 22, letterSpacing: '0.1em',
        color: credit, opacity: inP}}>{s.credit}</div> : null}
    </div>
  );
};

// ---------- 文字宽度估算（em）：中文 1、拉丁与数字约 0.56、空格 0.3。只用来挑字号，不用来截断——装不下 build.py 先报 ----------
export const emW = (t: string) => Array.from(String(t || '')).reduce((a, c) =>
  a + (c === ' ' ? 0.3 : /[0-9.%]/.test(c) ? 0.6 : /[\u0000-ÿ]/.test(c) ? 0.56 : 1), 0);
export const fitSize = (t: string, maxW: number, max: number, min: number) =>
  Math.max(min, Math.min(max, Math.floor(maxW / Math.max(emW(t), 0.5))));

// ---------- 「手机里的她」通用框：每个风格包给手机在画面窗里的位置和边框色 ----------
export type PhoneSpec = {x: number; y: number; w: number; h: number; r: number; bezel: number; k: number; faceY: number; color: string};
export const phonePushK = (f: number, s: Shot) => 1 + 0.05 * Math.min(Math.max((f - s.from) / Math.max(s.to - s.from, 1), 0), 1);
export const PhoneFrameCore: React.FC<{f: number; s: Shot; win: Rect; ph: PhoneSpec}> = ({f, s, win, ph}) => {
  const blink = Math.floor((f - s.from) / 15) % 2 === 0;
  const k = phonePushK(f, s);
  return (
    <div style={{position: 'absolute', left: win.x + ph.x - ph.bezel, top: win.y + ph.y - ph.bezel, width: ph.w + ph.bezel * 2,
      height: ph.h + ph.bezel * 2, borderRadius: ph.r + ph.bezel, border: `${ph.bezel}px solid ${ph.color}`, boxSizing: 'border-box',
      transform: `scale(${k})`, transformOrigin: `${(ph.x + ph.w / 2) / win.w * 100}% 50%`, boxShadow: '0 40px 90px rgba(0,0,0,0.4)'}}>
      <div style={{position: 'absolute', left: 26, top: 30, display: 'flex', alignItems: 'center', gap: 10, padding: '6px 14px 7px',
        background: 'rgba(13,18,22,0.55)', borderRadius: 20}}>
        <span style={{width: 12, height: 12, borderRadius: 12, background: blink ? '#E5483B' : 'rgba(229,72,59,0.35)'}} />
        <span style={{fontFamily: F.sans, fontWeight: 500, fontSize: 20, letterSpacing: '0.16em', color: '#F5F0E6'}}>REC</span>
      </div>
    </div>
  );
};

// ---------- 封面的另外三种形式（title 由各包自己画）：number 一个数字当钩子／versus 两边对比／quote 一句原话 ----------
// 选哪种由 build.py 按内容和账号登记定（同一账号相邻两支不用同一种）。颜色、字体、宽度由包传入。
export type CoverTok = {ink: string; soft: string; accent: string; numFont: string; numWeight: number; titleFont: string; w: number; align?: 'left' | 'center';
  numMax?: number; titleMax?: number; quoteMax?: number; mark?: boolean; titleLines?: number};  // 满幅包的封面夹在脸和字幕之间（约 920–1200），字号要封顶
export const CoverForm: React.FC<{d: any; t: CoverTok}> = ({d, t}) => {
  const al = t.align || 'left';
  const kick = d.kicker ? <div style={{fontFamily: F.sans, fontWeight: 400, fontSize: 28, letterSpacing: '0.36em', color: t.accent}}>{d.kicker}</div> : null;
  if (d.form === 'number' && d.number) {
    const v = String(d.number.value);
    const size = fitSize(v, t.w * 0.72, t.numMax || 300, Math.min(150, t.numMax || 150));
    return (
      <div style={{display: 'flex', flexDirection: 'column', alignItems: al === 'center' ? 'center' : 'flex-start'}}>
        {kick}
        <div style={{display: 'flex', alignItems: 'baseline', gap: 16, marginTop: 6, whiteSpace: 'nowrap'}}>
          <span style={{fontFamily: t.numFont, fontWeight: t.numWeight, fontSize: size, lineHeight: 1, letterSpacing: '-0.02em', color: t.accent}}>{v}</span>
          {d.number.unit ? <span style={{fontFamily: t.titleFont, fontWeight: 900, fontSize: Math.round(size * 0.3), color: t.ink}}>{d.number.unit}</span> : null}
        </div>
        {/* number 形式不再叠标题行：标题在刊头已有，叠上去既重复又会溢出面板（10-27 实测） */}
        {t.numberSub ? (d.title || []).slice(0, 1).map((x: string, i: number) => (
          <div key={i} style={{marginTop: 12, fontFamily: t.titleFont, fontWeight: 900, fontSize: fitSize(x, t.w, 48, 32), lineHeight: 1.16,
            color: t.soft, whiteSpace: 'nowrap'}}>{x}</div>
        )) : null}
      </div>
    );
  }
  if (d.form === 'versus' && d.versus) {
    const L = d.versus.left || {}, R = d.versus.right || {};
    const col = (it: any, win: boolean) => (
      <div style={{flex: 1, minWidth: 0}}>
        <div style={{fontFamily: F.sans, fontWeight: 600, fontSize: 32, letterSpacing: '0.2em', color: t.soft}}>{it.label}</div>
        <div style={{marginTop: 6, fontFamily: t.numFont, fontWeight: t.numWeight, fontSize: fitSize(String(it.value), t.w * 0.42, Math.min(170, t.numMax || 170), 80), lineHeight: 1,
          color: win ? t.accent : t.ink, whiteSpace: 'nowrap'}}>{it.value}</div>
      </div>
    );
    return (
      <div>
        {kick}
        <div style={{display: 'flex', alignItems: 'flex-end', gap: 28, marginTop: 14}}>
          {col(L, d.versus.win !== 1)}
          <div style={{fontFamily: t.titleFont, fontWeight: 900, fontSize: 44, color: t.soft, paddingBottom: 26}}>vs</div>
          {col(R, d.versus.win === 1)}
        </div>
        {(d.title || []).slice(0, t.titleLines || 9).map((x: string, i: number) => (
          <div key={i} style={{marginTop: i === 0 ? 22 : 0, fontFamily: t.titleFont, fontWeight: 900, fontSize: fitSize(x, t.w, t.titleMax || 76, 44), lineHeight: 1.16,
            color: t.ink, whiteSpace: 'nowrap'}}>{x}</div>
        ))}
      </div>
    );
  }
  if (d.form === 'quote' && d.quote) {
    const q = String(d.quote.text);
    const qmax = t.quoteMax || 84;
    const size = Math.max(Math.min(54, qmax), Math.min(qmax, Math.floor(t.w / Math.max(Math.ceil(emW(q) / 3), 1))));
    return (
      <div>
        {kick}
        {t.mark === false ? null : <div style={{marginTop: 8, fontFamily: t.titleFont, fontWeight: 900, fontSize: Math.round(size * 1.4), lineHeight: 0.8, color: t.accent}}>“</div>}
        <div style={{fontFamily: t.titleFont, fontWeight: 900, fontSize: size, lineHeight: 1.24, color: t.ink, width: t.w}}>{q}</div>
        {d.quote.source ? <div style={{marginTop: 18, fontFamily: F.sans, fontWeight: 400, fontSize: 26, letterSpacing: '0.12em', color: t.soft}}>— {d.quote.source}</div> : null}
      </div>
    );
  }
  return null;
};
