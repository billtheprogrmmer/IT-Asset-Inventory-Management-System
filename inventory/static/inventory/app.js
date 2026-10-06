// ITAIMS - small helpers. Everything works without JavaScript except the mobile menu.
document.addEventListener("DOMContentLoaded", function () {
  // Mobile sidebar
  var toggle = document.getElementById("menu-toggle");
  var sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () { sidebar.classList.toggle("open"); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") sidebar.classList.remove("open"); });
  }

  // Filter dropdowns submit the form as soon as they change
  document.querySelectorAll("form.filters select").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });

  // Dismiss flash messages
  document.querySelectorAll(".message button").forEach(function (btn) {
    btn.addEventListener("click", function () { btn.parentElement.remove(); });
  });

  // Print buttons
  document.querySelectorAll("[data-print]").forEach(function (btn) {
    btn.addEventListener("click", function () { window.print(); });
  });
});
