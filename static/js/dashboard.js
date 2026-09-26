function startClock() {
  const arabicDigits = {
    '0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤',
    '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'
  };

  function update() {
    const el = document.getElementById("live-clock");
    if (!el) return;

    try {
      const now = new Date();
      const formatter = new Intl.DateTimeFormat("en-US", {
        timeZone: "Africa/Cairo",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
      });

      const parts = formatter.formatToParts(now);
      let hour = "", minute = "", second = "", dayPeriod = "";
      for (const part of parts) {
        if (part.type === "hour") hour = part.value;
        if (part.type === "minute") minute = part.value;
        if (part.type === "second") second = part.value;
        if (part.type === "dayPeriod") dayPeriod = part.value;
      }

      const isPM = (dayPeriod && dayPeriod.toUpperCase() === "PM");
      const ampmArabic = isPM ? "م" : "ص";
      const timeFormatted = `${hour}:${minute}:${second}`;
      const arabicTime = timeFormatted.split("").map(c => arabicDigits[c] || c).join("");
      el.textContent = `${arabicTime} ${ampmArabic}`;
    } catch (e) {
      const now = new Date();
      let hours = now.getHours();
      const ampm = hours >= 12 ? "م" : "ص";
      hours = hours % 12;
      hours = hours ? hours : 12;
      const hh = String(hours).padStart(2, "0");
      const mm = String(now.getMinutes()).padStart(2, "0");
      const ss = String(now.getSeconds()).padStart(2, "0");
      const formatted = hh + ":" + mm + ":" + ss;
      const arabic = formatted.split("").map(c => arabicDigits[c] || c).join("");
      el.textContent = arabic + " " + ampm;
    }
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
