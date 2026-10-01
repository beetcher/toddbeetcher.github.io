// enjoy/done/main.js: intentionally minimal.
// Static page. Register buttons use data-open-register, which opens the sign-up dialog on the main page via ../#register.
document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('js');
  document.querySelectorAll('[data-open-register]').forEach((b) => b.addEventListener('click', () => { location.href = '../#register'; }));
});
