// KHOLA - order + payment pop-up flow (home page)
var unit = 0;
var orderDlg = document.getElementById('orderDlg');
var payDlg = document.getElementById('payDlg');
var orderForm = document.getElementById('orderForm');
var payForm = document.getElementById('payForm');
var oQty = document.getElementById('oQty');
var oTotal = document.getElementById('oTotal');

function fmt(n) { return 'MWK ' + n.toLocaleString(); }

function openOrder(id, name, price, stock) {
  if (!window.KHOLA_LOGGED_IN) { location = window.KHOLA_LOGIN_URL; return; }
  unit = price;
  document.getElementById('oSize').value = id;
  document.getElementById('oName').textContent = name + ' - K' + price.toLocaleString();
  oQty.max = stock;
  oQty.value = 1;
  oTotal.textContent = fmt(price);
  orderDlg.showModal();
}

oQty.addEventListener('input', function () {
  oTotal.textContent = fmt(unit * (parseInt(oQty.value) || 0));
});

// Step 1: check live Khola stock, then create the order number
orderForm.addEventListener('submit', async function (e) {
  e.preventDefault();
  var r = await fetch(window.KHOLA_ORDER_URL, {
    method: 'POST',
    body: new FormData(orderForm),
    headers: { 'X-CSRF-Token': CSRF }
  });
  var d = await r.json();
  if (!d.ok) { alert(d.error); return; }
  orderDlg.close();
  document.getElementById('pNo').textContent = d.order_no;
  document.getElementById('pTotal').textContent = fmt(d.total);
  payForm.action = '/order/' + d.id + '/pay';
  payDlg.showModal();
});
