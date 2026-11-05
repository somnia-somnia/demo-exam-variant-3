const slides = document.querySelectorAll('.slide');
let current = 0, timer;
function show(step) {
  slides[current].hidden = true;
  current = (current + step + slides.length) % slides.length;
  slides[current].hidden = false;
  document.querySelector('#counter').textContent = current + 1 + ' / ' + slides.length;
}
function schedule() {
  clearInterval(timer);
  if (slides.length && !document.hidden) timer = setInterval(() => show(1), 3000);
}
for (const button of document.querySelectorAll('[data-step]')) button.onclick = () => {
  show(Number(button.dataset.step));
  schedule();
};
document.addEventListener('visibilitychange', schedule);
schedule();
