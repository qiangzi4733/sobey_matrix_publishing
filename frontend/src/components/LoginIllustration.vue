<template>
  <!-- 登录页左侧插图：底座上立着文件夹、翻出的文档和印着 AI 的卷页。拿到设计原图后可以直接换成图片 -->
  <svg viewBox="0 0 640 560" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="li-top" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#ffffff" />
        <stop offset="1" stop-color="#e4ecfb" />
      </linearGradient>
      <linearGradient id="li-side-l" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#dfe8fa" />
        <stop offset="1" stop-color="#c9d7f3" />
      </linearGradient>
      <linearGradient id="li-side-r" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#eef3fd" />
        <stop offset="1" stop-color="#d6e1f7" />
      </linearGradient>
      <linearGradient id="li-folder" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#7fb0ff" />
        <stop offset="0.55" stop-color="#3f86f7" />
        <stop offset="1" stop-color="#2d6be8" />
      </linearGradient>
      <linearGradient id="li-folder-glass" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#b8d4ff" stop-opacity="0.9" />
        <stop offset="1" stop-color="#5b97fb" stop-opacity="0.75" />
      </linearGradient>
      <linearGradient id="li-paper" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#ffffff" />
        <stop offset="1" stop-color="#e6edfb" />
      </linearGradient>
      <linearGradient id="li-wave" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#d9e8ff" />
        <stop offset="0.5" stop-color="#8dbaff" />
        <stop offset="1" stop-color="#4a8df8" />
      </linearGradient>
      <linearGradient id="li-ai" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#5aa0ff" />
        <stop offset="1" stop-color="#2f6fe6" />
      </linearGradient>
      <radialGradient id="li-glow" cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stop-color="#6aa2ff" stop-opacity="0.45" />
        <stop offset="1" stop-color="#6aa2ff" stop-opacity="0" />
      </radialGradient>
      <filter id="li-shadow" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur in="SourceAlpha" stdDeviation="14" />
        <feOffset dy="18" />
        <feComponentTransfer><feFuncA type="linear" slope="0.18" /></feComponentTransfer>
        <feFlood flood-color="#3c64b4" />
        <feComposite operator="in" in2="SourceAlpha" />
        <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>

    <!-- 底座下的蓝色光晕 -->
    <ellipse cx="330" cy="440" rx="250" ry="110" fill="url(#li-glow)" />

    <!-- 浮在左上方的信封方块 -->
    <g filter="url(#li-shadow)" transform="translate(-90 -20)">
      <path d="M150 92 L262 40 Q276 34 290 41 L352 74 Q364 81 352 88 L240 140 Q226 146 212 139 L150 106 Q138 99 150 92 Z" fill="url(#li-top)" />
      <path d="M138 99 L138 112 Q138 120 150 126 L212 159 Q226 166 240 160 L352 108 Q364 101 364 94 L364 81 Q364 88 352 94 L240 146 Q226 152 212 145 L150 112 Q138 106 138 99 Z" fill="url(#li-side-l)" />
      <path d="M204 82 L250 104 L300 58" fill="none" stroke="#c7d5f2" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
    </g>

    <!-- 两层底座 -->
    <g filter="url(#li-shadow)">
      <path d="M70 410 L70 440 Q70 452 84 460 L300 562 Q318 570 336 562 L566 452 Q580 445 580 434 L580 404 Z" fill="url(#li-side-l)" />
      <path d="M84 396 L300 296 Q318 288 336 296 L566 400 Q584 410 566 420 L336 528 Q318 536 300 528 L84 426 Q66 416 84 396 Z" fill="url(#li-top)" />
      <path d="M140 388 L140 404 Q140 412 152 418 L302 488 Q318 495 334 488 L494 414 Q506 408 506 400 L506 384 Z" fill="url(#li-side-r)" />
      <path d="M152 378 L302 308 Q318 301 334 308 L494 382 Q510 390 494 398 L334 472 Q318 479 302 472 L152 402 Q136 393 152 378 Z" fill="url(#li-top)" />
    </g>

    <!-- 文件夹背板 -->
    <g transform="translate(186 92)">
      <path d="M8 40 Q8 26 22 22 L182 -20 Q196 -24 196 -10 L196 196 L60 320 Q38 336 26 318 L8 290 Z" fill="url(#li-folder)" />
      <path d="M30 34 L74 22" stroke="#ffffff" stroke-opacity="0.75" stroke-width="10" stroke-linecap="round" />
      <path d="M8 40 L8 290 Q16 300 26 318 L34 300 L34 60 Z" fill="#2558cf" opacity="0.5" />
    </g>

    <!-- 翻出的三页文档，像浏览器窗口 -->
    <g transform="translate(222 150)">
      <path d="M20 40 Q20 28 32 24 L200 -26 Q212 -30 212 -18 L212 130 L50 260 Q30 270 26 252 L20 230 Z" fill="url(#li-folder-glass)" />
      <path d="M36 52 Q36 40 48 36 L212 -12 Q224 -16 224 -4 L224 140 L66 266 Q46 278 42 258 L36 236 Z" fill="url(#li-paper)" />
      <circle cx="60" cy="46" r="5" fill="#ff8aa0" />
      <circle cx="76" cy="41" r="5" fill="#ffffff" stroke="#d6e0f4" />
      <circle cx="92" cy="36" r="5" fill="#7fd0ff" />
      <path d="M52 92 Q52 80 64 76 L226 30 Q238 26 238 38 L238 160 L84 280 Q62 292 58 272 L52 250 Z" fill="url(#li-paper)" opacity="0.96" />
      <path d="M78 110 L214 70 M78 130 L190 97" stroke="#4f8cf5" stroke-width="5" stroke-linecap="round" opacity="0.55" />
    </g>

    <!-- 卷出来的 AI 页 -->
    <g filter="url(#li-shadow)">
      <path
        d="M248 376 Q258 336 300 334 Q350 334 372 320 L548 236 Q590 222 604 262 L640 360 Q648 388 620 398 L438 470 Q400 482 382 458 Q352 418 320 430 Q284 444 264 418 Z"
        fill="url(#li-wave)"
        opacity="0.95"
      />
      <path d="M300 334 Q350 334 372 320 L548 236 Q568 230 582 240 L410 322 Q378 338 330 344 Z" fill="#ffffff" opacity="0.55" />
      <text
        x="0"
        y="0"
        transform="translate(470 418) rotate(-24) skewX(-12)"
        font-size="96"
        font-weight="800"
        font-family="Arial, Helvetica, sans-serif"
        fill="url(#li-ai)"
        stroke="#ffffff"
        stroke-opacity="0.45"
        stroke-width="2"
      >AI</text>
    </g>
  </svg>
</template>
