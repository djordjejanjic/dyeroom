"use strict";
// The site's pages need almost no script: a Copy button on code blocks (the install lines),
// shown only where the browser lets a page copy.
document.querySelectorAll(".code").forEach((block) => {
  const button = block.querySelector(".copy");
  if (!button || !navigator.clipboard) return;
  button.hidden = false;
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(block.querySelector("code").textContent);
      button.textContent = "Copied";
    } catch (_) {
      button.textContent = "Select and copy";
    }
    setTimeout(() => { button.textContent = "Copy"; }, 1800);
  });
});
