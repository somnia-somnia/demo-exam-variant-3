document.querySelectorAll('.slider').forEach(slider => {
  const slides = [...slider.querySelectorAll('.slide')];
  let current = 0, timer;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const showNext = () => {
    slides[current].hidden = true;
    current = (current + 1) % slides.length;
    slides[current].hidden = false;
  };
  const schedule = () => {
    clearInterval(timer);
    if (!motion.matches && !document.hidden) timer = setInterval(showNext, 3000);
  };
  document.addEventListener('visibilitychange', schedule);
  motion.addEventListener('change', schedule);
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
