document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.status').forEach((select) => {
    select.addEventListener('change', () => {
      select.disabled = true;
    });
  });
});
