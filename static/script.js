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

document.querySelectorAll('input[name="phone"], input[name="start_date"]').forEach(input => {
  input.addEventListener('input', () => {
    const d = input.value.replace(/\D/g, '').slice(0, input.name === 'phone' ? 11 : 8);
    input.value = input.name === 'phone'
      ? d.slice(0, 1) + (d.length > 1 ? '(' + d.slice(1, 4) : '') + (d.length > 4 ? ')' + d.slice(4, 7) : '') + (d.length > 7 ? '-' + d.slice(7, 9) : '') + (d.length > 9 ? '-' + d.slice(9) : '')
      : d.slice(0, 2) + (d.length > 2 ? '.' + d.slice(2, 4) : '') + (d.length > 4 ? '.' + d.slice(4) : '');
  });
});
