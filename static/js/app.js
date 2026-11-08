// KHOLA - shared JavaScript (loaded on every page)

// 1) Add the CSRF security token to every POST form
document.querySelectorAll('form').forEach(function (f) {
  if ((f.getAttribute('method') || '').toLowerCase() === 'post') {
    var i = document.createElement('input');
    i.type = 'hidden';
    i.name = 'csrf_token';
    i.value = CSRF;
    f.appendChild(i);
  }
});

// 2) Make the website installable as an app (PWA)
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(function () {});
}
var deferredPrompt = null;
var installBtn = document.getElementById('installBtn');
window.addEventListener('beforeinstallprompt', function (e) {
  e.preventDefault();
  deferredPrompt = e;
  installBtn.style.display = 'inline-block';
});
installBtn.addEventListener('click', function () {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt = null;
    installBtn.style.display = 'none';
  }
});
