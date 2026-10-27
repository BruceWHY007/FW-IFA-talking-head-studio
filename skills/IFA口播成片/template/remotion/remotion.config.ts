import {Config} from '@remotion/cli/config';
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
// 走 Metal（angle）而不是软件渲染；并发 4。不设会风扇狂转、慢一倍（父 skill references/04 §十）。
Config.setChromiumOpenGlRenderer('angle');
Config.setConcurrency(4);
Config.setOffthreadVideoCacheSizeInBytes(512 * 1024 * 1024); // 2GB 时长片中后段会把标签页挤崩（Request closed）
