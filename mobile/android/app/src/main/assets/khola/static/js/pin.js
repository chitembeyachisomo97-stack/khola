// KHOLA - 4-digit secure keypad (admin login / sign up / reset)
var pinField = document.getElementById('pin');
var dots = document.getElementById('dots');

function drawDots() { dots.textContent = '●'.repeat(pinField.value.length); }
function k(d) { if (pinField.value.length < 4) { pinField.value += d; drawDots(); } }
function b() { pinField.value = pinField.value.slice(0, -1); drawDots(); }
function c() { pinField.value = ''; drawDots(); }

document.getElementById('pinForm').addEventListener('submit', function (e) {
  if (pinField.value.length != 4) { e.preventDefault(); alert('Enter 4 digits'); }
});
