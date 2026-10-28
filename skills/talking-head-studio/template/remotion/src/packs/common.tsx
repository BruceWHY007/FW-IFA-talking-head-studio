import React from 'react';
import {interpolate} from 'remotion';
import {ease} from '../theme';

export const clamp = {extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const};

export type Line = {text: string; from: number; hl: [number, number][]};
export type Cap = {from: number; to: number; variant: string; lines: Line[]; cont?: boolean; animate?: boolean; top?: number};
export type Shot = {
  id: string; type: string; from: number; to: number; clip?: string; fit?: string; band?: {y: number; h: number};
  image?: string; iw?: number; ih?: number; credit?: string; tag?: string; figure?: any; bg?: string; push?: number; need?: string;
};
export type Rect = {x: number; y: number; w: number; h: number};

// 关键词着色：只换颜色和字重，不换字号（同一行里字号跳会抖基线）——kinetic 包自己另做放大
export const Spans: React.FC<{t: string; hl: [number, number][]; hlStyle: React.CSSProperties}> = ({t, hl, hlStyle}) => {
  const out: React.ReactNode[] = [];
  let i = 0;
  [...hl].sort((a, b) => a[0] - b[0]).forEach(([a, b], k) => {
    if (a < i) return;
    if (a > i) out.push(<span key={'n' + k}>{t.slice(i, a)}</span>);
    out.push(<span key={'h' + k} style={hlStyle}>{t.slice(a, b)}</span>);
    i = b;
  });
  if (i < t.length) out.push(<span key="tail">{t.slice(i)}</span>);
  return <>{out}</>;
};

// 遮罩揭开：文字层零 transform，只动 clip-path
export const wipe = (local: number, at: number, dur: number) =>
  interpolate(local, [at, at + dur], [100, 0], {...clamp, easing: ease.out});

export const prog = (local: number, a: number, b: number, e = ease.out) => interpolate(local, [a, b], [0, 1], {...clamp, easing: e});

// 画面窗里人脸定位：原片 1080×1920，把人脸中心放到窗内 faceY 处；k 是缩放；保证视频盖满窗
export const faceFit = (win: Rect, face: {cx: number; cy: number}, k: number, faceY: number | null) => {
  const fx = face.cx * 1080 * k, fy = face.cy * 1920 * k;
  const W = 1080 * k, H = 1920 * k;
  let left = win.w / 2 - fx;
  let top = faceY == null ? win.h * face.cy - fy : win.h * faceY - fy;
  left = Math.min(0, Math.max(win.w - W, left));
  top = Math.min(0, Math.max(win.h - H, top));
  return {left, top, width: W, height: H};
};
