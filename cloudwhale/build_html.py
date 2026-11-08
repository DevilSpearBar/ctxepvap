"""Pack the finished film into ONE self-contained HTML file (no external requests).

    .venv/bin/python build_html.py [video.mp4] [poster.jpg] [out.html]
"""

import base64
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, 'build')

PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Облачный кит</title>
<style>
  html, body {{ margin: 0; height: 100%; background: #0b0d14; }}
  body {{ display: flex; align-items: center; justify-content: center; overflow: hidden; }}
  .frame {{ position: relative; width: min(100vw, calc(100vh * 1920 / 804)); aspect-ratio: 1920 / 804;
           background: #000 center / cover no-repeat; box-shadow: 0 0 80px rgba(0, 0, 0, .6); }}
  video {{ position: absolute; inset: 0; width: 100%; height: 100%; display: block; background: transparent; }}
  .play {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
          cursor: pointer; transition: opacity .4s; background: radial-gradient(circle, rgba(0,0,0,.05), rgba(0,0,0,.35)); }}
  .play svg {{ width: 9%; min-width: 56px; filter: drop-shadow(0 4px 14px rgba(0,0,0,.45)); }}
  .play.hidden {{ opacity: 0; pointer-events: none; }}
  .play.loading svg {{ animation: pulse 1.2s ease-in-out infinite; }}
  @keyframes pulse {{ 50% {{ opacity: .45; }} }}
</style>
</head>
<body>
<div class="frame" id="frame" style="background-image:url(data:image/jpeg;base64,{poster})">
  <video id="v" playsinline preload="auto"></video>
  <div class="play loading" id="play" aria-label="play" role="button">
    <svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="rgba(255,250,240,.92)"/>
      <path d="M40 30 L72 50 L40 70 Z" fill="#c8463a"/></svg>
  </div>
</div>
<script id="film" type="application/octet-stream">{video}</script>
<script>
(function () {{
  var v = document.getElementById('v'), play = document.getElementById('play');
  var b64 = document.getElementById('film').textContent.replace(/\\s+/g, '');
  // Decode in chunks: one huge atob() is slow and memory-hungry on some browsers.
  var chunk = 1 << 22, parts = [];
  for (var i = 0; i < b64.length; i += chunk) {{
    var s = atob(b64.slice(i, i + chunk)), u = new Uint8Array(s.length);
    for (var j = 0; j < s.length; j++) u[j] = s.charCodeAt(j);
    parts.push(u);
  }}
  v.src = URL.createObjectURL(new Blob(parts, {{type: 'video/mp4'}}));
  v.addEventListener('canplay', function () {{ play.classList.remove('loading'); }}, {{once: true}});
  function toggle() {{
    if (v.paused) {{ v.play(); play.classList.add('hidden'); v.controls = true; }}
    else {{ v.pause(); }}
  }}
  play.addEventListener('click', toggle);
  v.addEventListener('ended', function () {{ play.classList.remove('hidden'); v.controls = false; v.currentTime = 0; }});
  document.addEventListener('keydown', function (e) {{
    if (e.code === 'Space') {{ e.preventDefault(); toggle(); }}
    if (e.key === 'f' && document.getElementById('frame').requestFullscreen) document.getElementById('frame').requestFullscreen();
  }});
}})();
</script>
</body>
</html>
"""


def main():
    video = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BUILD, 'cloudwhale.mp4')
    poster = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BUILD, 'poster.jpg')
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(BUILD, 'cloudwhale.html')
    with open(video, 'rb') as f:
        vb = base64.b64encode(f.read()).decode('ascii')
    with open(poster, 'rb') as f:
        pb = base64.b64encode(f.read()).decode('ascii')
    # wrap the payload so the file stays editor-friendly
    vb = '\n'.join(vb[i:i + 4096] for i in range(0, len(vb), 4096))
    html = PAGE.format(video=vb, poster=pb)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'{out}: {os.path.getsize(out) / 1e6:.1f} MB (video {os.path.getsize(video) / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
