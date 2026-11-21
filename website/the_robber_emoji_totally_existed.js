(function () {
  const STAR_COUNT = 20;

  function random(min, max) {
    return Math.random() * (max - min) + min;
  }

  function initStars() {
    const container = document.getElementById('bg-stars');
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;
    const placed = [];
    const minSpacing = 80;

    for (let i = 0; i < STAR_COUNT; i++) {
      const starWrapper = document.createElement('div');
      starWrapper.className = 'star';

      const starImg = document.createElement('img');
      starImg.src = 'robber.png';
      starImg.alt = '';
      starImg.draggable = false;
      starWrapper.appendChild(starImg);

      const bubble = document.createElement('div');
      bubble.className = 'star-bubble';
      bubble.textContent = 'The robber emoji tooootally existed... 👻';
      starWrapper.appendChild(bubble);

      let bubbleTimeout = null;
      starWrapper.addEventListener('click', function (e) {
        e.stopPropagation();
        bubble.classList.add('visible');
        if (bubbleTimeout) {
          clearTimeout(bubbleTimeout);
        }
        bubbleTimeout = setTimeout(function () {
          bubble.classList.remove('visible');
        }, 3000);
      });

      const size = random(24, 52);
      const radius = size / 2;
      let x = 0, y = 0;
      let valid = false;
      let attempts = 0;

      while (!valid && attempts < 150) {
        attempts++;
        x = random(Math.max(radius, 60), Math.max(radius, width - 60));
        y = random(Math.max(radius, 60), Math.max(radius, height - 60));
        valid = true;

        for (const p of placed) {
          const dx = x - p.x;
          const dy = y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < minSpacing + (size + p.size) / 2) {
            valid = false;
            break;
          }
        }
      }

      placed.push({ x, y, size });

      starWrapper.style.left = x + 'px';
      starWrapper.style.top = y + 'px';
      starWrapper.style.width = size + 'px';

      const driftDuration = random(40, 100);
      const driftDelay = random(0, 6);
      const scaleDuration = random(3, 7);
      const scaleDelay = driftDelay + 0.5;

      starWrapper.style.animationDuration = driftDuration + 's';
      starWrapper.style.animationDelay = driftDelay + 's';

      starImg.style.animationDuration = scaleDuration + 's';
      starImg.style.animationDelay = scaleDelay + 's';

      container.appendChild(starWrapper);
    }
  }

  document.addEventListener('DOMContentLoaded', initStars);
})();
