let data;
const get = (selector, root = document) => root.querySelector(selector);
const path = location.pathname;
function options(select, values, selected = '') {
  select.replaceChildren(new Option('Выберите', ''));
  for (const value of values) select.add(new Option(value, value, false, value === selected));
}
async function start() {
  const response = await fetch('/api' + location.search);
  data = await response.json();
  if (!response.ok) throw new Error(data.message);
  get('#notice').textContent = sessionStorage.notice || '';
  sessionStorage.removeItem('notice');
  document.body.classList.toggle('logged', !!data.user);
  const admin = data.user && data.user.is_admin;
  const page = path === '/bookings/new' ? 'new' : ['/admin', '/bookings'].includes(path) ? 'orders' : path.slice(1);
  get('#' + page).hidden = false;
  get('#promo').hidden = page === 'orders';
  get('.slider').hidden = page === 'new';
  get('#fleet').hidden = page !== 'new';
  options(get('[name=car]'), data.cars);
  options(get('[name=payment]'), data.payments);
  options(get('#filter select'), data.statuses, data.status);
  get('#filter select').options[0].text = 'Все статусы';
  get('#filter').hidden = !admin;
  get('#create').hidden = !!admin;
  get('#title').textContent = admin ? 'Панель администратора' : 'Мои заявки';
  get('#count').textContent = 'Заявок: ' + data.rows.length;
  get('#empty').hidden = data.rows.length > 0;
  for (const row of data.rows) {
    const card = get('#card').content.cloneNode(true);
    const find = selector => get(selector, card);
    const finished = row.status === data.statuses[2];
    find('h2').textContent = row.car;
    find('.details').textContent = 'Заявка № ' + row.id + ' · ' + row.status + '\n' + row.start_date.split('-').reverse().join('.') + ' · ' + row.payment;
    find('.contact').textContent = row.full_name + ' · ' + row.phone + ' · ' + row.email;
    find('img').src = '/static/img/' + ['vesta.jpg', 'slide1.jpg', 'fleet.jpg'][data.cars.indexOf(row.car)];
    const status = find('.status-form');
    status.hidden = !admin || finished;
    status.action = '/admin/' + row.id + '/status';
    status.elements.filter.value = data.status;
    options(status.elements.status, data.statuses.slice(1), row.status);
    find('.review').hidden = !row.review;
    find('.review p').textContent = row.review;
    const review = find('.review-form');
    review.hidden = !!admin || !finished || !!row.review;
    review.action = '/bookings/' + row.id + '/review';
    find('.booking-note').hidden = !!admin || finished;
    get('#cards').append(card);
  }
}
start().catch(error => get('#notice').textContent = error.message);

document.addEventListener('submit', async event => {
  const form = event.target;
  if (form.method === 'get') return;
  event.preventDefault();
  get('output', form).textContent = '';
  try {
    const body = new FormData(form);
    body.set('csrf', data.csrf);
    const response = await fetch(form.action, {method: 'POST', body: body});
    if (response.redirected) { location.href = response.url; return; }
    const result = await response.json();
    if (response.ok) { sessionStorage.notice = result.message || ''; location.href = result.next; return; }
    get('output', form).textContent = Object.values(result.errors || {message: result.message}).join('\n');
  } catch (error) { get('#notice').textContent = 'Ошибка отправки. Обновите страницу.'; }
});

const slides = document.querySelectorAll('.slide');
let current = 0, timer;
const motion = matchMedia('(prefers-reduced-motion: reduce)');
function show(step) {
  slides[current].hidden = true;
  current = (current + step + slides.length) % slides.length;
  slides[current].hidden = false;
  get('#counter').textContent = current + 1 + ' / ' + slides.length;
}
function schedule() {
  clearInterval(timer);
  if (!motion.matches && !document.hidden) timer = setInterval(() => show(1), 3000);
}
for (const button of document.querySelectorAll('[data-step]')) button.onclick = () => {
  show(Number(button.dataset.step));
  schedule();
};
document.addEventListener('visibilitychange', schedule);
motion.addEventListener('change', schedule);
schedule();
addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
