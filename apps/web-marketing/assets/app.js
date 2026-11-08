document.getElementById("menu")?.addEventListener("click", () => {
  document.querySelector(".links")?.classList.toggle("open");
});

document.querySelectorAll("[data-eye]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = document.getElementById(btn.getAttribute("data-eye"));
    if (!input) return;
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Hide" : "Show";
    btn.setAttribute("aria-pressed", show ? "true" : "false");
  });
});

if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  window.addEventListener("pointermove", (event) => {
    document.documentElement.style.setProperty("--mx", event.clientX + "px");
    document.documentElement.style.setProperty("--my", event.clientY + "px");
  }, { passive: true });
}

(async () => {
  const cards = document.querySelectorAll("[data-os]");
  if (!cards.length) return;
  const platform = (navigator.userAgentData?.platform || navigator.userAgent).toLowerCase();
  const os = /android/.test(platform) ? "android"
    : /iphone|ipad|ios/.test(platform) ? "ios"
    : /win/.test(platform) ? "windows"
    : /mac/.test(platform) ? "macos"
    : /linux|cros/.test(platform) ? "linux" : "";
  const ua = navigator.userAgent;
  const browser = navigator.brave ? "brave"
    : /edg\//i.test(ua) ? "edge"
    : /firefox/i.test(ua) ? "firefox"
    : /chrome/i.test(ua) ? "chrome"
    : /safari/i.test(ua) ? "safari" : "";
  cards.forEach((card) => {
    if (card.dataset.os === os || card.dataset.os === "ext-" + browser) card.classList.add("mine");
  });
  const detected = document.getElementById("detected");
  if (detected) detected.textContent = (os || "this device") + (browser ? " · " + browser : "");
})();
