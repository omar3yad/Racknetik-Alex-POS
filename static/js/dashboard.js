function startClock() {
  const arabicDigits = {
    '0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤',
    '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'
  };

  function update() {
    const el = document.getElementById("live-clock");
    if (!el) return;

    const now = new Date();
    // Adjust to UTC + 2 hours for Cairo time
    const cairoTime = new Date(now.getTime() + now.getTimezoneOffset() * 60 * 1000 + 2 * 60 * 60 * 1000);

    const hh = String(cairoTime.getHours()).padStart(2, "0");
    const mm = String(cairoTime.getMinutes()).padStart(2, "0");
    const ss = String(cairoTime.getSeconds()).padStart(2, "0");

    const formatted = hh + ":" + mm + ":" + ss;
    const arabic = formatted.split("").map(c => arabicDigits[c] || c).join("");
    el.textContent = arabic;
  }

  update();
  setInterval(update, 1000);
}

function startSessionRefresh(url) {
  function refresh() {
    fetch(url)
      .then(res => res.json())
      .then(data => {
        const el = document.getElementById("session-count");
        if (el && data && typeof data.total === "number") {
          el.textContent = data.total;
        }
      })
      .catch(() => {}); // Silently ignore errors
  }

  setInterval(refresh, 60000);
}

startClock();
// startSessionRefresh is called inside the template passing the URL
