// static/js/add_subscription.js (image preview)
document.addEventListener('DOMContentLoaded', function() {
  const input = document.getElementById('logo');
  const preview = document.getElementById('logo-preview');
  if (!input || !preview) return;  // element bestaat niet?

  input.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (!file || !file.type.startsWith('image/')) {
      preview.style.display = 'none';
      return;
    }
    // maak preview
    const url = URL.createObjectURL(file);
    preview.src = url;
    preview.style.display = 'block';
    // vrijgeven als je preview niet meer nodig hebt
    preview.onload = () => URL.revokeObjectURL(url);
  });
});
