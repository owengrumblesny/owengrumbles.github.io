// Toggle between the Dracula (default) and Alucard themes, remembered per visitor.
(function () {
  var root = document.documentElement;
  var btn = document.getElementById("themeToggle");
  if (!btn) return;

  function render() {
    var alucard = root.getAttribute("data-theme") === "alucard";
    // Show the theme you would switch TO.
    btn.textContent = alucard ? "\u263E Dracula" : "\u2600 Alucard";
    btn.setAttribute("aria-label", alucard ? "Switch to the Dracula theme" : "Switch to the Alucard theme");
  }

  render();

  btn.addEventListener("click", function () {
    var alucard = root.getAttribute("data-theme") === "alucard";
    if (alucard) {
      root.removeAttribute("data-theme");
      try { localStorage.setItem("theme", "dracula"); } catch (e) {}
    } else {
      root.setAttribute("data-theme", "alucard");
      try { localStorage.setItem("theme", "alucard"); } catch (e) {}
    }
    render();
  });
})();
