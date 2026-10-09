import {Config} from '@remotion/cli/config';

// Качество: кадры без потерь (PNG), сжатие с запасом — Instagram всё равно пережмёт ещё раз
Config.setVideoImageFormat('png');
Config.setCrf(12);
Config.setX264Preset('slow');
Config.setPixelFormat('yuv420p');   // стандартная цветовая шкала (не «полный диапазон»)
Config.setColorSpace('bt709');
Config.setChromiumOpenGlRenderer('swangle'); // 3D без видеокарты
Config.setConcurrency(4);
