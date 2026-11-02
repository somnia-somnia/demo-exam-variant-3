document.querySelectorAll('.slider').forEach(slider => {
  const slides = [...slider.querySelectorAll('.slide')];
  const counter = slider.querySelector('.slide-count');
  const pause = slider.querySelector('.pause');
  let current = 0, timer;
  let paused = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const show = step => {
    slides[current].hidden = true;
    current = (current + step + slides.length) % slides.length;
    slides[current].hidden = false;
    counter.textContent = `${current + 1} / ${slides.length}`;
  };
  const schedule = () => {
    clearInterval(timer);
    if (!paused && !document.hidden) timer = setInterval(() => show(1), 3000);
    pause.setAttribute('aria-pressed', String(paused));
    pause.setAttribute('aria-label', paused ? 'Возобновить автосмену' : 'Приостановить автосмену');
    pause.textContent = paused ? '▶' : 'Ⅱ';
  };
  slider.querySelectorAll('[data-step]').forEach(button => button.addEventListener('click', () => {
    show(Number(button.dataset.step)); schedule();
  }));
  pause.addEventListener('click', () => { paused = !paused; schedule(); });
  slider.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault(); show(event.key === 'ArrowRight' ? 1 : -1); schedule();
    }
  });
  document.addEventListener('visibilitychange', schedule);
  schedule();
});
