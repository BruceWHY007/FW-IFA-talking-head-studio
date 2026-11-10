import {Config} from '@remotion/cli/config';
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
// 走显卡（angle：macOS＝Metal，Windows＝D3D11）而不是软件渲染，不设会风扇狂转、慢一倍；没有显卡的 Linux 用 swangle。
// 可用环境变量 IFA_GL 改（angle／angle-egl／swangle／egl）。并发由 render.py 按这台机器的核数和内存传进来。
Config.setChromiumOpenGlRenderer(((process.env.IFA_GL as any) || (process.platform === 'linux' ? 'swangle' : 'angle')));
Config.setConcurrency(Number(process.env.IFA_RENDER_CONCURRENCY) || 3);
Config.setOffthreadVideoCacheSizeInBytes(512 * 1024 * 1024); // 2GB 时长片中后段会把标签页挤崩（Request closed）
