// 风格包「港金」：6 种颜色以内、两种字族（宋体主张＋Didot 系数字）、一条贯穿全片的金色细线。
// 换风格包＝整份替换这个文件的值，组件不改。所有动效时长写帧（30fps），缓动只用这里的几条。
import {Easing} from 'remotion';
import tlRaw from './timeline.json';
import THEMES from './packs/themes.json';

// 账号主题（build.py 按 decompose.theme／账号登记解析好写进 timeline.theme）；没写就用琥珀金
const _th: any = (tlRaw as any).theme || {};
export const TH: {name: string; paper: string; accent: string; line: string; dark: string; foot: string; custom: boolean} = {
  ...(THEMES as any)['琥珀金'], name: '琥珀金', custom: false, ..._th,
};

export const C = {
  ink: '#0D1216',        // 深底与底板
  paper: '#F5F0E6',      // 主文字（暖白，不用纯白）
  gold: '#D8A863',       // 暗底上的金（强调、细线）
  goldText: '#E8C27F',   // 金色文字（比细线提亮一档，保证 4.5:1）
  goldDeep: '#94673D',   // 浅底上的金
  harbour: '#2E5A5F',    // 维港青（只用于底板色偏，不单独上屏）
};

export const plate = (a = 0.62) => `rgba(13,18,22,${a})`;

export const F = {
  serif: '"SHSerif", "Songti SC", serif',
  sans: '"PingFang SC", "Hiragino Sans GB", sans-serif',
  didot: '"Bodoni Moda", "Didot", serif',
};

// 竖屏安全区：顶部 170 以上是状态栏与频道切换，底部 1520 以下是标题描述与音乐条，右侧 940 以外的中段是点赞评论栏
export const SAFE = {x: 72, top: 170, bottom: 1520, right: 940};

export const ease = {
  out: Easing.bezier(0.16, 1, 0.3, 1),      // 进场：快起慢收，看得清
  in: Easing.bezier(0.7, 0, 0.84, 0),       // 离场：慢起快走
  inOut: Easing.bezier(0.65, 0, 0.35, 1),   // 镜头推拉
};

export const D = {
  plateIn: 6,     // 字幕底板从细线张开
  textIn: 8,      // 文字遮罩揭开
  lineDraw: 10,   // 金线画出
  cardIn: 10,     // 卡片 materialize（模糊＋缩放一起收）
  out: 4,
};
