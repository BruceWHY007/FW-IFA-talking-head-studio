// 信息卡（I 镜头）：quote 原文要点／compare 两边对比／list 几件事／timeline 时间线／chart 柱图。
// 数据格式通用（decompose 里写一次），材质由风格包给：剪报（K1）、网格（K2）、品牌面板（K3）、象牙纸签（A）、玻璃（B）、直接落字（C）。
// 同一句话在不同风格包里长得不一样，同一风格包里按内容出不同的卡——这就是「每支不一样」的第一层。
// 规矩：文字层零位移（只用 clip-path 揭开、不透明度降档）；数字不做 count-up；柱从 0 起、预测用斜线；每张卡有来源行。
import React from 'react';
import {OffthreadVideo, interpolate, staticFile} from 'remotion';
import {Rect, Shot, clamp, prog, wipe, faceFit} from './common';
import {emW, fitSize} from './parts';
import {F, ease} from '../theme';

export type Presenter = {mode: 'blur' | 'box' | 'pip' | 'polaroid'; rect?: Rect; radius?: number; border?: string; topBar?: string};
export type InfoStyle = {
  area: Rect;                 // 卡片内容区（画面窗内坐标）
  ink: string; mute: string; accent: string; accent2: string; card: string;
  mark: 'marker' | 'underline' | 'color' | 'circle';
  titleFont: string; titleWeight: number; numFont: string; numWeight: number; bodyFont?: string;
  radius: number; pad: number; gap: number;
  areaCard?: string[];        // 这些卡型画成「一整张卡」（盖在视频上的包要这样，否则字压在画面上）
  presenter: Presenter;
  Surface?: React.FC<{x: number; y: number; w: number; h: number; seed: number; on?: boolean}>;   // 卡面材质
  WindowBg?: React.FC;        // 非 blur 模式时铺满画面窗的底（桌面、网格、渐变）
  Circle?: React.FC<{x: number; y: number; w: number; h: number; p: number}>;  // K1 手画红圈
  sourcePrefix?: string;
};

const appear = (f: number, at: number, d = 6) => wipe(f - at, 0, d);   // 遮罩揭开的剩余百分比（100→0）

// 关键词标记：荧光笔（K1）、下划线（A/K2）、换色（B/C/K3）。画成文字自己的背景（跟着换行走，box-decoration-break），重点词整段不拆行。
// 第 5 轮之后：绝对定位的色块在重点词跨行时会塌成一条竖线（K1 原话卡实测），改成背景渐变按 backgroundSize 扫开
const Marked: React.FC<{t: string; hl?: [number, number] | null; at: number; f: number; st: InfoStyle}> = ({t, hl, at, f, st}) => {
  if (!hl) return <>{t}</>;
  const [a, b] = hl;
  const p = prog(f - at, 0, 8);
  const bg = st.mark === 'marker' ? 'linear-gradient(transparent 16%, rgba(218,207,8,0.82) 16%, rgba(218,207,8,0.82) 92%, transparent 92%)'
    : st.mark === 'underline' ? `linear-gradient(transparent 88%, ${st.accent} 88%)` : 'none';
  const col = st.mark === 'marker' ? st.ink : p > 0.3 ? st.accent : st.ink;
  return (
    <>
      {t.slice(0, a)}
      <span style={{color: col, whiteSpace: 'nowrap', backgroundImage: bg, backgroundRepeat: 'no-repeat', backgroundSize: `${p * 100}% 100%`,
        WebkitBoxDecorationBreak: 'clone', boxDecorationBreak: 'clone', padding: st.mark === 'marker' ? '0 4px' : 0}}>{t.slice(a, b)}</span>
      {t.slice(b)}
    </>
  );
};

// 讲解人：不在 blur 模式时，她缩进一个框里继续说（嘴型不断）——数据拿走舞台，人还在
const PresenterBox: React.FC<{st: InfoStyle; face: {cx: number; cy: number}; src: string; f: number; from: number}> = ({st, face, src, f, from}) => {
  const pr = st.presenter;
  if (pr.mode === 'blur' || !pr.rect) return null;
  const r = pr.rect;
  // 讲解人框慢推 8%：她停顿换气时框里也不冻住（第 6 轮样片：K1／K3 的小框在停顿处冻 0.5–0.8s）
  const k = Math.max(r.w / 1080, r.h / 1920) * (pr.mode === 'pip' ? 1.7 : 1.35) * (1 + 0.08 * Math.min(Math.max((f - from) / 150, 0), 1));
  const ff = faceFit({x: 0, y: 0, w: r.w, h: r.h}, face, k, pr.mode === 'pip' ? 0.52 : 0.46);
  const p = prog(f - from, -4, 4);   // 切点那一帧框已经出来一半（第 6 轮：K2 切进来先露空网格）
  return (
    <div style={{position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, overflow: 'hidden', borderRadius: pr.radius || 0,
      border: pr.border, boxSizing: 'border-box', clipPath: `inset(${(1 - p) * 100}% 0 0 0 round ${pr.radius || 0}px)`, background: '#222'}}>
      <OffthreadVideo src={staticFile(src)} muted style={{position: 'absolute', left: ff.left, top: ff.top, width: ff.width, height: ff.height, maxWidth: 'none'}} />
      {pr.topBar ? <div style={{position: 'absolute', left: 0, top: 0, right: 0, height: 6, background: pr.topBar}} /> : null}
    </div>
  );
};

const Source: React.FC<{st: InfoStyle; text?: string; x: number; y: number; w: number; f: number; at: number}> = ({st, text, x, y, w, f, at}) =>
  text ? (
    <div style={{position: 'absolute', left: x, top: y, width: w, fontFamily: F.sans, fontWeight: 400, fontSize: 22, lineHeight: 1.4, letterSpacing: '0.06em',
      color: st.mute, clipPath: `inset(0 ${appear(f, at, 8)}% 0 0)`}}>{(st.sourcePrefix ?? '来源 · ') + text}</div>
  ) : null;

export const InfoCore: React.FC<{f: number; s: Shot; st: InfoStyle; face: {cx: number; cy: number}; src: string}> = ({f, s, st, face, src}) => {
  const info = (s as any).info || {};
  const A = st.area;
  const t0 = s.from - 2;   // 卡片在切点前 4 帧就开始落、切点那一帧已经基本到位（K2 实测：晚 2 帧起会露 3 帧空网格＝闪白）
  const big = (st.areaCard || []).includes(info.kind);
  const S = big ? undefined : st.Surface;   // 一整张卡时，里面的条目不再各自有卡面
  const body = st.bodyFont || F.sans;
  const kids: React.ReactNode[] = [];
  const cardIn = (from: number) => `inset(0 0 ${appear(f, from - 2, 8)}% 0)`;

  if (info.kind === 'quote') {
    const text = String(info.text || '');
    const inner = A.w - st.pad * 2;
    // 字号：三行以内放得下的最大号（48–80）；卡片高度跟着内容走，竖向居中在内容区里
    let size = 80;
    while (size > 48 && Math.ceil((emW(text) * size) / inner) > 3) size -= 2;
    const lines = Math.ceil((emW(text) * size) / inner);
    const ch = st.pad * 2 + 46 + lines * size * 1.42 + (info.source ? 56 : 10);
    const qy = A.y + Math.max(0, (A.h - ch) / 2);
    kids.push(
      <div key="q" style={{position: 'absolute', left: A.x, top: qy, width: A.w, height: ch, clipPath: cardIn(t0)}}>
        {S || (big && st.Surface) ? React.createElement((S || st.Surface)!, {x: 0, y: 0, w: A.w, h: ch, seed: 1, on: true}) : null}
        {info.label ? <div style={{position: 'absolute', left: st.pad, top: st.pad - 6, fontFamily: body, fontWeight: 500, fontSize: 24, letterSpacing: '0.16em',
          color: st.mute}}>{info.label}</div> : null}
        <div style={{position: 'absolute', left: st.pad, top: st.pad + 40, width: A.w - st.pad * 2, fontFamily: st.titleFont, fontWeight: st.titleWeight,
          fontSize: size, lineHeight: 1.42, color: st.ink, clipPath: `inset(-10% ${appear(f, t0 - 1, 5)}% -10% 0)`}}>
          <Marked t={text} hl={info.hl} at={info.hlAt ?? t0 + 12} f={f} st={st} />
        </div>
        <Source st={st} text={info.source} x={st.pad} y={ch - st.pad - 24} w={A.w - st.pad * 2} f={f} at={t0 + 10} />
      </div>
    );
  }

  if (info.kind === 'compare') {
    const items: any[] = info.items || [];
    const n = Math.max(items.length, 1);
    const titleH = info.title ? 84 : 0;
    const cw = (A.w - st.gap * (n - 1)) / n, ch = A.h - titleH - 46;
    if (info.title) kids.push(
      <div key="t" style={{position: 'absolute', left: A.x, top: A.y, width: A.w, fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(info.title, A.w, 56, 40),
        color: st.ink, whiteSpace: 'nowrap', clipPath: `inset(-10% ${appear(f, t0, 6)}% -10% 0)`}}>{info.title}</div>);
    items.forEach((it, i) => {
      const at = it.revealAt ?? t0 + i * 10;
      const win = info.win === i || it.win;
      const x = A.x + i * (cw + st.gap), y = A.y + titleH;
      const nsz = fitSize(String(it.value), cw - st.pad * 2, 170, 80);
      kids.push(
        <div key={'c' + i} style={{position: 'absolute', left: x, top: y + (S ? i * 18 : 0), width: cw, height: ch, clipPath: cardIn(at - 4)}}>
          {S ? <S x={0} y={0} w={cw} h={ch} seed={i + 3} on={win} /> : null}
          <div style={{position: 'absolute', left: st.pad, top: st.pad, fontFamily: body, fontWeight: 600, fontSize: 30, letterSpacing: '0.18em', color: win ? st.accent : st.mute}}>{it.label}</div>
          <div style={{position: 'absolute', left: st.pad - 4, top: st.pad + 58, fontFamily: st.numFont, fontWeight: st.numWeight, fontSize: nsz, lineHeight: 1, whiteSpace: 'nowrap',
            letterSpacing: '-0.02em', color: win ? st.accent : st.ink, clipPath: `inset(-10% ${appear(f, at, 5)}% -10% 0)`}}>{it.value}</div>
          {it.unit ? <div style={{position: 'absolute', left: st.pad, top: st.pad + 70 + nsz, fontFamily: body, fontWeight: 600, fontSize: 32, color: st.ink,
            clipPath: `inset(0 ${appear(f, at + 2, 5)}% 0 0)`}}>{it.unit}</div> : null}
          {it.note ? <div style={{position: 'absolute', left: st.pad, bottom: st.pad, width: cw - st.pad * 2, fontFamily: body, fontWeight: 400, fontSize: 26, lineHeight: 1.4,
            color: st.mute, clipPath: `inset(0 ${appear(f, at + 4, 6)}% 0 0)`}}>{it.note}</div> : null}
          {win && st.Circle ? <st.Circle x={st.pad - 30} y={st.pad + 40} w={Math.min(cw - st.pad, emW(String(it.value)) * nsz * 0.62 + 60)} h={nsz + 40}
            p={prog(f - at, 8, 22)} /> : null}
          {win && st.mark === 'underline' ? <div style={{position: 'absolute', left: st.pad, top: st.pad + 64 + nsz, width: 120, height: 6, background: st.accent,
            transform: `scaleX(${prog(f - at, 6, 14)})`, transformOrigin: '0% 50%'}} /> : null}
        </div>
      );
    });
    kids.push(<Source key="s" st={st} text={info.source} x={A.x} y={A.y + A.h - 30} w={A.w} f={f} at={t0 + 14} />);
  }

  if (info.kind === 'list' || info.kind === 'timeline') {
    const items: any[] = info.items || [];
    const titleH = info.title ? 100 : 0;
    const rowH = Math.min(240, (A.h - titleH - 40) / Math.max(items.length, 1));
    const tMax = Math.round(Math.min(66, rowH * 0.32)), dSz = Math.round(Math.min(34, Math.max(26, rowH * 0.15)));
    const oy = Math.max(0, (A.h - titleH - rowH * items.length) / 2);   // 整组竖向居中
    const ats = items.map((it, i) => it.revealAt ?? t0 + i * 12);   // 没写锚点的第一条在切点就在（不露空卡）
    const active = ats.reduce((a, at, i) => (f >= at ? i : a), -1);
    if (info.title) kids.push(
      <div key="t" style={{position: 'absolute', left: A.x, top: A.y + oy, width: A.w, fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(info.title, A.w, 60, 40),
        color: st.ink, whiteSpace: 'nowrap', clipPath: `inset(-10% ${appear(f, t0, 6)}% -10% 0)`}}>{info.title}</div>);
    const tl = info.kind === 'timeline';
    if (tl) {
      const y0 = A.y + oy + titleH + 30, y1 = y0 + rowH * (items.length - 1);
      const cur = active < 0 ? y0 : y0 + rowH * active;
      kids.push(<div key="ln0" style={{position: 'absolute', left: A.x + 22, top: y0, width: 3, height: y1 - y0, background: st.mute, opacity: 0.3}} />);
      kids.push(<div key="ln1" style={{position: 'absolute', left: A.x + 22, top: y0, width: 3, height: Math.max(cur - y0, 0), background: st.accent}} />);
    }
    items.forEach((it, i) => {
      const at = ats[i];
      if (f < at - 2) return;
      const on = i === active;
      const y = A.y + oy + titleH + i * rowH;
      const dim = on ? 1 : 0.42;
      const tx = tl ? A.x + 72 : A.x + st.pad + Math.round(tMax * 1.5);
      kids.push(
        <div key={'r' + i} style={{position: 'absolute', left: A.x, top: y, width: A.w, height: rowH - 16, clipPath: cardIn(at - 2)}}>
          {S && !tl ? <S x={(i % 2) * 18} y={0} w={A.w - 36} h={rowH - 24} seed={i + 7} on={on} /> : null}
          {tl
            ? <div style={{position: 'absolute', left: 10, top: 18, width: 27, height: 27, borderRadius: 27, background: on ? st.accent : st.card,
                border: `3px solid ${on ? st.accent : st.mute}`, boxSizing: 'border-box'}} />
            : <div style={{position: 'absolute', left: st.pad - 6 + (i % 2) * 18, top: 10, fontFamily: st.numFont, fontWeight: st.numWeight, fontSize: Math.round(tMax * 1.5), lineHeight: 1,
                color: st.accent, opacity: on ? 1 : 0.5}}>{it.n ?? String(i + 1)}</div>}
          <div style={{position: 'absolute', left: tx - A.x + (tl ? 0 : (i % 2) * 18), top: tl ? 6 : 22, opacity: dim}}>
            {tl && it.when ? <div style={{fontFamily: st.numFont, fontWeight: st.numWeight, fontSize: dSz + 4, color: on ? st.accent : st.mute, whiteSpace: 'nowrap'}}>{it.when}</div> : null}
            <div style={{marginTop: tl ? 4 : 0, fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(it.t || it.what || '', A.w - (tx - A.x) - 40, tMax, 38),
              lineHeight: 1.2, color: st.ink, whiteSpace: 'nowrap'}}>
              <Marked t={String(it.t || it.what || '')} hl={on && st.mark !== 'circle' ? [0, String(it.t || it.what || '').length] : null} at={at} f={f} st={st} />
            </div>
            {it.d ? <div style={{marginTop: 8, fontFamily: body, fontWeight: 400, fontSize: dSz, color: st.mute, whiteSpace: 'nowrap'}}>{it.d}</div> : null}
          </div>
        </div>
      );
    });
    kids.push(<Source key="s" st={st} text={info.source} x={A.x} y={A.y + A.h - 30} w={A.w} f={f} at={t0 + 14} />);
  }

  if (info.kind === 'chart') {
    const groups: any[] = info.groups || [];
    const series: string[] = info.series || [];
    const vmax = Math.max(...groups.flatMap((g) => g.values || [0]), 1);
    const step = vmax > 50 ? 20 : vmax > 10 ? 5 : 1;
    const top = Math.ceil(vmax / step) * step;
    const titleH = 130;
    const X0 = A.x + 60, Y0 = A.y + A.h - 112, H = A.h - titleH - 170, W = A.w - 70;
    const sc = H / top;
    const gw = W / Math.max(groups.length, 1);
    const bw = Math.min(120, (gw - 60) / Math.max(series.length, 1));
    const cols = [st.accent, st.accent2, st.mute];
    kids.push(
      <div key="t" style={{position: 'absolute', left: A.x, top: A.y, width: A.w, clipPath: `inset(-10% ${appear(f, t0, 6)}% -10% 0)`}}>
        <div style={{fontFamily: st.titleFont, fontWeight: st.titleWeight, fontSize: fitSize(info.title || '', A.w, 52, 38), color: st.ink, whiteSpace: 'nowrap'}}>{info.title}</div>
        <div style={{display: 'flex', gap: 30, marginTop: 14, fontFamily: body, fontSize: 26, color: st.ink}}>
          {series.map((n, i) => <span key={n}><i style={{display: 'inline-block', width: 22, height: 22, background: cols[i], verticalAlign: -3, marginRight: 10}} />{n}</span>)}
        </div>
      </div>
    );
    const svg: React.ReactNode[] = [];
    for (let v = 0; v <= top + 1e-6; v += step) {
      const y = Y0 - v * sc;
      svg.push(<line key={'g' + v} x1={X0} y1={y} x2={X0 + W} y2={y} stroke={v ? st.mute : st.ink} strokeOpacity={v ? 0.25 : 1} strokeWidth={v ? 1.5 : 3} />);
      svg.push(<text key={'v' + v} x={X0 - 14} y={y + 8} textAnchor="end" fontFamily={st.numFont} fontSize={24} fill={st.mute}>{v}</text>);
    }
    groups.forEach((g, gi) => {
      const at = g.revealAt ?? t0 + 8 + gi * 14;
      const gx = X0 + gi * gw + (gw - bw * series.length - 16 * (series.length - 1)) / 2;
      (g.values || []).forEach((val: number, bi: number) => {
        const grow = prog(f - at - bi * 3, 0, 12, ease.out);
        const h = val * sc * grow, x = gx + bi * (bw + 16);
        const col = cols[bi] || st.mute;
        svg.push(<rect key={`b${gi}_${bi}`} x={x} y={Y0 - h} width={bw} height={h} fill={g.pred ? `url(#hatch${bi})` : col} stroke={col} strokeWidth={g.pred ? 3 : 0} />);
        if (grow > 0.98) svg.push(<text key={`l${gi}_${bi}`} x={x + bw / 2} y={Y0 - h - 16} textAnchor="middle" fontFamily={st.numFont} fontWeight={700}
          fontSize={40} fill={bi === 0 ? st.accent : st.ink}>{val}</text>);
      });
      svg.push(<text key={'x' + gi} x={X0 + gi * gw + gw / 2} y={Y0 + 44} textAnchor="middle" fontFamily={body} fontSize={28} fill={st.ink}
        opacity={f >= at ? 1 : 0}>{g.label}</text>);
    });
    kids.push(
      <svg key="c" width={2000} height={2000} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
        <defs>
          {cols.map((c, i) => (
            <pattern key={i} id={'hatch' + i} width={12} height={12} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width={12} height={12} fill={st.card} /><line x1={0} y1={0} x2={0} y2={12} stroke={c} strokeWidth={5} />
            </pattern>
          ))}
        </defs>
        {svg}
      </svg>
    );
    kids.push(<Source key="s" st={st} text={info.source} x={A.x} y={A.y + A.h - 30} w={A.w} f={f} at={t0 + 14} />);
  }

  const Bg = st.WindowBg;
  const card = big && info.kind !== 'quote' && st.Surface ? (
    <div style={{position: 'absolute', left: A.x - st.pad, top: A.y - st.pad, width: A.w + st.pad * 2, height: A.h + st.pad * 2, clipPath: cardIn(s.from)}}>
      {React.createElement(st.Surface, {x: 0, y: 0, w: A.w + st.pad * 2, h: A.h + st.pad * 2, seed: 0, on: true})}
    </div>
  ) : null;
  return (
    <>
      {st.presenter.mode !== 'blur' && Bg ? <Bg /> : null}
      {card}
      {kids}
      <PresenterBox st={st} face={face} src={src} f={f} from={s.from} />
    </>
  );
};
