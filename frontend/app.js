/**
 * StreamRip Pro — Standalone Vanilla JavaScript Client
 * Communicates with the real Python 3 backend endpoints (/api/analyze, /api/jobs, /api/download)
 */

let currentLang = 'en';

document.getElementById('langToggle')?.addEventListener('click', () => {
  currentLang = currentLang === 'en' ? 'hi' : 'en';
  document.getElementById('heroTitle').textContent =
    currentLang === 'en'
      ? 'Authorized YouTube Media Processor & FFmpeg Workstation'
      : 'अधिकृत YouTube मीडिया प्रोसेसर और FFmpeg वर्कस्टेशन';
});

document.getElementById('analyzeForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = document.getElementById('urlInput').value.trim();
  const errorBox = document.getElementById('errorBox');
  const resultBox = document.getElementById('resultBox');
  errorBox.classList.add('hidden');
  resultBox.classList.add('hidden');

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) {
      errorBox.textContent = `${data.title_en || 'Error'}: ${data.message_en || ''}`;
      errorBox.classList.remove('hidden');
      return;
    }
    resultBox.innerHTML = `
      <div style="margin-top:1.5rem">
        <h3>${data.title}</h3>
        <p>${data.channel} · ${data.duration_formatted} · ${data.video_id}</p>
      </div>
    `;
    resultBox.classList.remove('hidden');
  } catch (err) {
    errorBox.textContent = String(err);
    errorBox.classList.remove('hidden');
  }
});
