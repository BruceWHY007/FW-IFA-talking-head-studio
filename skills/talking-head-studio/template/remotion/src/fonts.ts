import {continueRender, delayRender} from 'remotion';
import {FONT_DATA} from './fontdata';

// 字体全部本地固定版本：build.py 把按本片用字切好的宋体子集和 Bodoni Moda 编成 base64 写进 fontdata.ts，
// 渲染时不发任何网络请求。（10-22 实测：用 staticFile 的 url() 加载，长片渲染会有标签页的字体请求永不返回，
// delayRender 挂到超时、整片失败；改成内嵌后消失。）
const faces: [string, string, string][] = [
  ['SHSerif', 'SHSerif-Heavy', '900'],
  ['SHSerif', 'SHSerif-SemiBold', '600'],
  ['Bodoni Moda', 'BodoniModa', '400 900'],
];

const b64 = (s: string) => {
  const bin = atob(s);
  const u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u.buffer;
};

let started = false;
export const loadFonts = () => {
  if (started || typeof document === 'undefined') return;
  started = true;
  const h = delayRender('fonts');
  Promise.all(
    faces.map(([family, key, weight]) => {
      if (!FONT_DATA[key]) return null;
      const f = new FontFace(family, b64(FONT_DATA[key]), {weight});
      return f.load().then((ff) => (document as any).fonts.add(ff)).catch(() => null);
    }),
  ).then(() => continueRender(h));
};
