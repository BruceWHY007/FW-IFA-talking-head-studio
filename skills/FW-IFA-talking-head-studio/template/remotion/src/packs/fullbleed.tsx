// 风格包 F · 满幅讲述（v2，2026-10-29）—— 结构拆自参考片 R0（暖调书房单人观点口播），信息卡与标题卡借 R1／R2（深色数据讲解）。
// 规格、量法与约束全文在 references/11_F满幅讲述_规格与约束.md；这里的每个数字都能在那份文档里找到出处。
//
// 版面语法只有四层，全片不变：
//   ① 顶部刊头：两行宋体（只在人脸镜头出现，被顶部插条盖住时让位）
//   ② 字幕：宋体粗、白字柔影、一行、中心线 y=1118；重话整行换金／银金属字并放大
//   ③ 底部声明：常驻小字 y=1800
//   ④ 一层「画面处理」轮换：满幅人脸 ／ 人脸＋插条 ／ B-roll 满幅 ／ B-roll＋她的小窗（方窗、光晕圆、细环圆）／ 三条分带 ／ 横版画框条
// 信息靠「她在说 + 画面处理」承载；只有真正的数据和清单才上玻璃卡（R1／R2 的做法，换成暖金配色）。
import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import tlRaw from '../timeline.json';
import {Cap, Shot, clamp, faceFit, prog} from './common';
import {fitSize, emW, PhoneFrameCore, PhotoCore} from './parts';
import {InfoCore, InfoStyle} from './info';
import {F, ease} from '../theme';

const tl: any = tlRaw;
const WIN = {x: 0, y: 0, w: 1080, h: 1920};
const FACE = tl.aroll.face || {cx: 0.5, cy: 0.42, w: 0.3};

// ---------- 恒定参数（R0 实测 720×1280 ×1.5 换算到 1080×1920，见 references/11 §二）----------
export const FB = {
  kickTop: 100, kickSize: 62, kickPitch: 76,          // 刊头：两行，62px，行距 76
  capCY: 1118, capSize: 66, hookSize: 84, toneSize: 96, capMaxW: 960,   // 字幕：中心线 1118；开场钩子 84；金银重话 96
  capLowCY: 1380,                                       // 卡片、标题卡、原文截图在屏时字幕落到卡下面（R1／R2 的字幕在 0.715 高度，卡在上方）
  footCY: 1800, footSize: 33,                          // 声明：中心 1800，33px，62% 白
  stackX: 150, stackTop: 1040, stackPitch: 150, stackSize: 88,           // 堆叠清单：左对齐 x=150，行距 150，88px
  stepX: 120, stepTop: 900, stepSize: 120,             // 步骤标题：左对齐，120px，压在字幕上方
  topBand: 520, bottomBand: 1270,                       // 插条：顶部 0–520／底部 1270–1920
  bands3: [0, 650, 1290, 1920],                         // 三条分带的分界
  glow: {cx: 740, cy: 520, d: 620},                     // 光晕圆：直径 620，圆心偏右上
  glowband: {cx: 720, cy: 470, d: 560, split: 1200},    // 光晕圆＋下条：上 0–1200，下 1200–1920（R0 是 1150；字幕中心 1118、字底到 1160，接缝放在字下面，10-29 验收：字压在接缝上）
  pip: {w: 400, h: 520, y: 200, r: 44, frame: 14},      // 方窗：400×520，顶 200，磨砂边 14
  ring: {cx: 900, cy: 300, d: 230, line: 5},            // 细环圆：R1 的新闻画面叙述位
};

// 暗位不低于 #E0A63A：原来的 #B98330 压在亮底（手机屏、窗光）上读成黑铜色，「备案」两字看不清（10-29 验片）
export const GOLD = 'linear-gradient(180deg, #FFF9DE 0%, #FCE7A6 28%, #F5CB64 52%, #E6AE3F 70%, #FAE08E 100%)';
// 纸面上的金：同一套渐变压深两档（浅底上的亮金对比度只有 2:1，读不清——10-29 v1 自查）
export const GOLD_DEEP = 'linear-gradient(180deg, #EBBB5A 0%, #D29A30 38%, #B27414 62%, #9A6010 78%, #D49A2E 100%)';
export const SILVER = 'linear-gradient(180deg, #FFFFFF 0%, #F1F2F4 36%, #A7ACB4 58%, #E6E8EB 78%, #FFFFFF 100%)';
const INK = '#FFFFFF';
const SHADOW = '0 2px 4px rgba(0,0,0,0.85), 0 4px 18px rgba(0,0,0,0.55)';
// 字幕专用：再加一圈宽柔影（36px），亮底上字周围自带一层暗晕，不用整条底板（R0 的做法是描边＋柔影，不做色块）
const CAP_SHADOW = SHADOW + ', 0 0 14px rgba(0,0,0,0.45), 0 0 40px rgba(0,0,0,0.55)';
const metal = (tone: string): React.CSSProperties => ({
  backgroundImage: tone === 'silver' ? SILVER : GOLD, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
});
// 金属字没法用 text-shadow（字是透明的），立体感和暖光用 drop-shadow 叠两层
// 贴一圈深棕细边（亮底上字形不糊），再叠暖光
const METAL_FX = 'drop-shadow(0 0 1.2px rgba(74,42,6,0.95)) drop-shadow(0 2px 2px rgba(0,0,0,0.62)) drop-shadow(0 0 14px rgba(255,196,110,0.30))';
const CAP_METAL_FX = METAL_FX + ' drop-shadow(0 0 5px rgba(0,0,0,0.6)) drop-shadow(0 0 18px rgba(0,0,0,0.5))';
const SILVER_FX = 'drop-shadow(0 3px 3px rgba(0,0,0,0.78)) drop-shadow(0 0 12px rgba(255,255,255,0.22))';
const CAP_SILVER_FX = SILVER_FX + ' drop-shadow(0 0 5px rgba(0,0,0,0.6)) drop-shadow(0 0 18px rgba(0,0,0,0.5))';

const at = (f: number, a: number, b: number) => f >= a && f < b;
const shotAt = (f: number): Shot | null => (tl.shots as Shot[]).find((s) => f >= s.from && f < s.to) || null;
const isFaceFrame = (s: Shot | null) => !s;   // 镜头表里只登记非人脸镜头，没有镜头＝她满幅在说
const insertAt = (f: number) => (tl.inserts || []).find((x: any) => at(f, x.from, x.to));
const textsAt = (f: number) => (tl.texts || []).filter((x: any) => at(f, x.from, x.to));

// ---------- 底：没有画布色，满幅就是她 ----------
const Under: React.FC = () => null;

// 刊头与字幕的托底：只压到 0.30，不改亮部（我们的原片窗光多，R0 是暗书柜；见 11 §三「背景亮」）
const Scrim: React.FC = () => {
  const f = useCurrentFrame();
  const s = shotAt(f);
  const face = isFaceFrame(s);
  return (
    <>
      {face && !(insertAt(f) || {}).pos?.startsWith?.('top') ? (
        <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 330, pointerEvents: 'none',
          background: 'linear-gradient(180deg, rgba(0,0,0,0.40) 0%, rgba(0,0,0,0.20) 52%, rgba(0,0,0,0) 100%)'}} />
      ) : null}
      {/* 字幕托底：默认 0.20；亮底 B-roll 由 build 量字幕那一带的亮度给 capScrim（0.20–0.55） */}
      <div style={{position: 'absolute', left: 0, right: 0, top: FB.capCY - 170, height: 340, pointerEvents: 'none',
        background: `linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,${(s as any)?.capScrim ?? 0.2}) 38%, rgba(0,0,0,${(s as any)?.capScrim ?? 0.2}) 62%, rgba(0,0,0,0) 100%)`}} />
      {/* 底部托底托住声明：白桌面、白墙这类亮底上 0.30 不够（10-29：声明白字压白桌面看不清），加深到 0.55 */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 320, pointerEvents: 'none',
        background: 'linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.28) 50%, rgba(0,0,0,0.55) 100%)'}} />
    </>
  );
};

// ---------- ① 刊头：两行宋体，居中（R0：从 CRS 到跨境涉税监管／财富传承的逻辑正在彻底重构）----------
const Masthead: React.FC<{f: number; series: string; episode: string}> = ({f, series, episode}) => {
  const lines: string[] = (tl.masthead && tl.masthead.lines && tl.masthead.lines.length ? tl.masthead.lines : [series, episode]).filter(Boolean);
  return (
    <div style={{position: 'absolute', left: 60, right: 60, top: FB.kickTop, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
      {lines.slice(0, 2).map((t, i) => (
        <div key={i} style={{fontFamily: F.serif, fontWeight: 600, fontSize: fitSize(t, 960, FB.kickSize, 44), lineHeight: `${FB.kickPitch}px`,
          color: INK, letterSpacing: '0.02em', textShadow: SHADOW, whiteSpace: 'nowrap'}}>{t}</div>
      ))}
    </div>
  );
};
// 刊头只在「看得见她」的帧出现：人脸镜头、人脸＋底部插条；顶部插条盖住它时让位；B-roll、卡片都不出
const mastheadOn = (f: number, s: Shot | null) => {
  if (!isFaceFrame(s)) return false;
  const ins = insertAt(f);
  if (ins && ins.pos === 'top') return false;
  if (tl.outro && f >= tl.outro.from) return false;
  return true;
};

// ---------- ② 字幕：一行宋体粗，白字柔影；关键词说到时变金；整行重话换金／银并放大 ----------
const LineText: React.FC<{l: any; f: number; size: number; tone?: string}> = ({l, f, size, tone}) => {
  const t: string = l.text;
  if (tone) {
    return <span style={{display: 'inline-block', filter: tone === 'silver' ? CAP_SILVER_FX : CAP_METAL_FX}}><span style={metal(tone)}>{t}</span></span>;
  }
  const hl: [number, number][] = l.hl || [];
  const hlAt: number[] = l.hlAt || [];
  const out: React.ReactNode[] = [];
  let i = 0;
  hl.map((r, k) => ({r, a: hlAt[k] ?? l.from})).sort((x, y) => x.r[0] - y.r[0]).forEach(({r, a}, k) => {
    if (r[0] < i) return;
    if (r[0] > i) out.push(<span key={'n' + k} style={{textShadow: CAP_SHADOW}}>{t.slice(i, r[0])}</span>);
    const on = f >= a;
    out.push(on
      ? <span key={'h' + k} style={{display: 'inline-block', filter: CAP_METAL_FX}}><span style={metal('gold')}>{t.slice(r[0], r[1])}</span></span>
      : <span key={'h' + k} style={{textShadow: CAP_SHADOW}}>{t.slice(r[0], r[1])}</span>);
    i = r[1];
  });
  if (i < t.length) out.push(<span key="tail" style={{textShadow: CAP_SHADOW}}>{t.slice(i)}</span>);
  // 祖先的 text-shadow 会画在 background-clip:text 的渐变上面，把金字压成黑铜色（10-29 验片：「备案」）——影子只给白字片段，金属字用 drop-shadow
  return <span>{out}</span>;
};

// 字幕落低位的镜头：信息卡、标题卡、照片卡、原文截图（字压在卡面上会糊，白字压白纸读不出——10-29 v1 自查）
const lowCap = (s: any) => !!s && (['G', 'I', 'P'].includes(s.type) || s.layout === 'doc');
const Caption: React.FC<{cap: Cap & any; f: number}> = ({cap, f}) => {
  const lines = (cap.lines || []).filter((l: any) => f >= l.from || (cap.animate && l === cap.lines[0]));
  if (!lines.length) return null;
  const cy = lowCap(shotAt(f)) ? FB.capLowCY : FB.capCY;
  const p = cap.animate ? prog(f - cap.from, 0, 3) : 1;
  const n = lines.length;
  return (
    <div style={{position: 'absolute', left: 60, right: 60, top: cy, transform: 'translateY(-50%)', display: 'flex', flexDirection: 'column',
      alignItems: 'center', gap: 6, opacity: p}}>
      {lines.map((l: any, i: number) => {
        const tone = l.tone || cap.tone;
        const base = tone ? FB.toneSize : cap.hook ? FB.hookSize : FB.capSize;
        const size = fitSize(l.text, FB.capMaxW, base, 44);
        return (
          <div key={i} style={{fontFamily: F.serif, fontWeight: 900, fontSize: size, lineHeight: 1.22, color: INK, whiteSpace: 'nowrap',
            letterSpacing: '0.01em', marginTop: i && n > 1 ? 4 : 0}}>
            <LineText l={l} f={f} size={size} tone={tone} />
          </div>
        );
      })}
    </div>
  );
};
// 堆叠清单、散点关键词在场时，字幕让位（R0 t79–84、t150：同一处只有一种字）
const paperOn = (s: any) => !!s && s.type === 'I' && s.info && s.info.surface === 'paper';
const hideCaption = (f: number, s?: any) => textsAt(f).some((x: any) => x.kind === 'stack' || x.kind === 'scatter') || paperOn(s);

// ---------- ③ 底部声明 ----------
const Foot: React.FC = () => (
  <div style={{position: 'absolute', left: 0, right: 0, top: FB.footCY - FB.footSize * 0.7, textAlign: 'center', fontFamily: F.serif, fontWeight: 600,
    fontSize: FB.footSize, letterSpacing: '0.06em', color: 'rgba(255,255,255,0.72)', textShadow: '0 1px 3px rgba(0,0,0,0.75), 0 2px 10px rgba(0,0,0,0.55)'}}>
    {tl.disclaimer || '本内容仅作为科普，不构成任何投资建议'}
  </div>
);
const Over: React.FC = () => <><Scrim /><Foot /></>;

// 真实性角标（示意画面／AI 生成）：落在声明上方右侧，小而清楚
const Label: React.FC<{f: number; from: number; text: string}> = ({f, from, text}) => text ? (
  <div style={{position: 'absolute', right: 48, top: FB.footCY - 76, fontFamily: F.sans, fontWeight: 400, fontSize: 21, letterSpacing: '0.14em',
    color: 'rgba(255,255,255,0.62)', textShadow: '0 1px 6px rgba(0,0,0,0.7)', opacity: prog(f - from, 0, 6)}}>{text}</div>
) : null;

// ---------- 光线：分带接缝的细白光（R0 分带、画框条的边）----------
const Seam: React.FC<{y: number}> = ({y}) => (
  <div style={{position: 'absolute', left: 0, right: 0, top: y - 2, height: 4, background: 'rgba(255,255,255,0.82)',
    boxShadow: '0 0 14px 3px rgba(255,255,255,0.45), 0 0 40px 6px rgba(255,236,200,0.25)'}} />
);

const camera = (move: string, p: number) => {
  if (move === 'pan-l') return `scale(1.08) translateX(${(0.5 - p) * 5}%)`;
  if (move === 'pan-r') return `scale(1.08) translateX(${(p - 0.5) * 5}%)`;
  if (move === 'pull') return `scale(${1.07 - 0.07 * p})`;
  if (move === 'hold') return `scale(${1.02 + 0.015 * p})`;
  return `scale(${1 + 0.07 * p})`;
};
const Media: React.FC<{src?: string; img?: string; move: string; p: number; style?: React.CSSProperties; dim?: string}> = ({src, img, move, p, style, dim}) => {
  const st: React.CSSProperties = {position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', transform: camera(move, p),
    filter: dim || 'saturate(1.02) contrast(1.04)', ...style};
  if (img) return <Img src={staticFile(img)} style={st} />;
  if (src) return <OffthreadVideo src={staticFile(src)} muted style={st} />;
  return null;
};
const Missing: React.FC<{s: any}> = ({s}) => (
  <div style={{position: 'absolute', inset: 0, background: '#16130F', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 80,
    color: '#D8A863', fontSize: 40, fontFamily: F.serif, textAlign: 'center', lineHeight: 1.5}}>{s.id} · {s.need || '待补素材'}<br />（{s.layout || 'full'}）</div>
);

// ---------- ④ B-roll 的六种画面处理（在 Sequence 里，帧号是本镜局部帧）----------
const BRoll: React.FC<{s: any}> = ({s}) => {
  const f = useCurrentFrame();
  const dur = s.to - s.from;
  const p = interpolate(f, [0, dur], [0, 1], {...clamp, easing: ease.inOut});
  const move = s.move || 'push';
  const lay = s.layout || 'full';
  const has = s.clip || s.img;
  const dim = s.type === 'G' ? 'blur(9px) brightness(0.42) saturate(0.85)' : undefined;
  if (!has && s.type !== 'G') return <AbsoluteFill><Missing s={s} /></AbsoluteFill>;

  if (lay === 'bands3') {
    // 三条分带：同一题材的三段素材上下叠，入场时上下两条从两侧滑进来（R0 t1–3：钱→点钞→钱）
    const [y0, y1, y2, y3] = FB.bands3;
    const clips: string[] = [s.clip, ...(s.clips || [])];
    const slide = interpolate(f, [0, 8], [1, 0], {...clamp, easing: ease.out});
    const rows = [[y0, y1, -1], [y1, y2, 0], [y2, y3, 1]] as const;
    return (
      <AbsoluteFill style={{background: '#0D0B09'}}>
        {rows.map(([a, b, dir], i) => (
          <div key={i} style={{position: 'absolute', left: 0, top: a, width: 1080, height: b - a, overflow: 'hidden',
            transform: `translateX(${dir * slide * 110}%)`}}>
            {clips[i] ? <Media src={clips[i]} move={i === 1 ? 'push' : i === 0 ? 'pan-l' : 'pan-r'} p={p} />
              : <Media src={clips[0]} move={i === 0 ? 'pan-r' : 'pan-l'} p={p} />}
          </div>
        ))}
        <Seam y={y1} /><Seam y={y2} />
      </AbsoluteFill>
    );
  }
  if (lay === 'glowband') {
    const sp = FB.glowband.split;
    return (
      <AbsoluteFill style={{background: '#0D0B09'}}>
        <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: sp, overflow: 'hidden'}}><Media src={s.clip} img={s.img} move={move} p={p} /></div>
        <div style={{position: 'absolute', left: 0, top: sp, width: 1080, height: 1920 - sp, overflow: 'hidden',
          clipPath: `inset(${interpolate(f, [0, 9], [100, 0], {...clamp, easing: ease.out})}% 0 0 0)`}}>
          {(s.clips || [])[0] ? <Media src={s.clips[0]} move="pan-r" p={p} dim="brightness(0.86) saturate(1.0) contrast(1.04)" /> : null}
        </div>
        <Seam y={sp} />
      </AbsoluteFill>
    );
  }
  if (lay === 'doc') {
    // 原文截图：一张纸放在暖暗底上，缓慢上移；说到那句时荧光带从左扫到右（R2 政策原文页的做法）
    const iw = s.iw || 1080, ih = s.ih || 1920;
    const cw = 900, chh = Math.round(ih * cw / iw);
    const viewH = 1020;   // 纸面 250–1270，字幕在 1440（白字不压白纸）
    const travel = Math.max(0, Math.min(chh - viewH, 260));
    const y = interpolate(f, [0, dur], [0, -travel], {...clamp, easing: ease.inOut});
    const hl = s.hl;   // [x, y, w, h]，原图像素
    const sweep = hl ? interpolate(f, [(s.hlAt ?? s.from + 12) - s.from, (s.hlAt ?? s.from + 12) - s.from + 12], [0, 1], {...clamp, easing: ease.out}) : 0;
    return (
      <AbsoluteFill style={{background: 'radial-gradient(120% 70% at 50% 30%, #2A241D 0%, #120F0C 70%)'}}>
        <div style={{position: 'absolute', left: (1080 - cw) / 2, top: 250, width: cw, height: viewH, overflow: 'hidden', borderRadius: 10,
          boxShadow: '0 40px 90px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.12)'}}>
          <div style={{position: 'absolute', left: 0, top: y, width: cw, height: chh}}>
            <Img src={staticFile(s.img)} style={{width: cw, height: chh}} />
            {hl ? <div style={{position: 'absolute', left: hl[0] * cw / iw - 6, top: hl[1] * cw / iw - 4, width: (hl[2] * cw / iw + 12) * sweep,
              height: hl[3] * cw / iw + 8, background: 'rgba(255,214,90,0.45)', mixBlendMode: 'multiply', borderRadius: 4}} /> : null}
          </div>
        </div>
      </AbsoluteFill>
    );
  }
  // full／pip／glow／ring／band：底都是一条满幅素材（band 已由 build.py 烘成「画框条＋同素材虚化底」）
  return (
    <AbsoluteFill style={{background: '#0D0B09'}}>
      {has ? <Media src={s.clip} img={s.img} move={lay === 'band' ? 'hold' : move} p={p} dim={dim} /> : null}
      {lay === 'band' && s.band ? <><Seam y={s.band.y} /><Seam y={s.band.y + s.band.h} /></> : null}
    </AbsoluteFill>
  );
};

// ---------- 她的小窗：方窗（磨砂边）／光晕圆／细环圆。画在全局帧上，嘴型和原片同步 ----------
const Speaker: React.FC<{w: number; h: number; share: number; faceY?: number; f: number; from: number; to: number}> = ({w, h, share, faceY = 0.42, f, from, to}) => {
  const fw = FACE.w || 0.3;
  const kCover = Math.max(w / 1080, h / 1920);
  const k0 = Math.max(kCover, share * w / (fw * 1080));
  const k = k0 * (1 + 0.04 * interpolate(f, [from, Math.max(to, from + 1)], [0, 1], clamp));   // 小窗也慢推，停顿处不冻
  const r = faceFit({x: 0, y: 0, w, h}, FACE, k, faceY);
  return <OffthreadVideo src={staticFile(tl.aroll.src)} muted style={{position: 'absolute', left: r.left, top: r.top, width: r.width, height: r.height,
    maxWidth: 'none', filter: 'saturate(1.02) contrast(1.03)'}} />;
};
const Pip: React.FC<{f: number; s: any}> = ({f, s}) => {
  const lay = s.layout || 'full';
  if (!['pip', 'glow', 'glowband', 'ring', 'doc'].includes(lay)) return null;
  const local = f - s.from;
  const p = prog(local, -2, 8);
  if (lay === 'pip') {
    const P_ = FB.pip;
    const x = s.pip_pos === 'left' ? 120 : s.pip_pos === 'right' ? 1080 - 120 - P_.w : (1080 - P_.w) / 2;
    return (
      <div style={{position: 'absolute', left: x - P_.frame, top: P_.y - P_.frame, width: P_.w + P_.frame * 2, height: P_.h + P_.frame * 2,
        borderRadius: P_.r + P_.frame, background: 'rgba(255,255,255,0.26)', border: '1.5px solid rgba(255,255,255,0.55)', backdropFilter: 'blur(14px)',
        boxShadow: '0 28px 70px rgba(0,0,0,0.45)', opacity: p, transform: `scale(${0.96 + 0.04 * p})`}}>
        <div style={{position: 'absolute', left: P_.frame, top: P_.frame, width: P_.w, height: P_.h, borderRadius: P_.r, overflow: 'hidden', background: '#222'}}>
          <Speaker w={P_.w} h={P_.h} share={0.46} faceY={0.38} f={f} from={s.from} to={s.to} />
        </div>
      </div>
    );
  }
  if (lay === 'glow' || lay === 'glowband') {
    const G = lay === 'glow' ? FB.glow : FB.glowband;
    const R_ = G.d / 2;
    const mask = 'radial-gradient(circle at 50% 50%, #000 58%, rgba(0,0,0,0.75) 68%, rgba(0,0,0,0) 78%)';
    return (
      <div style={{position: 'absolute', left: G.cx - R_, top: G.cy - R_, width: G.d, height: G.d, opacity: p}}>
        <div style={{position: 'absolute', inset: -G.d * 0.16, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,214,150,0.42) 40%, rgba(255,200,120,0.16) 56%, rgba(255,200,120,0) 70%)'}} />
        <div style={{position: 'absolute', inset: 0, WebkitMaskImage: mask, maskImage: mask, overflow: 'hidden'}}>
          <Speaker w={G.d} h={G.d} share={0.36} faceY={0.44} f={f} from={s.from} to={s.to} />
        </div>
      </div>
    );
  }
  const Rg = FB.ring;
  return (
    <div style={{position: 'absolute', left: Rg.cx - Rg.d / 2, top: Rg.cy - Rg.d / 2, width: Rg.d, height: Rg.d, borderRadius: '50%', overflow: 'hidden',
      boxShadow: `0 0 0 ${Rg.line}px rgba(255,255,255,0.94), 0 18px 44px rgba(0,0,0,0.5)`, opacity: p, background: '#222'}}>
      <Speaker w={Rg.d} h={Rg.d} share={0.5} faceY={0.46} f={f} from={s.from} to={s.to} />
    </div>
  );
};

// ---------- 插条（盖在她的画面上，她还在）：顶部／底部／角落小图 ----------
const Inserts: React.FC = () => (
  <>
    {(tl.inserts || []).map((x: any, i: number) => {
      const top = x.pos === 'top' ? 0 : x.pos === 'bottom' ? FB.bottomBand : 1360;
      const h = x.pos === 'top' ? FB.topBand : x.pos === 'bottom' ? 1920 - FB.bottomBand : 240;
      const left = x.pos === 'corner' ? 72 : 0, w = x.pos === 'corner' ? 360 : 1080;
      return (
        <Sequence key={i} from={x.from} durationInFrames={x.to - x.from}>
          <InsertBody x={x} top={top} h={h} left={left} w={w} />
        </Sequence>
      );
    })}
  </>
);
const InsertBody: React.FC<{x: any; top: number; h: number; left: number; w: number}> = ({x, top, h, left, w}) => {
  const f = useCurrentFrame();
  const dur = x.to - x.from;
  const p = interpolate(f, [0, dur], [0, 1], {...clamp, easing: ease.inOut});
  const rev = interpolate(f, [0, 8], [100, 0], {...clamp, easing: ease.out});
  const corner = x.pos === 'corner';
  const clip = x.pos === 'top' ? `inset(0 0 ${rev}% 0)` : x.pos === 'bottom' ? `inset(${rev}% 0 0 0)` : `inset(0 ${rev}% 0 0 round 16px)`;
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left, top, width: w, height: h, overflow: 'hidden', clipPath: clip, borderRadius: corner ? 16 : 0,
        boxShadow: corner ? '0 0 0 4px rgba(255,255,255,0.92), 0 16px 40px rgba(0,0,0,0.45)' : 'none'}}>
        <Media src={x.clip} img={x.img} move={x.move || (x.pos === 'top' ? 'pan-l' : 'push')} p={p} />
      </div>
      {!corner && rev < 99 ? <Seam y={x.pos === 'top' ? h : top} /> : null}
    </AbsoluteFill>
  );
};

// ---------- 屏上字的三种排法：堆叠清单／步骤标题／散点关键词（R0 t79、t90–105、t150）----------
const Texts: React.FC<{f: number}> = ({f}) => (
  <>
    {textsAt(f).map((x: any, i: number) => {
      if (x.kind === 'step') {
        const l = x.lines[0];
        const w = 100 - 100 * prog(f - l.from, -2, 5);
        return (
          <div key={i} style={{position: 'absolute', left: FB.stepX, top: FB.stepTop, fontFamily: F.serif, fontWeight: 900, fontSize: FB.stepSize, lineHeight: 1,
            color: INK, textShadow: l.tone ? undefined : SHADOW, whiteSpace: 'nowrap', clipPath: `inset(-20% ${w}% -20% 0)`}}>
            {l.tone ? <span style={{display: 'inline-block', filter: METAL_FX}}><span style={metal(l.tone)}>{l.t}</span></span> : l.t}
          </div>
        );
      }
      if (x.kind === 'scatter') {
        const slots = [[170, 1010], [760, 1010], [220, 1200], [700, 1200], [460, 1330]];
        return (
          <React.Fragment key={i}>
            {x.lines.filter((l: any) => f >= l.from - 2).map((l: any, k: number) => {
              const [sx, sy] = l.xy || slots[k % slots.length];
              return (
                <div key={k} style={{position: 'absolute', left: sx, top: sy, fontFamily: F.serif, fontWeight: 900, fontSize: l.size || 80, whiteSpace: 'nowrap',
                  clipPath: `inset(-20% ${100 - 100 * prog(f - l.from, -2, 5)}% -20% 0)`}}>
                  <span style={{display: 'inline-block', filter: METAL_FX}}><span style={metal(l.tone || 'gold')}>{l.t}</span></span>
                </div>
              );
            })}
          </React.Fragment>
        );
      }
      // stack：一行一行长出来，最多 3 行（第 4 行起把最早一行顶掉——R0 从不超过 3 行）
      const shown = x.lines.filter((l: any) => f >= l.from - 2);
      const vis = shown.slice(-3);
      const center = x.align === 'center';
      const num = !!x.num;   // 序号列左对齐、文字列左对齐，整块居中（说「1234」时用）
      const numW = num ? 90 : 0, gapN = num ? 22 : 0;
      const maxEm = Math.max(...x.lines.map((l: any) => emW(l.t)), 1);
      const avail = (center ? 960 : 1080 - FB.stackX - 60) - numW - gapN;
      const usize = Math.max(48, Math.min(x.size || FB.stackSize, Math.floor(avail / maxEm)));
      const blockW = numW + gapN + Math.ceil(maxEm * usize);
      return (
        <div key={i} style={{position: 'absolute', left: num ? (center ? (1080 - blockW) / 2 : FB.stackX) : center ? 60 : FB.stackX, right: !num && center ? 60 : undefined,
          top: x.top || FB.stackTop, display: 'flex', flexDirection: 'column', alignItems: num ? 'flex-start' : center ? 'center' : 'flex-start'}}>
          {vis.map((l: any, k: number) => {
            const size = num ? usize : fitSize(l.t, center ? 960 : 1080 - FB.stackX - 60, l.size || x.size || FB.stackSize, 48);
            const tone = l.tone || x.tone;
            const idx = x.lines.indexOf(l);
            const fx = tone === 'silver' ? SILVER_FX : METAL_FX;
            const body = tone === 'white'
              ? <span style={{color: INK, textShadow: SHADOW}}>{l.t}</span>
              : <span style={{display: 'inline-block', filter: fx}}><span style={metal(tone || 'gold')}>{l.t}</span></span>;
            return (
              <div key={l.t + k} style={{height: FB.stackPitch, display: 'flex', alignItems: 'center', fontFamily: F.serif, fontWeight: 900, fontSize: size,
                whiteSpace: 'nowrap', clipPath: `inset(-20% ${100 - 100 * prog(f - l.from, -2, 5)}% -20% 0)`}}>
                {num ? <span style={{display: 'inline-block', width: numW, filter: fx}}>
                  <span style={{...metal(tone === 'silver' ? 'silver' : 'gold'), fontFamily: F.didot, fontWeight: 700, fontSize: Math.round(size * 1.05)}}>{idx + 1}</span></span> : null}
                <span style={{marginLeft: gapN}}>{body}</span>
              </div>
            );
          })}
        </div>
      );
    })}
  </>
);

// ---------- 常驻进度坞（R2 的税目表做法）：讲「四个变化／三类资产」时，底部一条玻璃坞跟着点亮 ----------
const Tracker: React.FC<{f: number; s: Shot | null}> = ({f, s}) => {
  const T = tl.tracker;
  // 一处只放一种字：堆叠清单、散点关键词在场时进度坞让位（10-29 v1 自查：「居民个人」压在坞上）
  if (!T || !at(f, T.from, T.to) || !isFaceFrame(s) || textsAt(f).some((x: any) => x.kind === 'stack' || x.kind === 'scatter')
    || (insertAt(f) || {}).pos === 'bottom') return null;   // 底部插条在场时也让位（10-29 v2 样片：坞压在插条上）
  const items: any[] = T.items || [];
  const cur = items.reduce((a: number, it: any, i: number) => (f >= it.from ? i : a), -1);
  const n = Math.max(items.length, 1);
  const X = 72, Y = 1330, W = 936, H = 196;
  const titleW = T.title ? 200 : 0;
  const cw = (W - 36 - titleW - (n - 1) * 14) / n;
  const p = prog(f - T.from, 0, 8);
  return (
    <div style={{position: 'absolute', left: X, top: Y, width: W, height: H, borderRadius: 30, background: 'rgba(22,18,14,0.66)',
      border: '1.5px solid rgba(255,231,190,0.24)', backdropFilter: 'blur(16px)', boxShadow: '0 24px 60px rgba(0,0,0,0.45)',
      opacity: p, clipPath: `inset(0 0 ${100 - 100 * p}% 0 round 30px)`}}>
      {T.title ? (
        <div style={{position: 'absolute', left: 30, top: 0, width: titleW - 20, height: H, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
          <div style={{fontFamily: F.serif, fontWeight: 900, fontSize: fitSize(T.title, titleW - 30, 42, 28), color: '#F5F0E6', lineHeight: 1.15}}>{T.title}</div>
          {T.en ? <div style={{marginTop: 8, fontFamily: F.sans, fontSize: 15, letterSpacing: '0.22em', color: 'rgba(245,240,230,0.5)', textTransform: 'uppercase'}}>{T.en}</div> : null}
        </div>
      ) : null}
      {items.map((it: any, i: number) => {
        const on = i === cur, done = i < cur;
        return (
          <div key={i} style={{position: 'absolute', left: 18 + titleW + i * (cw + 14), top: 22, width: cw, height: H - 44, borderRadius: 20,
            background: on ? 'linear-gradient(180deg, rgba(232,194,127,0.26), rgba(232,194,127,0.10))' : 'rgba(255,255,255,0.05)',
            border: on ? '2px solid rgba(240,207,140,0.9)' : '1.5px solid rgba(255,255,255,0.12)', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 6}}>
            <div style={{fontFamily: F.didot, fontWeight: 700, fontSize: 34, lineHeight: 1, color: on ? '#F0CF8C' : done ? 'rgba(240,207,140,0.6)' : 'rgba(255,255,255,0.32)'}}>
              {it.n || String(i + 1).padStart(2, '0')}</div>
            <div style={{fontFamily: F.serif, fontWeight: 900, fontSize: fitSize(it.t, cw - 20, 34, 22), lineHeight: 1.2, whiteSpace: 'nowrap',
              color: on ? '#FFF6E2' : done ? 'rgba(245,240,230,0.66)' : 'rgba(245,240,230,0.34)'}}>{it.t}</div>
          </div>
        );
      })}
    </div>
  );
};

const Layers: React.FC<{f: number; s: Shot | null}> = ({f, s}) => (
  <>
    <Inserts />
    <Tracker f={f} s={s} />
    <Texts f={f} />
  </>
);

// ---------- G 标题卡／数字卡（R1 的章节卡：暗底、金尘、光束，金属大字＋英文副行）----------
// under：数字卡／词卡底下垫一层她本人的虚化原片（同步、压暗），卡在屏的 2–3 秒画面不冻（10-29 qa：三张大字卡各冻 2–3s）
const TitleBg: React.FC<{local: number; under?: boolean}> = ({local, under}) => {
  const dots = React.useMemo(() => Array.from({length: 120}, (_, i) => {
    const r = (n: number) => { const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453; return x - Math.floor(x); };
    return {x: r(1) * 1080, y: r(2) * 1920, s: 1 + r(3) * 3, a: 0.25 + r(4) * 0.6, v: 0.3 + r(5) * 0.8};
  }), []);
  // 金色光斑：缓慢上浮、左右轻摆、明暗呼吸——卡在屏 2–3 秒，背景始终在动（文字层不动）
  const orbs = React.useMemo(() => Array.from({length: 16}, (_, i) => {
    const r = (n: number) => { const x = Math.sin(i * 91.17 + n * 13.7) * 24634.6345; return x - Math.floor(x); };
    return {x: r(1) * 1080, y: r(2) * 2100, r: 34 + r(3) * 80, v: 1.4 + r(4) * 1.6, a: 0.45 + r(5) * 0.45};
  }), []);
  return (
    <AbsoluteFill style={{background: 'radial-gradient(70% 45% at 50% 46%, #3A2C18 0%, #17110A 55%, #080605 100%)', overflow: 'hidden'}}>
      {under ? <>
        <OffthreadVideo src={staticFile(tl.aroll.src)} muted style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover',
          filter: 'blur(26px) brightness(0.55) saturate(0.7)', transform: `scale(${1.12 + 0.0006 * local})`}} />
        <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(70% 45% at 50% 46%, rgba(58,44,24,0.55) 0%, rgba(23,17,10,0.72) 55%, rgba(8,6,5,0.86) 100%)'}} />
      </> : null}
      <div style={{position: 'absolute', left: -540, top: -40, width: 2160, height: 2000, opacity: 0.28,
        background: 'repeating-conic-gradient(from 0deg at 50% 50%, rgba(255,214,150,0.0) 0deg, rgba(255,214,150,0.35) 2deg, rgba(255,214,150,0.0) 5deg, rgba(255,214,150,0.0) 14deg)',
        transform: `rotate(${local * 0.16}deg)`, WebkitMaskImage: 'radial-gradient(circle at 50% 50%, #000 0%, transparent 46%)',
        maskImage: 'radial-gradient(circle at 50% 50%, #000 0%, transparent 46%)'}} />
      {orbs.map((o, i) => (
        <div key={'o' + i} style={{position: 'absolute', left: o.x + Math.sin(local / 40 + i) * 26 - o.r, top: ((o.y - local * o.v) % 2100 + 2100) % 2100 - 120 - o.r,
          width: o.r * 2, height: o.r * 2, borderRadius: '50%', filter: 'blur(6px)',
          background: 'radial-gradient(circle, rgba(246,218,160,0.55) 0%, rgba(246,218,160,0.18) 55%, rgba(246,218,160,0) 72%)',
          opacity: o.a * (0.65 + 0.35 * Math.sin(local / 14 + i * 1.7))}} />
      ))}
      {dots.map((d, i) => (
        <div key={i} style={{position: 'absolute', left: d.x, top: (d.y - local * d.v * 1.2 + 1920) % 1920, width: d.s, height: d.s, borderRadius: d.s,
          background: '#F3D59A', opacity: d.a * (0.6 + 0.4 * Math.sin(local / 9 + i))}} />
      ))}
    </AbsoluteFill>
  );
};
const Figure: React.FC<{f: number; s: Shot}> = ({f, s}) => {
  const fig = s.figure || {};
  const local = f - s.from;
  const rv = Math.max((fig.revealFrom ?? s.from + 6) - s.from, 6);
  const wipeV = interpolate(local, [rv - 3, rv + 2], [100, 0], {...clamp, easing: ease.out});
  const lab = interpolate(local, [0, 8], [100, 0], {...clamp, easing: ease.out});
  const isNum = fig.kind === 'number';
  const v = String(fig.value || '');
  const size = isNum ? Math.min(300, Math.floor(860 / Math.max(emW(v) + (fig.unit ? 1.3 : 0), 0.8)))
    : fitSize(v, 900, v.length <= 2 ? 250 : 190, 110);
  const yMid = 780;   // 整块落在 1300 以上，给低位字幕（1440）让出地方
  return (
    <AbsoluteFill>
      {!s.bg ? <TitleBg local={local} under /> : null}
      <div style={{position: 'absolute', left: 0, right: 0, top: yMid - size * 0.5 - 120, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
        {fig.label ? <div style={{clipPath: `inset(0 ${lab}% 0 0)`, fontFamily: F.serif, fontWeight: 600, fontSize: 40, letterSpacing: '0.18em',
          color: '#E8C27F', textShadow: '0 2px 10px rgba(0,0,0,0.6)', whiteSpace: 'nowrap', marginBottom: 34}}>{fig.label}</div> : null}
        <div style={{position: 'relative', clipPath: `inset(-20% ${wipeV}% -20% 0)`, display: 'flex', alignItems: 'baseline', gap: 14, whiteSpace: 'nowrap'}}>
          <span style={{display: 'inline-block', filter: METAL_FX}}>
            <span style={{...metal('gold'), fontFamily: isNum ? F.didot : F.serif, fontWeight: isNum ? 700 : 900, fontSize: size, lineHeight: 1.05,
              letterSpacing: isNum ? '-0.02em' : '0.04em'}}>{v}</span>
          </span>
          {fig.unit ? <span style={{display: 'inline-block', filter: METAL_FX}}><span style={{...metal('gold'), fontFamily: F.serif, fontWeight: 900,
            fontSize: Math.round(size * 0.3)}}>{fig.unit}</span></span> : null}
        </div>
        {fig.en ? <div style={{marginTop: 26, fontFamily: F.sans, fontWeight: 500, fontSize: 26, letterSpacing: '0.34em', textTransform: 'uppercase',
          color: 'rgba(255,255,255,0.72)', clipPath: `inset(0 ${interpolate(local, [rv + 2, rv + 12], [100, 0], clamp)}% 0 0)`}}>{fig.en}</div> : null}
        <div style={{marginTop: 30, width: 240, height: 2, background: 'linear-gradient(90deg, transparent, #E8C27F, transparent)',
          transform: `scaleX(${interpolate(local, [4, rv + 8], [0, 1], {...clamp, easing: ease.inOut})})`}} />
      </div>
    </AbsoluteFill>
  );
};

// ---------- I 信息卡：玻璃（R1／R2，暖金）；list 可换 R0 的「皱纸单」----------
const GLASS: InfoStyle = {
  area: {x: 72, y: 420, w: 936, h: 760}, ink: '#FFF8EA', mute: 'rgba(255,248,234,0.90)', accent: '#F4CF86', accent2: 'rgba(244,207,134,0.5)',
  card: 'rgba(24,19,14,0.84)', unitInline: true, mark: 'color', titleFont: F.serif, titleWeight: 900, numFont: F.didot, numWeight: 700, radius: 28, pad: 40, gap: 24,
  presenter: {mode: 'pip', rect: {x: FB.ring.cx - FB.ring.d / 2, y: 150, w: FB.ring.d, h: FB.ring.d}, radius: FB.ring.d / 2, border: '5px solid rgba(255,255,255,0.92)'},
  Surface: ({x, y, w, h, on}: any) => (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, borderRadius: 28,
      background: on ? 'linear-gradient(180deg, rgba(64,50,30,0.90), rgba(30,24,18,0.90))' : 'linear-gradient(180deg, rgba(44,37,30,0.86), rgba(24,20,16,0.86))',
      border: on ? '1.5px solid rgba(244,207,134,0.7)' : '1.5px solid rgba(255,231,190,0.28)',
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.10), 0 26px 70px rgba(0,0,0,0.5)'}} />
  ),
  WindowBg: () => {
    const f = useCurrentFrame();
    return (
      <AbsoluteFill>
        <OffthreadVideo src={staticFile(tl.aroll.src)} muted style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover',
          filter: 'blur(28px) brightness(0.5) saturate(0.85)', transform: 'scale(1.15)'}} />
        <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(80% 50% at 50% 30%, rgba(216,168,99,0.18), rgba(8,6,5,0.34) 70%)'}} />
        <div style={{position: 'absolute', inset: 0, backgroundImage: 'radial-gradient(rgba(255,240,210,0.08) 1px, transparent 1.6px)', backgroundSize: '28px 28px',
          opacity: 0.6 + 0.0 * f}} />
      </AbsoluteFill>
    );
  },
  areaCard: ['quote', 'chart'],
  sourcePrefix: '来源 · ',
};
// 皱纸单（R0 t179–186）：整屏皱白纸，上方方窗里是她，下面金字一条一条长出来，居中
const PaperBg: React.FC = () => (
  <AbsoluteFill style={{background: '#EDEBE6'}}>
    <svg width={1080} height={1920} style={{position: 'absolute', inset: 0}}>
      <filter id="crumple"><feTurbulence type="fractalNoise" baseFrequency="0.012 0.018" numOctaves={4} seed={7} result="n" />
        <feDiffuseLighting in="n" lightingColor="#F7F5F0" surfaceScale={3.2}><feDistantLight azimuth={225} elevation={52} /></feDiffuseLighting></filter>
      <rect width={1080} height={1920} filter="url(#crumple)" />
    </svg>
    <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(90% 60% at 50% 40%, rgba(255,255,255,0.35), rgba(0,0,0,0.06))'}} />
  </AbsoluteFill>
);
const PaperList: React.FC<{f: number; s: any}> = ({f, s}) => {
  const info = s.info || {};
  const items: any[] = info.items || [];
  const P_ = FB.pip;
  const p = prog(f - s.from, -2, 8);
  return (
    <AbsoluteFill>
      <PaperBg />
      <div style={{position: 'absolute', left: (1080 - P_.w) / 2 - P_.frame, top: 150 - P_.frame, width: P_.w + P_.frame * 2, height: P_.h + P_.frame * 2,
        borderRadius: P_.r + P_.frame, background: 'rgba(200,200,200,0.45)', boxShadow: '0 18px 50px rgba(0,0,0,0.18)', opacity: p}}>
        <div style={{position: 'absolute', left: P_.frame, top: P_.frame, width: P_.w, height: P_.h, borderRadius: P_.r, overflow: 'hidden'}}>
          <Speaker w={P_.w} h={P_.h} share={0.46} faceY={0.38} f={f} from={s.from} to={s.to} />
        </div>
      </div>
      {(() => {
        // 序号列左对齐、文字列左对齐，整块在屏幕上水平居中（10-29 验片：「说四条」要有清楚的 1234）
        const numbered = info.numbered !== false && items.length > 1;
        const texts = items.map((it) => String(it.t || ''));
        const maxEm = Math.max(...texts.map((t) => emW(t)), 1);
        const numW = numbered ? 78 : 0, gapN = numbered ? 26 : 0;
        const size = Math.max(40, Math.min(66, Math.floor((960 - numW - gapN) / maxEm)));
        const blockW = numW + gapN + Math.ceil(maxEm * size);
        const fx = 'drop-shadow(0 0 1px rgba(80,46,6,0.85)) drop-shadow(0 2px 2px rgba(60,36,6,0.32))';
        const goldTxt: React.CSSProperties = {backgroundImage: GOLD_DEEP, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent'};
        return (
          <div style={{position: 'absolute', left: (1080 - blockW) / 2, top: 760, width: blockW}}>
            {items.filter((it) => f >= (it.revealAt ?? s.from) - 2).map((it, i) => (
              <div key={i} style={{height: 112, display: 'flex', alignItems: 'center', whiteSpace: 'nowrap',
                clipPath: `inset(-20% ${100 - 100 * prog(f - (it.revealAt ?? s.from), -2, 5)}% -20% 0)`}}>
                {numbered ? <span style={{display: 'inline-block', width: numW, filter: fx}}>
                  <span style={{...goldTxt, fontFamily: F.didot, fontWeight: 700, fontSize: Math.round(size * 1.05)}}>{i + 1}</span></span> : null}
                <span style={{display: 'inline-block', marginLeft: gapN, filter: fx}}>
                  <span style={{...goldTxt, fontFamily: F.serif, fontWeight: 900, fontSize: size}}>{it.t}</span></span>
              </div>
            ))}
          </div>
        );
      })()}
    </AbsoluteFill>
  );
};
const Info: React.FC<{f: number; s: Shot; face: any; src: string}> = (p) => {
  const info = (p.s as any).info || {};
  if (info.surface === 'paper' && info.kind === 'list') return <PaperList f={p.f} s={p.s} />;
  return <InfoCore {...p} st={GLASS} />;
};

const Photo: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <AbsoluteFill><TitleBg local={f - s.from} /><PhotoCore f={f} s={s} win={WIN} credit="rgba(255,255,255,0.7)" /></AbsoluteFill>
);
const PhoneFrame: React.FC<{f: number; s: Shot}> = ({f, s}) => (
  <PhoneFrameCore f={f} s={s} win={WIN} ph={{x: 230, y: 300, w: 480, h: 960, r: 54, bezel: 12, k: 0.95, faceY: 0.42, color: '#FFFFFF'}} />
);

// R0 没有名字条，结尾自己报名字；给了 speaker 就在开场左下给一条克制的小字（3.6 秒）
const NameTag: React.FC<{f: number; d: any}> = ({f, d}) => {
  if (!d || !d.name || !at(f, d.from, d.to)) return null;
  const p = prog(f - d.from, 0, 8) * (1 - prog(f - (d.to - 8), 0, 8));
  return (
    <div style={{position: 'absolute', left: 72, top: 1440, opacity: p}}>
      <div style={{fontFamily: F.serif, fontWeight: 900, fontSize: 48, color: INK, textShadow: SHADOW}}>{d.name}</div>
      {(d.lines || []).length ? <div style={{marginTop: 8, fontFamily: F.serif, fontWeight: 600, fontSize: 28, color: 'rgba(255,255,255,0.82)', textShadow: SHADOW}}>
        {(d.lines || []).join(' · ')}</div> : null}
    </div>
  );
};
const Tag: React.FC<{f: number; t: any}> = ({f, t}) => {
  if (!t || !t.text) return null;
  const p = prog(f - t.from, 0, 8);
  return (
    <div style={{position: 'absolute', left: 72, top: 1440, padding: '10px 22px 11px', borderRadius: 999, background: 'rgba(22,18,14,0.6)',
      border: '1.5px solid rgba(240,207,140,0.5)', fontFamily: F.serif, fontWeight: 600, fontSize: 28, letterSpacing: '0.08em', color: '#F5F0E6',
      opacity: p, backdropFilter: 'blur(10px)'}}>{t.text}</div>
  );
};
const EndCard: React.FC = () => null;      // R0 不做落版卡：结论在画中画里说完，回到她本人报名字、关注
const Cover: React.FC = () => null;        // R0 第一帧就是封面：刊头＋开场钩子大字幕压在她身上
const SplitLabels: React.FC = () => null;

export const fullbleed = {
  name: 'fullbleed', win: WIN, faceY: null, canvas: '#000', breathe: 0.02, halftone: 0,
  Under, Over, Masthead, Caption, NameTag, EndCard, Tag, Cover, Figure, Photo, SplitLabels, Label, PhoneFrame, Info, info: GLASS,
  BRoll, Pip, Layers, hideCaption, mastheadOn, noCover: true, capsAfterEnd: true, underBlur: 6,
  mastheadOnB: false, coverInWindow: true, seam: '#FFFFFF',
};
