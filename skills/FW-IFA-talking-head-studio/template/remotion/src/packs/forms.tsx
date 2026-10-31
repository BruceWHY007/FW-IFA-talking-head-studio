// 按内容结构换形式（2026-10-31）：数轴 scale／点阵 dots／前后拉杆 beforeafter／链条 flow／汇聚 converge／航线 route。
// 运动语法借自 video-shotcraft 的镜头卡（value-stagger-gradient、radial-wave、before-after-slider-scrub、draw-svg-trace、
// bezier-source-converge-merge、glow-flyline-moves），字体、配色、材质一律用风格包给的 InfoStyle——借动作，不借皮。
// 纪律（和 info.tsx 同一套）：文字层零 transform（只用 clip-path 揭开、不透明度降档）；数字不 count-up、在开口帧落定；
// 线条、圆点、图标这些非文字元素可以生长、弹出；每个条目按自己的原话锚点（items[].at → revealAt）出现；
// 落定后靠讲解人小窗与底层原片保持画面在动（qa 冻结只量画面窗），不额外撒光效。
import React from 'react';
import {Shot, clamp, prog, wipe} from './common';
import {fitSize} from './parts';
import {F, ease} from '../theme';
import {interpolate} from 'remotion';
import {ICONS, iconStroke} from './icons';
import type {InfoStyle} from './info';

export const FORM_KINDS = ['scale', 'dots', 'beforeafter', 'flow', 'converge', 'route'];

const appear = (f: number, at: number, d = 6) => wipe(f - at, 0, d);
const lr = (f: number, at: number, d = 6) => `inset(-14% ${appear(f, at, d)}% -14% 0)`;      // 左到右揭开
const down = (f: number, at: number, d = 8) => `inset(0 0 ${appear(f, at, d)}% 0)`;          // 上到下揭开

const NumText: React.FC<{v: string}> = ({v}) => (
  <>{String(v).split(/([–—-])/).map((c, i) => /^[–—-]$/.test(c)
    ? <span key={i} style={{display: 'inline-block', width: '0.36em', height: '0.045em', minHeight: 4, background: 'currentColor', margin: '0 0.14em', verticalAlign: '0.3em'}} />
    : <span key={i}>{c}</span>)}</>
);

export const Icon: React.FC<{name?: string; x: number; y: number; size: number; color: string; clip?: string; opacity?: number}> = ({name, x, y, size, color, clip, opacity}) => {
  const ic = name ? ICONS[name] : null;
  if (!ic) return null;
  return (
    <svg viewBox={`0 0 ${ic.vb} ${ic.vb}`} fill="none" stroke={color} strokeWidth={iconStroke(ic.vb, size)} strokeLinecap="round" strokeLinejoin="round"
      style={{position: 'absolute', left: x, top: y, width: size, height: size, overflow: 'visible', clipPath: clip, opacity}}
      dangerouslySetInnerHTML={{__html: ic.svg}} />
  );
};

const Title: React.FC<{t?: string; A: any; st: InfoStyle; f: number; at: number; y?: number}> = ({t, A, st, f, at, y}) =>
  t ? <div style={{position: 'absolute', left: A.x, top: y ?? A.y, width: A.w, fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(t, A.w, 58, 40),
    lineHeight: 1.2, color: st.ink, whiteSpace: 'nowrap', clipPath: lr(f, at, 6)}}>{t}</div> : null;

const Src: React.FC<{st: InfoStyle; text?: string; A: any; f: number; at: number}> = ({st, text, A, f, at}) =>
  text ? <div style={{position: 'absolute', left: A.x, top: A.y + A.h - 30, width: A.w, fontFamily: F.sans, fontSize: 22, letterSpacing: '0.06em',
    color: st.mute, clipPath: lr(f, at, 8)}}>{(st.sourcePrefix ?? '来源 · ') + text}</div> : null;

const cubic = (p: number[][], t: number) => {
  const u = 1 - t;
  return [0, 1].map((k) => u * u * u * p[0][k] + 3 * u * u * t * p[1][k] + 3 * u * t * t * p[2][k] + t * t * t * p[3][k]);
};
const pathD = (p: number[][]) => `M${p[0][0]},${p[0][1]} C${p[1][0]},${p[1][1]} ${p[2][0]},${p[2][1]} ${p[3][0]},${p[3][1]}`;

// 画线：pathLength=1 的描线（draw-svg-trace 的做法：笔头先行，闭合后再出内容）
const Stroke: React.FC<{d: string; p: number; color: string; w?: number; dash?: string; opacity?: number}> = ({d, p, color, w = 3, dash, opacity = 1}) => (
  <path d={d} pathLength={1} fill="none" stroke={color} strokeWidth={w} strokeLinecap="round" opacity={opacity}
    strokeDasharray={dash ? undefined : '1 1'} strokeDashoffset={dash ? undefined : 1 - p}
    style={dash ? {strokeDasharray: dash, clipPath: `inset(0 ${(1 - p) * 100}% 0 0)`} : undefined} />
);

export const FormCore: React.FC<{f: number; s: Shot; st: InfoStyle; t0: number}> = ({f, s, st, t0}) => {
  const info = (s as any).info || {};
  const A = st.area;
  const items: any[] = info.items || [];
  const ats: number[] = items.map((it, i) => it.revealAt ?? t0 + i * 12);
  const kids: React.ReactNode[] = [];
  const titleH = info.title ? 96 : 0;
  const body = st.bodyFont || F.sans;
  kids.push(<Title key="t" t={info.title} A={A} st={st} f={f} at={t0} />);

  // ---------- 数轴：几个同类数字落在同一把尺上（谁高谁低一眼看出来）----------
  if (info.kind === 'scale') {
    const vs = items.map((it) => Number(it.v));
    const lo = Math.min(...vs), hi = Math.max(...vs);
    const pad = (hi - lo) * 0.22 || Math.abs(hi) * 0.1 || 1;
    const vmin = info.min ?? lo - pad, vmax = info.max ?? hi + pad;
    const X0 = A.x + 30, W = A.w - 60;
    const axisY = A.y + titleH + (A.h - titleH - 40) * 0.5;
    const xOf = (v: number) => X0 + ((v - vmin) / (vmax - vmin)) * W;
    const pAxis = prog(f - t0, 0, 14, ease.inOut);
    kids.push(<div key="ax" style={{position: 'absolute', left: X0, top: axisY - 2, width: W * pAxis, height: 4, borderRadius: 2,
      background: `linear-gradient(90deg, ${st.mute}, ${st.ink})`, opacity: 0.55}} />);
    if (info.unit) kids.push(<div key="un" style={{position: 'absolute', left: X0 + W - 200, top: axisY + 16, width: 200, textAlign: 'right', fontFamily: body,
      fontSize: 24, letterSpacing: '0.12em', color: st.mute, clipPath: lr(f, t0 + 10, 8)}}>{info.unit}</div>);
    const order = items.map((it, i) => i).sort((a, b) => vs[a] - vs[b]);
    order.forEach((i, rank) => {
      const it = items[i];
      const at = ats[i];
      if (f < at - 2) return;
      const up = it.side ? it.side === 'up' : rank % 2 === 0;
      const me = !!it.me;
      const col = me ? st.accent : st.ink;
      const x = xOf(vs[i]);
      const stem = 118;
      const pStem = prog(f - at, 0, 8);
      const pop = interpolate(f - at, [0, 5, 10], [0, 1.35, 1], clamp);
      const tw = 360;
      const tx = Math.max(A.x, Math.min(A.x + A.w - tw, x - tw / 2));
      const nsz = fitSize(String(it.show ?? it.v), tw, me ? 96 : 76, 48);
      kids.push(
        <React.Fragment key={'m' + i}>
          <div style={{position: 'absolute', left: x - 1.5, top: up ? axisY - stem * pStem : axisY, width: 3, height: stem * pStem, background: col, opacity: me ? 1 : 0.7}} />
          <div style={{position: 'absolute', left: x - (me ? 15 : 11), top: axisY - (me ? 15 : 11), width: me ? 30 : 22, height: me ? 30 : 22, borderRadius: 30,
            background: col, transform: `scale(${pop})`, boxShadow: me ? `0 0 26px ${st.accent}` : 'none'}} />
          <div style={{position: 'absolute', left: tx, width: tw, textAlign: 'center', top: up ? axisY - stem - nsz - 52 : axisY + stem + 8,
            clipPath: lr(f, at + 4, 6)}}>
            {up ? <div style={{fontFamily: body, fontSize: 28, letterSpacing: '0.08em', color: me ? st.accent : st.mute, marginBottom: 6, whiteSpace: 'nowrap'}}>{it.label}</div> : null}
            <div style={{fontFamily: st.numFont, fontWeight: st.numWeight, fontSize: nsz, lineHeight: 1, color: col, whiteSpace: 'nowrap'}}><NumText v={String(it.show ?? it.v)} /></div>
            {!up ? <div style={{fontFamily: body, fontSize: 28, letterSpacing: '0.08em', color: me ? st.accent : st.mute, marginTop: 8, whiteSpace: 'nowrap'}}>{it.label}</div> : null}
          </div>
        </React.Fragment>
      );
    });
  }

  // ---------- 点阵：一百个点里亮起一部分（占比、排位、几成）----------
  if (info.kind === 'dots') {
    const it = items[0] || {};
    const at = ats[0] ?? t0 + 10;
    const n = Math.max(0, Math.min(100, Math.round(Number(info.value ?? it.value ?? 0) * 100)));
    const S = Math.min(A.h - titleH - 70, A.w * 0.54);
    const pitch = S / 10, d = pitch * 0.5;
    const gx = A.x + A.w - S, gy = A.y + titleH + (A.h - titleH - 40 - S) / 2;
    const fromBottom = info.from === 'bottom';
    for (let k = 0; k < 100; k++) {
      const r = Math.floor(k / 10), c = k % 10;
      const idx = fromBottom ? 99 - k : k;
      const lit = idx < n;
      const base = prog(f - t0 - (r + c) * 0.5, 0, 6);
      const wave = lit ? (r + c) * 1.1 : 0;
      const on = lit ? prog(f - at - wave, 0, 4) : 0;
      const sc = lit ? interpolate(f - at - wave, [0, 4, 9], [1, 1.4, 1], clamp) : 1;
      kids.push(<div key={'d' + k} style={{position: 'absolute', left: gx + c * pitch + (pitch - d) / 2, top: gy + r * pitch + (pitch - d) / 2, width: d, height: d,
        borderRadius: d, background: on > 0.5 ? st.accent : st.mute, opacity: on > 0.5 ? 1 : 0.2 * base, transform: `scale(${base * sc})`,
        boxShadow: on > 0.5 ? `0 0 ${d * 0.6}px ${st.accent2}` : 'none'}} />);
    }
    const lw = A.w - S - 40;
    const show = String(info.show ?? it.show ?? '');
    kids.push(
      <div key="dl" style={{position: 'absolute', left: A.x, top: gy + S * 0.18, width: lw}}>
        <div style={{fontFamily: st.numFont, fontWeight: st.numWeight, fontSize: fitSize(show, lw, 150, 64), lineHeight: 1, color: st.accent, whiteSpace: 'nowrap',
          clipPath: lr(f, at + 6, 6)}}><NumText v={show} /></div>
        <div style={{marginTop: 28, fontFamily: body, fontSize: 34, lineHeight: 1.45, color: st.ink, clipPath: down(f, at + 10, 8)}}>{info.label ?? it.label}</div>
      </div>
    );
  }

  // ---------- 前后拉杆：以前怎样、现在怎样（分割杆扫过处换成新的，先猛甩后慢扫）----------
  if (info.kind === 'beforeafter') {
    const [b, a] = [items[0] || {}, items[1] || {}];
    const at = ats[1] ?? t0 + 20;
    const pw = A.w, ph = Math.min(A.h - titleH - 70, 400), px = A.x, py = A.y + titleH + 10 + (A.h - titleH - 70 - ph) / 2;
    const sw = interpolate(f - at, [0, 6, 22], [0, 0.72, 1], {...clamp, easing: ease.out});
    const bx = pw * sw;
    const Side: React.FC<{it: any; dim: boolean}> = ({it, dim}) => (
      <div style={{position: 'absolute', left: 52, top: 0, height: ph, width: pw - 104, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
        <div style={{alignSelf: 'flex-start', padding: '8px 22px', borderRadius: 40, border: `1.5px solid ${dim ? st.mute : st.accent}`, fontFamily: body, fontSize: 30,
          letterSpacing: '0.2em', color: dim ? st.mute : st.accent}}>{it.tag}</div>
        <div style={{marginTop: 30, fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(String(it.t || ''), pw - 104 - (it.icon ? 170 : 0), 96, 48), lineHeight: 1.2,
          color: dim ? st.mute : st.ink, whiteSpace: 'nowrap', textDecoration: dim && it.strike ? 'line-through' : 'none'}}>{it.t}</div>
        {it.d ? <div style={{marginTop: 22, fontFamily: body, fontSize: 30, lineHeight: 1.5, color: st.mute}}>{it.d}</div> : null}
        {it.icon ? <Icon name={it.icon} x={pw - 104 - 140} y={ph / 2 - 70} size={140} color={dim ? st.mute : st.accent} opacity={dim ? 0.5 : 0.9} /> : null}
      </div>
    );
    kids.push(
      <div key="ba" style={{position: 'absolute', left: px, top: py, width: pw, height: ph, clipPath: down(f, t0 - 2, 8)}}>
        {st.Surface ? React.createElement(st.Surface, {x: 0, y: 0, w: pw, h: ph, seed: 2, on: sw > 0.5}) : null}
        <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 0 0 ${bx}px)`}}><Side it={b} dim={false} /></div>
        <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${pw - bx}px 0 0)`}}><Side it={a} dim={false} /></div>
        {sw > 0 && sw < 1 ? <div style={{position: 'absolute', left: bx - 2, top: 0, width: 4, height: ph, background: st.accent, boxShadow: `0 0 24px ${st.accent}`}} /> : null}
        {sw > 0 && sw < 1 ? <div style={{position: 'absolute', left: bx - 22, top: ph / 2 - 22, width: 44, height: 44, borderRadius: 44, background: st.accent}} /> : null}
      </div>
    );
  }

  // ---------- 链条：先后、因果、资金路径（节点按原话一个个出来，连线先画到、节点再落）----------
  if (info.kind === 'flow') {
    const nodes = items.map((it, i) => ({it, at: ats[i]})).filter((x) => !x.it.back);
    const back = items.map((it, i) => ({it, at: ats[i]})).find((x) => x.it.back);
    const n = Math.max(nodes.length, 1);
    const gap = 54;
    const nh = Math.min(172, (A.h - titleH - 40 - gap * (n - 1)) / n);
    const nw = A.w * (back ? 0.74 : 0.8);
    const xs = nodes.map((_, i) => A.x + (i % 2 === 0 ? 0 : (back ? A.w * 0.08 : A.w - nw)));
    const ys = nodes.map((_, i) => A.y + titleH + 10 + i * (nh + gap));
    const active = nodes.reduce((a, x, i) => (f >= x.at ? i : a), -1);
    const svg: React.ReactNode[] = [];
    nodes.forEach((x, i) => {
      if (i === 0) return;
      const p0 = [xs[i - 1] + nw / 2, ys[i - 1] + nh], p3 = [xs[i] + nw / 2, ys[i]];
      const pts = [p0, [p0[0], p0[1] + gap * 0.6], [p3[0], p3[1] - gap * 0.6], p3];
      const p = prog(f - (x.at - 8), 0, 8);
      svg.push(<Stroke key={'l' + i} d={pathD(pts)} p={p} color={st.accent} w={3} />);
      if (p > 0.95) svg.push(<path key={'h' + i} d={`M${p3[0] - 9},${p3[1] - 12} L${p3[0]},${p3[1] - 2} L${p3[0] + 9},${p3[1] - 12}`} fill="none" stroke={st.accent} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />);
    });
    if (back && nodes.length >= 2) {
      const L = nodes.length - 1;
      const p0 = [xs[L] + nw, ys[L] + nh / 2], p3 = [xs[0] + nw, ys[0] + nh / 2];
      const rx = A.x + A.w - 6;
      const pts = [p0, [rx, p0[1]], [rx, p3[1]], p3];
      const p = prog(f - back.at, 0, 16, ease.inOut);
      svg.push(<Stroke key="bk" d={pathD(pts)} p={p} color={st.accent2} w={3} />);
      if (p > 0.95) svg.push(<path key="bkh" d={`M${p3[0] + 14},${p3[1] - 9} L${p3[0] + 3},${p3[1]} L${p3[0] + 14},${p3[1] + 9}`} fill="none" stroke={st.accent2} strokeWidth={3} strokeLinecap="round" />);
      const mid = cubic(pts, 0.5);
      kids.push(<div key="bkt" style={{position: 'absolute', left: mid[0] - 130, top: mid[1] - 22, width: 120, textAlign: 'right', fontFamily: body, fontSize: 26,
        letterSpacing: '0.1em', color: st.accent, whiteSpace: 'nowrap', clipPath: lr(f, back.at + 10, 6)}}>{back.it.t}</div>);
    }
    kids.push(<svg key="fl" width={2000} height={2000} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>{svg}</svg>);
    nodes.forEach((x, i) => {
      if (f < x.at - 2) return;
      const on = i === active;
      const ic = x.it.icon;
      const tx = ic ? 34 + nh * 0.5 + 24 : 34;
      kids.push(
        <div key={'n' + i} style={{position: 'absolute', left: xs[i], top: ys[i], width: nw, height: nh, clipPath: down(f, x.at - 2, 7)}}>
          {st.Surface ? React.createElement(st.Surface, {x: 0, y: 0, w: nw, h: nh, seed: i + 11, on}) : null}
          {ic ? <Icon name={ic} x={30} y={nh * 0.25} size={nh * 0.5} color={on ? st.accent : st.mute} /> : null}
          <div style={{position: 'absolute', left: tx, right: 24, top: 0, height: nh, display: 'flex', flexDirection: 'column', justifyContent: 'center', opacity: on ? 1 : 0.62}}>
            <div style={{fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(String(x.it.t || ''), nw - tx - 30, Math.min(60, nh * 0.46), 36),
              lineHeight: 1.15, color: on ? st.accent : st.ink, whiteSpace: 'nowrap'}}>{x.it.t}</div>
            {x.it.d ? <div style={{marginTop: 8, fontFamily: body, fontSize: Math.min(30, nh * 0.22), color: st.mute, whiteSpace: 'nowrap'}}>{x.it.d}</div> : null}
          </div>
        </div>
      );
    });
  }

  // ---------- 汇聚：几件事共同决定一个结果（来源一个个出来，结果出来时金光沿每条线流进去）----------
  if (info.kind === 'converge') {
    const src = items.map((it, i) => ({it, at: ats[i]})).filter((x) => !x.it.result);
    const res = items.map((it, i) => ({it, at: ats[i]})).find((x) => x.it.result);
    const n = Math.max(src.length, 1);
    const cw = A.w / n;
    const sy = A.y + titleH + 6, ih = 84;
    const rw = A.w * 0.72, rh = 170;
    const rx = A.x + (A.w - rw) / 2, ry = A.y + A.h - 40 - rh;
    const svg: React.ReactNode[] = [];
    const resAt = res ? res.at : 1e9;
    src.forEach((x, i) => {
      const cx = A.x + cw * i + cw / 2;
      const p0 = [cx, sy + ih + 70], p3 = [A.x + A.w / 2 + (i - (n - 1) / 2) * 40, ry - 4];
      const pts = [p0, [p0[0], p0[1] + (p3[1] - p0[1]) * 0.55], [p3[0], p3[1] - (p3[1] - p0[1]) * 0.5], p3];
      const p = prog(f - x.at - 4, 0, 14, ease.inOut);
      svg.push(<Stroke key={'c' + i} d={pathD(pts)} p={p} color={f >= resAt ? st.accent : st.mute} w={f >= resAt ? 3.5 : 2.5} opacity={f >= resAt ? 1 : 0.6} />);
      const tr = prog(f - resAt - i * 3, 0, 16, ease.inOut);
      if (tr > 0 && tr < 1) {
        const q = cubic(pts, tr);
        svg.push(<circle key={'p' + i} cx={q[0]} cy={q[1]} r={9} fill={st.accent} style={{filter: `drop-shadow(0 0 10px ${st.accent})`}} />);
      }
      if (f < x.at - 2) return;
      kids.push(
        <div key={'s' + i} style={{position: 'absolute', left: A.x + cw * i, top: sy, width: cw, height: ih + 70, textAlign: 'center', clipPath: down(f, x.at - 2, 7)}}>
          <Icon name={x.it.icon} x={cw / 2 - 36} y={0} size={72} color={f >= resAt ? st.accent : st.ink} />
          <div style={{position: 'absolute', left: 8, width: cw - 16, top: x.it.icon ? ih + 6 : 20, fontFamily: st.titleFont, fontWeight: st.titleWeight,
            fontSize: fitSize(String(x.it.t || ''), cw - 24, 46, 28), color: st.ink, whiteSpace: 'nowrap'}}>{x.it.t}</div>
        </div>
      );
    });
    kids.push(<svg key="cv" width={2000} height={2000} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>{svg}</svg>);
    if (res && f >= res.at - 2) kids.push(
      <div key="r" style={{position: 'absolute', left: rx, top: ry, width: rw, height: rh, clipPath: down(f, res.at + 8, 8)}}>
        {st.Surface ? React.createElement(st.Surface, {x: 0, y: 0, w: rw, h: rh, seed: 21, on: true}) : null}
        <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: rh, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(String(res.it.t || ''), rw - 60, 60, 36), color: st.accent, whiteSpace: 'nowrap'}}>{res.it.t}</div>
          {res.it.d ? <div style={{marginTop: 10, fontFamily: body, fontSize: 28, color: st.mute, whiteSpace: 'nowrap'}}>{res.it.d}</div> : null}
        </div>
      </div>
    );
  }

  // ---------- 航线：两地、跨境、资金怎么走（地点落针，飞线连过去，光点沿线来回）----------
  if (info.kind === 'route') {
    const places = items.map((it, i) => ({it, at: ats[i]})).filter((x) => !x.it.back && !x.it.via);
    const via = items.map((it, i) => ({it, at: ats[i]})).find((x) => x.it.via);
    const back = items.map((it, i) => ({it, at: ats[i]})).find((x) => x.it.back);
    const top = A.y + titleH + 60, bot = A.y + A.h - 120;
    const P2 = [[A.x + 60, top + 20], [A.x + A.w - 60, bot]];
    const P3 = [[A.x + 70, top + 30], [A.x + A.w - 70, (top + bot) / 2], [A.x + 70, bot]];
    const pos = places.length >= 3 ? P3 : P2;
    const svg: React.ReactNode[] = [];
    const arcs: {pts: number[][]; at: number; col: string; rev?: boolean}[] = [];
    places.forEach((x, i) => {
      if (i === 0 || !pos[i]) return;
      const a = pos[i - 1], b = pos[i];
      const bend = (i % 2 ? 1 : -1) * 170;
      arcs.push({pts: [a, [a[0] + bend * 0.2, a[1] + (b[1] - a[1]) * 0.1 - 40], [b[0] - bend, b[1] - (b[1] - a[1]) * 0.35], b], at: x.at, col: st.accent});
    });
    if (back && places.length >= 2) {
      const a = pos[Math.min(places.length, pos.length) - 1], b = pos[0];
      arcs.push({pts: [a, [a[0] + 10, a[1] - 330], [b[0] + 420, b[1] + 40], b], at: back.at, col: st.accent2, rev: true});
    }
    arcs.forEach((r, k) => {
      const p = prog(f - r.at, 0, 16, ease.inOut);
      svg.push(<Stroke key={'a' + k} d={pathD(r.pts)} p={p} color={r.col} w={3} />);
      if (p >= 1) {
        const ph = ((f - r.at - 16) % 54) / 54;
        const q = cubic(r.pts, ph);
        svg.push(<circle key={'g' + k} cx={q[0]} cy={q[1]} r={8} fill={r.col} style={{filter: `drop-shadow(0 0 12px ${r.col})`}} />);
        const e = r.pts[3], c = r.pts[2];
        const ang = Math.atan2(e[1] - c[1], e[0] - c[0]);
        const h = (s: number) => `${e[0] - 18 * Math.cos(ang + s)},${e[1] - 18 * Math.sin(ang + s)}`;
        svg.push(<path key={'ah' + k} d={`M${h(0.5)} L${e[0]},${e[1]} L${h(-0.5)}`} fill="none" stroke={r.col} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />);
      }
    });
    kids.push(<svg key="rt" width={2000} height={2000} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>{svg}</svg>);
    places.forEach((x, i) => {
      if (!pos[i] || f < x.at - 2) return;
      const [cx, cy] = pos[i];
      const ring = ((f - x.at) % 60) / 60;
      const right = cx > A.x + A.w / 2;
      kids.push(
        <React.Fragment key={'pl' + i}>
          <div style={{position: 'absolute', left: cx - 40, top: cy - 40, width: 80, height: 80, borderRadius: 80, border: `2px solid ${st.accent}`,
            opacity: (1 - ring) * 0.7, transform: `scale(${0.4 + ring * 1.1})`}} />
          <div style={{position: 'absolute', left: cx - 13, top: cy - 13, width: 26, height: 26, borderRadius: 26, background: st.accent,
            transform: `scale(${interpolate(f - x.at, [0, 5, 10], [0, 1.3, 1], clamp)})`}} />
          <div style={{position: 'absolute', top: cy - 42, ...(right ? {right: 1080 - (cx - 44)} : {left: cx + 44}), textAlign: right ? 'right' : 'left', clipPath: lr(f, x.at + 4, 6)}}>
            <div style={{fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: 66, lineHeight: 1.1, color: st.ink, whiteSpace: 'nowrap'}}>{x.it.t}</div>
            {x.it.d ? <div style={{marginTop: 8, fontFamily: body, fontSize: 30, color: st.mute, whiteSpace: 'nowrap'}}>{x.it.d}</div> : null}
          </div>
        </React.Fragment>
      );
    });
    if (via && arcs[0]) {
      const m = cubic(arcs[0].pts, 0.5);
      kids.push(<div key="via" style={{position: 'absolute', left: m[0] - 110, top: m[1] - 26, width: 220, textAlign: 'center', clipPath: lr(f, via.at, 6)}}>
        <span style={{display: 'inline-block', padding: '8px 22px', borderRadius: 40, background: st.card, border: `1.5px solid ${st.accent}`, fontFamily: body,
          fontSize: 32, letterSpacing: '0.12em', color: st.accent, whiteSpace: 'nowrap'}}>{via.it.t}</span></div>);
    }
    if (back && arcs.length) {
      const m = cubic(arcs[arcs.length - 1].pts, 0.45);
      kids.push(<div key="bk" style={{position: 'absolute', left: m[0] - 110, top: m[1] - 24, width: 220, textAlign: 'center', clipPath: lr(f, back.at + 12, 6)}}>
        <span style={{display: 'inline-block', padding: '6px 18px', borderRadius: 40, background: st.card, border: `1.5px dashed ${st.accent}`, fontFamily: body, fontSize: 30,
          letterSpacing: '0.1em', color: st.ink, whiteSpace: 'nowrap'}}>{back.it.t}</span></div>);
    }
  }

  kids.push(<Src key="src" st={st} text={info.source} A={A} f={f} at={t0 + 14} />);
  return <>{kids}</>;
};
