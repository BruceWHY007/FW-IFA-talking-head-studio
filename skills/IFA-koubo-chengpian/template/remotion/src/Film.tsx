import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import tlRaw from './timeline.json';
import {loadFonts} from './fonts';
import {ease} from './theme';
import {Cap, Shot, clamp, faceFit} from './packs/common';
import {editorial} from './packs/editorial';
import {glassPack} from './packs/glass';
import {kinetic} from './packs/kinetic';
import {evidence} from './packs/evidence';
import {diagram} from './packs/diagram';
import {brand} from './packs/brand';

// 一切时间都来自 timeline.json（build.py 生成，单一真源）。这里只负责「在第 f 帧画什么」；长什么样由风格包决定。
const tl: any = tlRaw;
loadFonts();
const PACKS: Record<string, any> = {editorial, glass: glassPack, kinetic, evidence, diagram, brand};
const pack = PACKS[tl.style || 'editorial'] || editorial;
const WIN = pack.win;

const shotAt = (f: number): Shot | null => (tl.shots as Shot[]).find((s) => f >= s.from && f < s.to) || null;

// 第 f 帧人脸层的缩放（跳切景别 × 呼吸，重话推近取大者）。落版要从最后一帧的缩放接着推，所以单独抽出来
const kAt = (f: number) => {
  const base = (tl.aroll.frame && tl.aroll.frame.scale) || 1;
  const z = (tl.arollZoom as any[]).find((r) => f >= r.from && f < r.to);
  // 呼吸：分带包 3%；满幅包 5%（满幅画面里人只占一小块，3% 在她停顿时读作静止——第 6 轮样片 C）
  const breathe = z ? 1 + (pack.breathe ?? 0.03) * interpolate(f, [z.from, z.to], [0, 1], {...clamp, easing: ease.inOut}) : 1;
  const em = (tl.emph || []).find((r: any) => f >= r.from && f < r.to);
  const push = em ? interpolate(f, [em.from, em.from + 15], [z ? z.scale : 1, em.scale], {...clamp, easing: ease.inOut}) : 0;
  return base * Math.max(z ? z.scale : 1, push) * breathe;
};

// 人脸层：整条剪后 A-roll 连续播放，按人脸中心放进画面窗；跳切处换景别；封面帧推近后 12 帧推回；卡片镜时虚化压暗做底
const ARoll: React.FC = () => {
  const f = useCurrentFrame();
  const s = shotAt(f);
  const face = tl.aroll.face || {cx: 0.5, cy: 0.42};
  // 落版：停在她的最后一帧，压暗 28%、缓推 4%（静帧但在动；冻结检查对这一段豁免）
  if (tl.outro && f >= tl.outro.from) {
    // 从最后一帧的缩放接着推 1%（第 4 轮评审：先退 2.9% 再推、推 4% 切到头顶；第 5 轮：推 2% 发顶仍碰窗沿）
    const p = interpolate(f, [tl.outro.from, tl.outro.from + tl.outro.frames], [0, 1], {...clamp, easing: ease.inOut});
    const ro = faceFit(WIN, face, kAt(tl.outro.from - 1) * (1 + 0.01 * p), pack.faceY);
    return (
      <AbsoluteFill style={{overflow: 'hidden'}}>
        <Img src={staticFile('outro.jpg')} style={{position: 'absolute', left: ro.left, top: ro.top, width: ro.width, height: ro.height, maxWidth: 'none',
          filter: `brightness(${1 - 0.28 * Math.min(p * 3, 1)}) saturate(0.95)`}} />
      </AbsoluteFill>
    );
  }
  const base = (tl.aroll.frame && tl.aroll.frame.scale) || 1;
  let k = kAt(f);
  const cv = tl.cover;
  if (cv && f < cv.frames + cv.trans) {
    k = base * interpolate(f, [cv.frames, cv.frames + cv.trans], [cv.scale || 1.12, 1], {...clamp, easing: ease.inOut});
  }
  // 卡片镜的底：大字卡、照片卡，以及「讲解人留在原位虚化」的信息卡（A／B／C）
  const under = s && (s.type === 'P' || (s.type === 'G' && !s.bg) || (s.type === 'I' && (!pack.info || pack.info.presenter.mode === 'blur')));
  // 卡片底：大字卡匀速推 1.06→1.22；信息卡按恒定速度推（每帧 0.25%，长卡不会越推越慢），实底卡面后的她只虚化 3px，动作透得出来
  // （第 5 轮 qa：推得太慢＋压得太暗，数字落定后画面窗就是死的；第 6 轮样片：5.4 秒的时间线卡后面几乎不动）
  const infoUnder = !!s && s.type === 'I';
  if (under) k = infoUnder ? base * (1.06 + 0.0025 * Math.max(f - s!.from, 0)) : base * interpolate(f, [s!.from, s!.to], [1.06, 1.22], clamp);
  const underBlur = infoUnder ? (pack.info && pack.info.areaCard && pack.info.areaCard.length ? 3 : 5) : 6;
  // 「手机里的她」：背景是她本人虚化压暗（满窗在动），手机里是清晰的她；手机与背景一起缓推
  if (s && s.type === 'PH' && pack.phone) {
    const ph = pack.phone;
    const p = 1;
    const kk = pack.phonePush ? pack.phonePush(f, s) : 1;
    const bg = faceFit(WIN, face, 1.25 * kk, pack.faceY);
    const rr = faceFit({x: 0, y: 0, w: ph.w, h: ph.h}, face, ph.k || 0.92, ph.faceY ?? 0.4);  // 放大到桌面杂物出框
    return (
      <AbsoluteFill style={{overflow: 'hidden', background: '#0D1216'}}>
        <OffthreadVideo src={staticFile(tl.aroll.src)} muted style={{position: 'absolute', left: bg.left, top: bg.top, width: bg.width, height: bg.height,
          maxWidth: 'none', filter: 'blur(18px) brightness(0.45) saturate(0.8)'}} />
        <div style={{position: 'absolute', left: ph.x, top: ph.y, width: ph.w, height: ph.h, borderRadius: ph.r, overflow: 'hidden',
          transform: `scale(${kk * (0.96 + 0.04 * p)})`, transformOrigin: `${(ph.x + ph.w / 2) / WIN.w * 100}% 50%`, opacity: p}}>
          <OffthreadVideo src={staticFile(tl.aroll.src)} muted style={{position: 'absolute', left: rr.left, top: rr.top, width: rr.width, height: rr.height, maxWidth: 'none'}} />
        </div>
      </AbsoluteFill>
    );
  }
  // 封面占了画面窗上部的包（K2）：封面期间人脸放低，封面收起时随推回一起回到正常位置
  const fyNow = cv && pack.coverFaceY != null && f < cv.frames + cv.trans
    ? interpolate(f, [cv.frames, cv.frames + cv.trans], [pack.coverFaceY, pack.faceY], {...clamp, easing: ease.inOut}) : pack.faceY;
  const r = faceFit(WIN, face, k, fyNow);
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <OffthreadVideo src={staticFile(tl.aroll.src)} muted
        style={{position: 'absolute', left: r.left, top: r.top, width: r.width, height: r.height, maxWidth: 'none',
          filter: under ? `blur(${underBlur}px) brightness(0.5) saturate(0.85)` : 'saturate(0.97) contrast(1.03)'}} />
    </AbsoluteFill>
  );
};

// B-roll：统一调色已烘进素材（按画面窗尺寸归一化）；这里加缓推（方向交替）和静态网点
// 运镜按画面选：push 推近／pull 拉远／pan-l、pan-r 横移（天际线、街景）／hold 只呼吸
const camera = (move: string, p: number) => {
  if (move === 'pan-l') return `scale(1.08) translateX(${(0.5 - p) * 5}%)`;
  if (move === 'pan-r') return `scale(1.08) translateX(${(p - 0.5) * 5}%)`;
  if (move === 'pull') return `scale(${1.07 - 0.07 * p})`;
  if (move === 'hold') return `scale(${1.02 + 0.015 * p})`;
  return `scale(${1 + 0.07 * p})`;
};
const BRoll: React.FC<{s: Shot}> = ({s}) => {
  const f = useCurrentFrame();
  const dur = s.to - s.from;
  const p = interpolate(f, [0, dur], [0, 1], {extrapolateRight: 'clamp', easing: ease.inOut});
  const move = (s as any).move || ((s.push || 1) > 0 ? 'push' : 'pull');
  // 大字卡的底一律虚化压暗：素材里若有 AI 乱码字也读不出来（10-22 评审第 2 轮：投影幕上「复复星」）
  const dim = s.type === 'G' ? 'blur(9px) brightness(0.42) saturate(0.85)' : 'none';
  // 章节第一镜：画面从下沿（接缝金线）升起，9 帧
  // 章节第一镜：新画面在切点那一帧已盖住画面窗 40%，8 帧升满；底下垫着上一镜（不露纸、不闪白，10-22 评审第 2 轮）
  const rise = (s as any).enter === 'rise' ? interpolate(f, [0, 10], [55, 0], {...clamp, easing: ease.inOut}) : 0;  // 10 帧 S 曲线：读作「升起」，不是「撕一下」
  const sp = (s as any).split;
  // 分屏：说到那个词，左镜收到左半边、右镜从右边推开进来（视频层上的变换，不碰文字）
  const sw = sp ? interpolate(f, [sp.at - s.from, sp.at - s.from + 10], [0, 1], {...clamp, easing: ease.inOut}) : 0;
  return (
    <>
    <AbsoluteFill style={{overflow: 'hidden', background: '#0D1216', clipPath: `inset(${rise}% 0 0 0)`}}>
      {(s as any).img ? (
        <AbsoluteFill>
          <Img src={staticFile((s as any).img)} style={{width: '100%', height: '100%', objectFit: 'cover',
            transform: camera(move, p), filter: `${dim === 'none' ? '' : dim + ' '}saturate(0.94) contrast(1.04) brightness(0.98)`}} />
        </AbsoluteFill>
      ) : s.clip ? (
        <AbsoluteFill style={{clipPath: `inset(0 ${sw * 50}% 0 0)`}}>
          <OffthreadVideo src={staticFile(s.clip)} muted style={{width: '100%', height: '100%', objectFit: 'cover',
            transform: `translateX(${-sw * 50 * (sp && sp.lx != null ? sp.lx : 0.5)}%) ${camera(move, p)}`, filter: dim}} />
        </AbsoluteFill>
      ) : <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#D8A863',
          fontSize: 40, fontFamily: 'serif'}}>{s.id} · {s.need || '待补素材'}</div>}
      {sp && sw > 0 ? (
        <div style={{position: 'absolute', top: 0, bottom: 0, left: '50%', width: '50%', overflow: 'hidden', clipPath: `inset(0 0 0 ${(1 - sw) * 100}%)`}}>
          <Sequence from={sp.at - s.from}>
            <OffthreadVideo src={staticFile(sp.clip)} muted style={{width: '100%', height: '100%', objectFit: 'cover', transform: camera('push', p)}} />
          </Sequence>
        </div>
      ) : null}
      {/* 分割线就是右半画面的左边缘，和它一起滑到正中（第 5 轮评审：线在中间自己长、画面从右边推，各走各的） */}
      {sp && sw > 0 ? <div style={{position: 'absolute', top: 0, bottom: 0, left: `calc(${50 + (1 - sw) * 50}% - 3px)`, width: 6, background: pack.seam || '#F3EDE3'}} /> : null}
      <AbsoluteFill style={{backgroundImage: 'radial-gradient(rgba(13,18,22,0.9) 0.9px, transparent 1.5px)', backgroundSize: '5px 5px',
        mixBlendMode: 'soft-light', opacity: pack.halftone}} />
    </AbsoluteFill>
    </>
  );
};

export const Film: React.FC = () => {
  const f = useCurrentFrame();
  const s = shotAt(f);
  const inCover = tl.cover && f < tl.cover.frames + tl.cover.trans;
  const onB = !!s && (['B', 'S'].includes(s.type) || (s.type === 'G' && !!s.bg));
  const showMast = tl.masthead && (pack.mastheadOnB !== false || !onB) && !(inCover && pack.name !== 'editorial');
  const caps = (tl.captions as Cap[]).filter((c) => f >= c.from && f < c.to);
  const P = pack;
  return (
    <AbsoluteFill style={{background: P.canvas}}>
      {P.Under ? <P.Under /> : null}
      <div style={{position: 'absolute', left: WIN.x, top: WIN.y, width: WIN.w, height: WIN.h, overflow: 'hidden', borderRadius: P.winRadius || 0,
        clipPath: P.winClip || undefined}}>
        <ARoll />
        {(tl.shots as Shot[]).filter((x) => x.type === 'B' || x.type === 'S' || (x.type === 'G' && x.bg)).map((x) => (
          <Sequence key={x.id} from={x.from} durationInFrames={x.to - x.from}>
            <BRoll s={x.type === 'G' ? {...x, clip: x.bg} : x} />
          </Sequence>
        ))}
        {s && s.type === 'G' && s.figure ? <P.Figure f={f} s={s} /> : null}
        {s && s.type === 'P' ? <P.Photo f={f} s={s} /> : null}
        {s && s.type === 'I' && P.Info ? <P.Info f={f} s={s} face={tl.aroll.face || {cx: 0.5, cy: 0.42}} src={tl.aroll.src} /> : null}
      </div>
      {P.Over ? <P.Over /> : null}
      {showMast ? <P.Masthead f={f} series={tl.masthead.series} episode={tl.masthead.episode} end={tl.end} chapters={tl.chapters}
        coverEnd={tl.cover && tl.coverInWindow ? tl.cover.frames : 0} /> : null}
      {s && (s as any).split && P.SplitLabels && f >= (s as any).split.at ? <P.SplitLabels f={f} at={(s as any).split.at} labels={(s as any).split.labels || []} /> : null}
      {s && (s as any).label && P.Label ? <P.Label f={f} from={s.from} text={(s as any).label} /> : null}
      {s && s.type === 'PH' && P.PhoneFrame ? <P.PhoneFrame f={f} s={s} /> : null}
      {(tl.tags || []).filter((t: any) => f >= t.from && f < t.to).map((t: any) => <P.Tag key={t.from} f={f} t={t} />)}
      {tl.nametag ? <P.NameTag f={f} d={tl.nametag} /> : null}
      {tl.end && P.EndCard ? <P.EndCard f={f} d={tl.end} /> : null}
      {caps.map((c, i) => <P.Caption key={c.from + '_' + i} cap={c} f={f} />)}
      {tl.outro && tl.outro.cta && f >= tl.outro.from ? <P.Caption f={f} cap={{from: tl.outro.from, to: tl.durationInFrames, variant: 'a', animate: true,
        lines: [{text: tl.outro.cta, from: tl.outro.from, hl: [[0, String(tl.outro.cta).length]], hlAt: [tl.outro.from]} as any]}} /> : null}
      {tl.cover ? <P.Cover f={f} d={tl.cover} /> : null}
      <AbsoluteFill style={{backgroundImage: `url(${staticFile('grain.png')})`, mixBlendMode: 'overlay', opacity: 0.06, pointerEvents: 'none'}} />
    </AbsoluteFill>
  );
};
